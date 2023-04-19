import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import ParseStatusError

load_dotenv()
logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELECHAT')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

REQUIRED_TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')


def check_tokens():
    """Проверка доступа токенов."""
    if not all(globals()[token] for token in REQUIRED_TOKENS):
        missing_tokens = [
            token for token in REQUIRED_TOKENS if globals()[token] is None
        ]
        error_msg = f"Отсутствующие токены: {', '.join(missing_tokens)}"
        logging.critical(error_msg)
        raise ValueError(error_msg)


def send_message(bot, message):
    """Отправка сообщений."""
    try:
        logger.debug(f'Начата отправка сообщения: {message}')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(
            f'Сообщение в Telegram отправлено: {message}')
        return True
    except telegram.error.TelegramError as error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {error}')
        return False


def get_api_answer(timestamp):
    """Создаёт запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    logging.info(f'Отправляем запрос к API: {ENDPOINT}')
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
    except requests.exceptions:
        raise ConnectionError(f'Ошибка запроса к: {ENDPOINT}')
    if homework_statuses.status_code != 200:
        raise ConnectionError(
            f'Ошибка подключения: {homework_statuses.status_code}'
        )
    try:
        response = homework_statuses.json()
        return response
    except Exception:
        raise TypeError(
            f'Ошибка преобразования полученного ответа json: {type(response)}'
        )


def check_response(response):
    """Проверяет ответ от эндпоинта."""
    if not isinstance(response, dict):
        logger.error('Произошла ошибка. Ответ не является словарем.')
        raise TypeError('Произошла ошибка. Ответ не является словарем.')
    try:
        homeworks = response['homeworks']
    except KeyError:
        logger.error('Не возможно получить необходимое содержимое.')
        raise KeyError('Не возможно получить необходимое содержимое.')
    if not isinstance(response['homeworks'], list):
        logger.error('Произошла ошибка. Ответ не является списком.')
        raise TypeError('Произошла ошибка. Ответ не является списком.')
    try:
        homeworks[0]
    except IndexError:
        logger.error('Список домашних работ пуст.')
        raise IndexError('Список домашних работ пуст.')
    return homeworks


def parse_status(homework):
    """Получение информации о домашней работе."""
    if not homework.get('homework_name'):
        logging.warning('Отсутствует имя домашней работы')
        raise KeyError('Отсутствует имя домашней работы')

    homework_name = homework.get('homework_name')

    status = homework.get('status')
    if 'status' not in homework:
        message = 'Отсуствует статуст домашней работы'
        logging.error(message)
        raise ParseStatusError(message)

    verdict = HOMEWORK_VERDICTS.get(status)
    if status not in HOMEWORK_VERDICTS:
        message = 'Недокументированный статус домашщней работы'
        logging.error(message)
        raise KeyError(message)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD
    last_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                last_message = message

            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Program failed: {error}'
            logging.exception(message)

            if last_message != message:
                send_message(bot, message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[
            logging.FileHandler(
                filename='homework.log', mode='w', encoding='UTF-8'),
            logging.StreamHandler(stream=sys.stdout)
        ],
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
    )

    main()
