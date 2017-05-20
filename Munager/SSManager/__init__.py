import json
import socket

from redis import Redis

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
        self.redis = Redis(
            host=self.config.get('redis_host', 'localhost'),
            port=self.config.get('redis_port', 6379),
            db=self.config.get('redis_db', 0),
        )

        # load throughput log to redis
        self.cli.send(b'ping')
        res = self.cli.recv(1506).decode('utf-8').replace('stat: ', '')
        res_json = json.loads(res)
        redis_keys = self.redis.keys()
        for port, throughput in res_json.items():
            # check user information in redis
            if self._get_key(['user', port]) in redis_keys:
                self.redis.set(self._get_key(['throughput', port]), throughput)
            else:
                # wait for next check and add information from MuAPI
                self.remove(port)
        self.logger.info('SSManager initializing.')

    @staticmethod
    def _to_unicode(_d):
        # change to unicode when get a hash table from redis
        ret = dict()
        for k, v in _d.items():
            ret[k.decode('utf-8')] = v.decode('utf-8')
        return ret

    def _get_key(self, _keys):
        keys = [self.config.get('redis_prefix', 'mu')]
        keys.extend(_keys)
        return ':'.join(keys)

    @property
    def state(self):
        self.cli.send(b'ping')
        res = self.cli.recv(1506).decode('utf-8').replace('stat: ', '')
        # change key from str to int
        res_json = json.loads(res)
        ret = dict()
        for port, throughput in res_json.items():
            info = self.redis.hgetall(self._get_key(['user', str(port)]))
            info = self._to_unicode(info)
            info['throughput'] = throughput
            ret[int(port)] = info
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
        self.cli.send(req)
        pipeline = self.redis.pipeline()
        pipeline.set(self._get_key(['throughput', str(port)]), 0)
        pipeline.hset(self._get_key(['user', str(port)]), 'password', password)
        pipeline.hset(self._get_key(['user', str(port)]), 'method', method)
        pipeline.execute()
        return self.cli.recv(1506) == b'ok'

    def remove(self, port):
        port = int(port)
        msg = dict(
            server_port=port,
        )
        req = 'remove: {msg}'.format(msg=json.dumps(msg))
        req = req.encode('utf-8')
        self.cli.send(req)
        return self.cli.recv(1506) == b'ok'
