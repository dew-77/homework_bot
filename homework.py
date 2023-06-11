import requests
import telegram
import time
import logging
import os
import sys
from dotenv import load_dotenv
from exceptions import StatusCodeError


logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')

handler.setFormatter(formatter)
logger.addHandler(handler)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

homework_statuses = {}


def check_tokens():
    """Проверка переменных окружения."""
    vars = [TELEGRAM_CHAT_ID, TELEGRAM_TOKEN, PRACTICUM_TOKEN]
    for var in vars:
        if not var:
            return False
    return True


def send_message(bot, message):
    """Отправка сообщения ботом в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(f'Error sending message: {error}')
    else:
        logging.debug('Message sent')


def get_api_answer(timestamp):
    """
    Запрос к эндпоинту.
    В случае успеха возвращает ответ API, приведенный к типам данных Python.
    """
    try:
        response = requests.get(
            url=ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if response.status_code != 200:
            raise StatusCodeError(
                f'Status code is different from 200 : {response.status_code}'
            )
        return response.json()
    except requests.RequestException():
        logging.error('Endpoint not available')
        return None
    except Exception as error:
        logging.error(f'Endpoint request error: {error}')


def check_response(response):
    """Проверка ответа API."""
    if type(response) != dict:
        msg = f'Incorrect type of API response: {type(response)}'
        logging.error(msg)
        raise TypeError(msg)
    keys = ['homeworks', 'current_date']
    missing_keys = [key for key in keys if key not in response]
    if missing_keys:
        msg = f'Keys are missing: {", ".join(missing_keys)}'
        logging.error(msg)
        raise KeyError(msg)
    if type(response['homeworks']) != list:
        msg = f'Incorrect type of homework: {type(response["homeworks"])}'
        logging.error(msg)
        raise TypeError(msg)
    return True


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    subkeys = ['status', 'homework_name']
    missing_subkeys = [
        subkey for subkey in subkeys if subkey not in homework
    ]
    if missing_subkeys:
        msg = f'Subkeys are missing: {", ".join(missing_subkeys)}'
        logging.error(msg)
        raise KeyError(msg)

    homework_name = homework['homework_name']
    hw_status = homework['status']
    if hw_status not in HOMEWORK_VERDICTS:
        msg = f'Incorrect status of homework: {hw_status}'
        logging.error(msg)
        raise KeyError(msg)

    if ((homework_name not in homework_statuses)
            or (homework_statuses[homework_name] != hw_status)):
        homework_statuses[homework_name] = hw_status
        verdict = HOMEWORK_VERDICTS[hw_status]
        message = (f'Изменился статус проверки работы "{homework_name}". '
                   f'{verdict}')
        logger.debug(message)
        return message
    else:
        logger.debug('No new statuses')
        return ''


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    else:
        logger.critical('One of the environment variables is missing')
        raise ValueError('Missing environment variables')

    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if len(response['homeworks']) > 0:
                status = parse_status(response['homeworks'][0])
                send_message(bot, status)
            timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
