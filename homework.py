import json
import logging
import os
import sys
import time
from http import HTTPStatus

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
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
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
    except telegram.error.TelegramError as error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {error}')


def get_api_answer(timestamp):
    """Создаёт запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    logging.info(f'Отправляем запрос к API: {ENDPOINT}')
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка запроса к: {ENDPOINT}, {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        raise ConnectionError(
            f'Ошибка подключения: {homework_statuses.status_code}'
        )
    try:
        response = homework_statuses.json()
        return response
    except json.JSONDecodeError as error:
        raise TypeError(
            f'Ошибка преобразования полученного ответа json:'
            f'{type(response)}, {error}'
        )


def check_response(response):
    """Проверяет ответ от эндпоинта."""
    if not isinstance(response, dict):
        logger.error('Произошла ошибка. Ответ не является словарем.')
        raise TypeError('Произошла ошибка. Ответ не является словарем.')
    try:
        homeworks = response['homeworks']

    except KeyError as error:
        logger.error(f'Невозможно получить необходимое содержимое: {error}')
        raise KeyError(f'Невозможно получить необходимое содержимое: {error}')
    if not isinstance(response['homeworks'], list):
        logger.error('По ключу "homeworks" не получен список')
        raise TypeError('По ключу "homeworks" не получен список')
    return homeworks


def parse_status(homework):
    """Получение информации о домашней работе."""
    homework_name = homework.get('homework_name')
    if not homework.get('homework_name'):
        logging.warning('Отсутствует имя домашней работы')
        raise KeyError('Отсутствует имя домашней работы')

    status = homework.get('status')
    if 'status' not in homework:
        message = 'Отсуствует статуст домашней работы'
        logging.error(message)
        raise ParseStatusError(message)

    if status not in HOMEWORK_VERDICTS:
        message = 'Статус домашней работы не определен.'
        logging.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS.get(status)

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
