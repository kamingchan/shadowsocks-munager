import json
import socket
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
        self.cli.send(b'ping')
        try:
            res = self.cli.recv(1506).decode('utf-8').replace('stat: ', '')
        except socket.timeout:
            return None
        except ConnectionRefusedError:
            return None
        # change key from str to int
        res_json = json.loads(res)
        logging.info('get state from ss-manage succeed!')
        ret = dict()
        for k, v in res_json.items():
            ret[int(k)] = v
        return ret

    def add(self, port, password):
        req = 'add: {"server_port":%d, "password":"%s"}' % (port, password)
        req = req.encode('utf-8')
        try:
            self.cli.send(req)
            return self.cli.recv(1506) == b'ok'
        except socket.timeout:
            return False
        except ConnectionRefusedError:
            return False

    def remove(self, port):
        req = 'remove: {"server_port":%d}' % (port,)
        req = req.encode()
        try:
            self.cli.send(req)
            return self.cli.recv(1506) == b'ok'
        except socket.timeout:
            return False
        except ConnectionRefusedError:
            return False


class MuAPI:
    def __init__(self, url, key, node_id):
        self.url = url
        self.key = key
        self.node_id = node_id

    @property
    def users(self):
        try:
            res = requests.get(self.url + '/users', params={'key': self.key}).json()
        except requests.exceptions.RequestException:
            logging.warning('api connection error, check your network or ss-panel.')
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
        para = {
            'u': 0,
            'd': traffic,
            'node_id': self.node_id
        }
        try:
            res = requests.post(url, params={'key': self.key}, data=para).json()
        except requests.exceptions.RequestException:
            logging.warning('api connection error, check your network or ss-panel.')
            return False
        if res['ret'] != 1:
            logging.error(res['msg'])
            return False
        logging.info('upload traffic succeed.')
        return True

    def post_online_user(self, amount):
        url = self.url + '/nodes/%d/online_count' % (self.node_id,)
        para = {
            'count': amount
        }
        try:
            res = requests.post(url, params={'key': self.key}, data=para).json()
        except requests.exceptions.RequestException:
            logging.warning('api connection error, check your network or ss-panel.')
            return False
        if res['ret'] != 1:
            logging.error(res['msg'])
            return False
        logging.info('upload online users succeed.')
        return True

    def post_load(self, load, uptime):
        url = self.url + '/nodes/%d/info' % (self.node_id,)
        para = {
            'load': load,
            'uptime': uptime
        }
        try:
            res = requests.post(url, params={'key': self.key}, data=para).json()
        except requests.exceptions.RequestException:
            logging.warning('api connection error, check your network or ss-panel.')
            return False
        if res['ret'] != 1:
            logging.error(res['msg'])
            return False
        logging.info('upload load users succeed.')
        return True


class User:
    def __init__(self, **entries):
        self.__dict__.update(entries)

    @property
    def available(self):
        return self.u + self.d < self.transfer_enable and self.enable == 1


def post_traffic():
    online_users = 0
    for port, traffic in state.items():
        dif = traffic - count[port]
        user_id = users[port].id
        if dif < 0:
            count[port] = traffic
            logging.warning('ss manager may be restarted, reset upload traffic.')
        if dif > 0:
            online_users += 1
            if api.add_traffic(user_id, dif):
                count[port] = traffic
                logging.info('upload user: %d traffic: %d succeed!' % (user_id, dif))
            else:
                logging.error('upload user: %d traffic: %d fail!' % (user_id, dif))
    api.post_online_user(online_users)


def reset_manager():
    logging.info('start to reset manager.')
    for port, traffic in state.items():
        if users[port].available:
            count[port] = traffic
            logging.info('reset manager, init port: %d with traffic: %d' % (port, traffic))
        else:
            ss_manager.remove(port)
            logging.info('reset manager, remove port: %d' % (port,))
    # add port
    for port, user in users.items():
        if user.available and port not in state:
            ss_manager.add(port, user.passwd)
            count[port] = 0
            logging.info('add port: %d with password: %s' % (port, user.passwd))
    logging.info('reset manager finish.')


def sync_port():
    # remove port
    for port, traffic in state.items():
        if not users[port].available:
            ss_manager.remove(port)
            logging.info('remove port: %d' % (port,))
    # add port
    for port, user in users.items():
        if user.available and port not in state:
            ss_manager.add(port, user.passwd)
            # reset traffic
            count[port] = 0
            logging.info('add port: %d with password: %s' % (port, user.passwd))
            # TODO: check password change


def upload_load():
    with open('/proc/loadavg') as f:
        load = f.read()
    with open('/proc/uptime') as f:
        uptime = f.read().split()[0]
    api.post_load(load, uptime)


if __name__ == '__main__':
    api = MuAPI(URL, KEY, ID)
    ss_manager = SSManager(MANAGER_IP, MANAGER_PORT)

    count = dict()

    users = api.users
    state = ss_manager.state
    if users is None or state is None:
        logging.error('start fail, please check network!')
        exit(1)
    reset_manager()
    while True:
        # sleep
        sleep(UPDATE_TIME)
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
        # upload load
        upload_load()
