import logging


def get_logger(name, config):
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt=config.get('log_format', '[%(name)s][%(asctime)s][%(lineno)3d][%(levelname)7s] %(message)s'),
        datefmt=config.get('date_time_format', '%m-%d %H:%M:%S'),
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(config.get('log_level', 'DEBUG'))
    return logger
