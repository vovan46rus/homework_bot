class ParseStatusError(Exception):
    def __init__(self, text):
        message = (
            f'Парсинг ответа API: {text}'
        )
        super().__init__(message)


class MessageError(Exception):
    """Ошибка во время отправки сообщения в телеграм."""

    def __init__(self, error):
        self.error = error

    def __str__(self):
        return ('Во время отправки сообщения в телеграм произошел сбой!'
                f'Ошибка: {self.error}')
