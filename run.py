import click

from Munager import Munager


@click.command()
@click.option('--config-file', default='./config/config.yml', help='Configuration file path.')
def bootstrap(config_file):
    app = Munager(config_file)
    app.run()


if __name__ == '__main__':
    bootstrap()
