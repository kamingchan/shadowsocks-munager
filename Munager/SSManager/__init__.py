import json
import os
import socket
from logging import getLogger

from redis import Redis

from Munager.SSManager.SNIProxy import SNIProxy


class SSManager:
    def __init__(self, config):
        self.config = config
        self.logger = getLogger()
        self.cli = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.cli.settimeout(self.config.get('timeout', 10))
        self.cli.bind(self.config.get('bind_address'))
        self.cli.connect(self.config.get('manager_address'))  # address of Shadowsocks manager
        self.redis = Redis(
            host=self.config.get('redis_host', 'localhost'),
            port=self.config.get('redis_port', 6379),
            db=self.config.get('redis_db', 0),
        )
        self.sniproxy = SNIProxy(self.config)

        # load throughput log to redis
        self.cli.send(b'ping')
        res = self.cli.recv(1506).decode('utf-8').replace('stat: ', '')
        res_json = json.loads(res)
        redis_keys = self.redis.keys()
        for port, throughput in res_json.items():
            # check user information in redis
            if self._get_key(['user', port]).encode('utf-8') in redis_keys:
                cursor = int(self.redis.hget(self._get_key(['user', port]), 'cursor').decode('utf-8'))
                if cursor < throughput:
                    self.logger.info('port: {} wait for upload throughput.'.format(port))
                else:
                    self.redis.hset(self._get_key(['user', port]), 'cursor', throughput)
                    self.logger.info('reset port: {} cursor: {}.'.format(port, throughput))
            else:
                # wait for next check and add information from MuAPI
                self.logger.info('remove port: {} due to lost data in redis.'.format(port))
                self.remove(port)
            # Sync user information from Redis to SNIProxy
            password = self.redis.hget(self._get_key(['user', port]), 'password').decode('utf-8')
            self.sniproxy.add(port, password)
        self.logger.info('SSManager initializing.')

    @staticmethod
    def _to_unicode(_d):
        # change to unicode when get a hash table from redis
        ret = dict()
        for k, v in _d.items():
            ret[k.decode('utf-8')] = v.decode('utf-8')
        return ret

    @staticmethod
    def _fix_type(_d):
        # convert type when get a unicode dict from redis
        _d['cursor'] = int(_d.get('cursor', 0))
        return _d

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
        ret_by_port, ret_by_uid = dict(), dict()
        for port, throughput in res_json.items():
            info = self.redis.hgetall(self._get_key(['user', str(port)]))
            info = self._to_unicode(info)
            info = self._fix_type(info)
            info['throughput'] = throughput
            info['port'] = port
            user_id = info.get('user_id')
            ret_by_port[int(port)] = info
            ret_by_uid[user_id] = info
        return ret_by_port, ret_by_uid

    def add(self, user_id, port, password, method, plugin, plugin_opts):
        msg = dict(
            server_port=port,
            password=password,
            method=method,
            fast_open=self.config.get('fast_open'),
            mode=self.config.get('mode'),
            plugin=plugin,
            plugin_opts=plugin_opts,
        )
        req = 'add: {msg}'.format(msg=json.dumps(msg))
        # to bytes
        req = req.encode('utf-8')
        self.cli.send(req)
        self.sniproxy.add(port, password)
        pipeline = self.redis.pipeline()
        pipeline.hset(self._get_key(['user', str(port)]), 'cursor', 0)
        pipeline.hset(self._get_key(['user', str(port)]), 'user_id', user_id)
        pipeline.hset(self._get_key(['user', str(port)]), 'password', password)
        pipeline.hset(self._get_key(['user', str(port)]), 'method', method)
        pipeline.hset(self._get_key(['user', str(port)]), 'plugin', plugin)
        pipeline.hset(self._get_key(['user', str(port)]), 'plugin_opts', plugin_opts)
        pipeline.execute()
        return self.cli.recv(1506) == b'ok'

    def remove(self, port):
        msg = dict(
            server_port=int(port),
        )
        req = 'remove: {msg}'.format(msg=json.dumps(msg))
        req = req.encode('utf-8')
        self.cli.send(req)
        self.sniproxy.remove(port)
        return self.cli.recv(1506) == b'ok'

    def reset_inactive_port(self):
        ports, _ = self.state
        for port, info in ports.items():
            if info.get('cursor') == info.get('throughput'):
                self.remove(port)

    def set_cursor(self, port, data):
        self.redis.hset(self._get_key(['user', str(port)]), 'cursor', data)

    def __del__(self):
        bind_address = self.config.get('bind_address')
        if os.path.exists(bind_address):
            os.remove(bind_address)
