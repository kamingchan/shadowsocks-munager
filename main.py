import json
import socket
from signal import signal, SIGINT
from time import sleep

import requests

from config import *


class SSManager:
    def __init__(self, manager_ip, manager_port):
        self.cli = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cli.settimeout(SOCKET_TIMEOUT)
        self.cli.connect((manager_ip, manager_port))  # address of Shadowsocks manager

    @property
    def state(self):
        try:
            self.cli.send(b'ping')
            res = self.cli.recv(1506).decode('utf-8').replace('stat: ', '')
        except socket.timeout as e:
            logging.exception(e)
            return None
        except ConnectionRefusedError as e:
            logging.exception(e)
            return None
        # change key from str to int
        res_json = json.loads(res)
        logging.info('get state from ss-manage succeed!')
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
            plugin=PLUGIN,
            plugin_opts=PLUGIN_OPTS,
            fast_open=FAST_OPEN,
            mode=MODE
        )
        req = 'add: {msg}'.format(msg=json.dumps(msg))
        # to bytes
        req = req.encode('utf-8')
        try:
            self.cli.send(req)
            return self.cli.recv(1506) == b'ok'
        except socket.timeout as e:
            logging.exception(e)
            return False
        except ConnectionRefusedError as e:
            logging.exception(e)
            return False

    def remove(self, port):
        req = 'remove: {"server_port":%d}' % (port,)
        req = req.encode('utf-8')
        try:
            self.cli.send(req)
            return self.cli.recv(1506) == b'ok'
        except socket.timeout as e:
            logging.exception(e)
            return False
        except ConnectionRefusedError as e:
            logging.exception(e)
            return False


class MuAPI:
    def __init__(self, url, key, node_id):
        self.url = url
        self.key = key
        self.node_id = node_id
        self.session = requests.session()
        self.session.params = {'key': self.key}

    @property
    def users(self) -> dict or None:
        """
        port: User object
        """
        try:
            res = self.session.get(self.url + '/users', timeout=HTTP_TIMEOUT).json()
        except requests.exceptions.RequestException as e:
            logging.exception(e)
            logging.warning('api connection error, check your network or ss-panel.')
            return None
        except ValueError as e:
            logging.exception(e)
            logging.warning('load json error, check your ss-panel.')
            return None
        if res['ret'] != 1:
            logging.error(res['msg'])
            return None
        ret = dict()
        for user in res['data']:
            ret[user['port']] = User(**user)
        return ret

    def add_traffic(self, user_id, traffic):
        url = self.url + '/users/%d/traffic' % (user_id,)
        data = {
            'u': 0,
            'd': traffic,
            'node_id': self.node_id
        }
        try:
            res = self.session.post(url, data=data, timeout=HTTP_TIMEOUT).json()
        except requests.exceptions.RequestException as e:
            logging.exception(e)
            logging.warning('api connection error, check your network or ss-panel.')
            return False
        except ValueError as e:
            logging.exception(e)
            logging.warning('load json error, check your ss-panel.')
            return False
        if res['ret'] != 1:
            logging.error(res['msg'])
            return False
        return True

    def post_online_user(self, amount):
        url = self.url + '/nodes/%d/online_count' % (self.node_id,)
        data = {
            'count': amount
        }
        try:
            res = self.session.post(url, data=data, timeout=HTTP_TIMEOUT).json()
        except requests.exceptions.RequestException as e:
            logging.exception(e)
            logging.warning('api connection error, check your network or ss-panel.')
            return False
        except ValueError as e:
            logging.exception(e)
            logging.warning('load json error, check your ss-panel.')
            return False
        if res['ret'] != 1:
            logging.error(res['msg'])
            return False
        return True

    def post_load(self, load, uptime):
        url = self.url + '/nodes/%d/info' % (self.node_id,)
        data = {
            'load': load,
            'uptime': uptime
        }
        try:
            res = self.session.post(url, data=data, timeout=HTTP_TIMEOUT).json()
        except requests.exceptions.RequestException as e:
            logging.exception(e)
            logging.warning('api connection error, check your network or ss-panel.')
            return False
        except ValueError as e:
            logging.exception(e)
            logging.warning('load json error, check your ss-panel.')
            return False
        if res['ret'] != 1:
            logging.error(res['msg'])
            return False
        return True


