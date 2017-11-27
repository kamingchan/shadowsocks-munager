import logging
import os

import click
import yaml

from Munager import Munager


@click.command()
@click.option('--config-file', default='./config/config.yml', help='Configuration file path.')
def bootstrap(config_file):
    # load config
    with open(config_file) as f:
        config = yaml.load(f.read())

    # replace config with environment variables
    env_variables = os.environ
    config.update(env_variables)

    # set logger
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt=config.get('log_format', '[%(name)s][%(asctime)s][%(lineno)3d][%(levelname)7s] %(message)s'),
        datefmt=config.get('date_time_format', '%m-%d %H:%M:%S'),
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(config.get('log_level', 'DEBUG'))
    logger.debug('load config from {}.'.format(config_file))

    app = Munager(config)
    app.run()


if __name__ == '__main__':
    bootstrap()
