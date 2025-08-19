# utils/logging_utils.py
import logging
from logging.handlers import TimedRotatingFileHandler
import os

def setup_logging(log_dir="/home/ec2-user/blog-tistory-comment-bot/log"):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch_formatter = logging.Formatter('[%(asctime)s] %(levelname)s | %(name)s:%(lineno)d >>> %(message)s')
    ch.setFormatter(ch_formatter)
    logger.addHandler(ch)

    # file handler rotating daily
    fh = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "server.log"),
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(ch_formatter)
    logger.addHandler(fh)

    return logger