class User:
    def __init__(self, **entries):
        self.__dict__.update(entries)
        # from Mu api
        # passwd: ss password
        # method: ss method

    @property
    def available(self):
        return self.u + self.d < self.transfer_enable and self.enable == 1


def post_traffic():
    online_users = 0
    for port, traffic in state.items():
        dif = traffic - throughput_count[port]
        user_id = users[port].id
        if dif < 0:
            throughput_count[port] = traffic
            logging.warning('ss manager may be restarted, reset upload traffic.')
        if dif > 0:
            online_users += 1
            if api.add_traffic(user_id, dif):
                throughput_count[port] = traffic
                logging.info('upload user: %d traffic: %d succeed!' % (user_id, dif))
            else:
                logging.error('upload user: %d traffic: %d fail!' % (user_id, dif))
    if api.post_online_user(online_users):
        logging.info('upload online users succeed!')
    else:
        logging.warning('upload online users fail!')


def reset_manager():
    logging.info('start to reset manager.')
    for port, traffic in state.items():
        if port not in users or not users[port].available:
            ss_manager.remove(port)
            logging.info('reset manager, remove port: %d' % (port,))
        else:
            throughput_count[port] = traffic
            logging.info('reset manager, init port: %d with traffic: %d' % (port, traffic))
    # add port
    for port, user in users.items():
        if user.available and port not in state:
            ss_manager.add(port, user.passwd, user.method)
            throughput_count[port] = 0
            logging.info('add port: %d, password: %s, method: %s' % (port, user.passwd, user.method))
        # add password and method
        user_password[port] = user.passwd
        user_method[port] = user.method
    logging.info('reset manager finish.')


def sync_port():
    # remove port
    for port, traffic in state.items():
        if port not in users or not users[port].available:
            ss_manager.remove(port)
            logging.info('remove port: %d' % (port,))
    # add port
    for port, user in users.items():
        if user.available and port not in state:
            ss_manager.add(port, user.passwd, user.method)
            # reset traffic
            throughput_count[port] = 0
            user_password[port] = user.passwd
            user_method[port] = user.method
            logging.info('add port: %d, password: %s, method: %s' % (port, user.passwd, user.method))
        if user.available and port in state:
            # check password and method change
            if user.passwd != user_password[port] or user.method != user_method[port]:
                logging.info('port: %d change password or method, reset.' % (port,))
                ss_manager.remove(port)
                ss_manager.add(port, user.passwd, user.method)
                throughput_count[port] = 0
                user_password[port] = user.passwd
                user_method[port] = user.method


def upload_load():
    with open('/proc/loadavg') as f:
        load = f.read()
    with open('/proc/uptime') as f:
        uptime = f.read().split()[0]
    if api.post_load(load, uptime):
        logging.info('upload load succeed!')
    else:
        logging.warning('upload load fail!')


def int_signal_handler(signal, _):
    logging.info('receive signal {}, upload traffic'.format(signal))
    post_traffic()
    logging.info('exting...')
    exit(0)


if __name__ == '__main__':
    api = MuAPI(URL, KEY, ID)
    ss_manager = SSManager(MANAGER_IP, MANAGER_PORT)

    throughput_count = dict()
    user_password = dict()
    user_method = dict()

    users = api.users
    state = ss_manager.state
    if users is None or state is None:
        logging.error('start fail, please check network!')
        exit(1)
    reset_manager()
    signal(SIGINT, int_signal_handler)
    while True:
        # upload load
        upload_load()
        # sleep
        logging.info('thread start sleep.')
        sleep(UPDATE_TIME)
        logging.info('thread wake up.')
        # update two side information
        users = api.users
        if users is None:
            logging.warning('get from mu api timeout!')
            continue
        state = ss_manager.state
        if state is None:
            logging.warning('get from ss manager timeout!')
            continue
        # post traffic
        post_traffic()
        # sync port
        sync_port()
