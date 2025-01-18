import logging
from logging import Logger
import time

_logger = None


def __get_formatter():
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: - %(message)s')
    formatter.converter = time.gmtime
    return formatter


def get_logger() -> Logger:
    """
    Returns the singleton logger instance. Initializes it if it doesn't exist.
    """
    global _logger
    if _logger is None:
        _logger = logging.getLogger('Logger')
        _logger.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler()

        console_handler.setLevel(logging.INFO)

        console_handler.setFormatter(__get_formatter())

        _logger.addHandler(console_handler)

    return _logger


def add_log_file_handler(path: str):
    file_handler = logging.FileHandler(
        path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(__get_formatter())
    get_logger().addHandler(file_handler)
