# coding=utf-8
import logging
import os
from datetime import datetime

LOG_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep + '..' + os.sep + '..' + os.sep + 'logs' + os.sep
LOG_FILE_PATH = LOG_DIR + 'localbuild.{}.log'.format(datetime.now().strftime('%Y%m%d'))
LOGGER = None


def get_logger():
    global LOGGER
    if LOGGER is None:
        LOGGER = _Logging().get_logger()
    return LOGGER


class _Logging:
    def __init__(self, filename=LOG_FILE_PATH):
        self.filename = filename
        self.format = logging.Formatter('%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self._setup_console_logger()
        self._setup_file_logger()

    def _setup_console_logger(self):
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(self.format)
        self.logger.addHandler(handler)

    def _setup_file_logger(self):
        log_dir = os.path.dirname(self.filename)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        fileLog = logging.FileHandler(self.filename)
        fileLog.setLevel(logging.DEBUG)
        fileLog.setFormatter(self.format)
        self.logger.addHandler(fileLog)

    def get_logger(self):
        return self.logger
