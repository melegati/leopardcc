import logging
import datetime

_logger = None


def get_logger():
    """
    Returns the singleton logger instance. Initializes it if it doesn't exist.
    """
    global _logger
    if _logger is None:
        _logger = logging.getLogger('MyAppLogger')
        _logger.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler()
        filename = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d-%H-%M-%S") + '.txt'
        file_handler = logging.FileHandler(
            'app-logs/' + filename)

        console_handler.setLevel(logging.INFO)
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: - %(message)s')
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        _logger.addHandler(console_handler)
        _logger.addHandler(file_handler)

    return _logger
