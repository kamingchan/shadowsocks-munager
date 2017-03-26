URL = 'https://www.example.com/mu'
KEY = 'your_key'
UPDATE_TIME = 120
ID = 1

MANAGER_IP = '127.0.0.1'
MANAGER_PORT = 8888

SOCKET_TIMEOUT = 10
HTTP_TIMEOUT = 10
FAST_OPEN = True
PLUGIN = 'obfs-server'
PLUGIN_OPTS = 'obfs=http'

import logging

logging.basicConfig(
    format='TIME %(asctime)s LINE %(lineno)-4d  %(levelname)-8s %(message)s',
    datefmt='%m-%d %H:%M',
    level=logging.INFO
)
