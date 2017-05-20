import json
import socket

from Munager.Utils import get_logger


class SSManager:
    def __init__(self, config):
        self.config = config
        self.logger = get_logger('SSManager', config)
        self.cli = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cli.settimeout(self.config.get('timeout', 10))
        self.cli.connect(
            # (ip, port)
            (self.config.get('manager_ip'), self.config.get('manager_port'))
        )  # address of Shadowsocks manager
        self.logger.info('SSManager initializing.')

    @property
    def state(self):
        try:
            self.cli.send(b'ping')
            res = self.cli.recv(1506).decode('utf-8').replace('stat: ', '')
        except ConnectionError as e:
            self.logger.exception(e)
            return dict()
        # change key from str to int
        res_json = json.loads(res)
        self.logger.info('get state from ss-manage succeed!')
        ret = dict()
        for k, v in res_json.items():
            # port: throughput
            ret[int(k)] = v
        return ret

    def add(self, port, password, method):
        msg = dict(
            server_port=port,
            password=password,
            method=method,
            fast_open=self.config.get('fast_open'),
            mode=self.config.get('mode'),
            plugin=self.config.get('plugin'),
            plugin_opts=self.config.get('plugin_opts'),
        )
        req = 'add: {msg}'.format(msg=json.dumps(msg))
        # to bytes
        req = req.encode('utf-8')
        try:
            self.cli.send(req)
            return self.cli.recv(1506) == b'ok'
        except ConnectionError as e:
            self.logger.exception(e)
            return False

    def remove(self, port):
        msg = dict(
            server_port=port,
        )
        req = 'remove: {msg}'.format(msg=json.dumps(msg))
        req = req.encode('utf-8')
        try:
            self.cli.send(req)
            return self.cli.recv(1506) == b'ok'
        except ConnectionError as e:
            self.logger.exception(e)
            return False
