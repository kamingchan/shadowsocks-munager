from time import time

import psutil
import yaml
from tornado import gen
from tornado.ioloop import IOLoop, PeriodicCallback

from Munager.MuAPI import MuAPI
from Munager.SSManager import SSManager
from Munager.Utils import get_logger


class Munager:
    def __init__(self, config_path):
        # load yaml config
        with open(config_path) as f:
            self.config = yaml.load(f.read())

        # set logger
        self.logger = get_logger('Munager', self.config)

        self.logger.debug('load config from {}.'.format(config_path))
        self.logger.debug('config: {}'.format(self.config))

        # mix
        self.ioloop = IOLoop.current()
        self.mu_api = MuAPI(self.config)
        self.ss_manager = SSManager(self.config)
        self.logger.debug('Munager initializing.')

    @property
    @gen.coroutine
    def sys_status(self):
        wait_time = self.config.get('diff_time', 10)

        sent = psutil.net_io_counters().bytes_sent
        recv = psutil.net_io_counters().bytes_recv
        yield gen.sleep(wait_time)
        current_sent = psutil.net_io_counters().bytes_sent
        current_recv = psutil.net_io_counters().bytes_recv
        # change in to killo bytes
        sent_speed = (current_sent - sent) / wait_time * 8 / 1024
        recv_speed = (current_recv - recv) / wait_time * 8 / 1024
        cpu = psutil.cpu_percent()
        vir = psutil.virtual_memory().percent
        swp = psutil.swap_memory().percent
        upload = round(sent_speed, 2)
        download = round(recv_speed, 2)
        uptime = time() - psutil.boot_time()
        return dict(
            cpu=cpu,
            vir=vir,
            swp=swp,
            upload=upload,
            download=download,
            uptime=uptime,
        )

    @gen.coroutine
    def post_load(self):
        # cpu, vir, swp, upload, download, sent_speed, recv_speed = self.sys_status
        data = yield self.sys_status
        result = yield self.mu_api.post_load(data)
        self.logger.info('post system load return {}.'.format(result))

    @gen.coroutine
    def update_ss_manager(self):
        # get from MuAPI and ss-manager
        users = yield self.mu_api.get_users('port')
        state = self.ss_manager.state
        self.logger.info('get MuAPI and ss-manager succeed, now begin to check ports.')
        self.logger.debug('get state from ss-manager: {}.'.format(state))

        # remove port
        for port in state:
            if port not in users or not users.get(port).available:
                self.ss_manager.remove(port)
                self.logger.info('remove port: {}.'.format(port))

        # add port
        for port, user in users.items():
            user_id = user.id
            if user.available and port not in state:
                if self.ss_manager.add(
                        user_id=user_id,
                        port=user.port,
                        password=user.passwd,
                        method=user.method,
                ):
                    self.logger.info('add user at port: {}.'.format(user.port))

            if user.available and port in state:
                if user.passwd != state.get(port).get('password') or user.method != state.get(port).get('method'):
                    if self.ss_manager.remove(user.port) and self.ss_manager.add(
                            user_id=user_id,
                            port=user.port,
                            password=user.passwd,
                            method=user.method,
                    ):
                        self.logger.info('reset port {} due to method or password changed.'.format(user.port))
        # check finish
        self.logger.info('check ports finished.')

        # update online users count
        state_list = [x for _, x in state.items()]
        online_amount = len(list(filter(lambda x: x.get('throughput') > x.get('cursor'), state_list)))
        result = yield self.mu_api.post_online_user(online_amount)
        if result:
            self.logger.info('upload online user count: {}.'.format(online_amount))

    @gen.coroutine
    def upload_throughput(self):
        state = self.ss_manager.state
        for port, info in state.items():
            cursor = info.get('cursor')
            throughput = info.get('throughput')
            if throughput < cursor:
                self.logger.warning('error throughput, try fix.')
                self.ss_manager.set_cursor(port, throughput)
            elif throughput > cursor:
                dif = throughput - cursor
                user_id = info.get('user_id')
                result = yield self.mu_api.upload_throughput(user_id, dif)
                if result:
                    self.ss_manager.set_cursor(port, throughput)
                    self.logger.info('update traffic: {} for port: {}.'.format(dif, port))

    def run(self):
        # period task
        PeriodicCallback(
            callback=self.post_load,
            callback_time=self._to_msecond(self.config.get('post_load_period', 60)),
            io_loop=self.ioloop,
        ).start()
        PeriodicCallback(
            callback=self.update_ss_manager,
            callback_time=self._to_msecond(self.config.get('update_port_period', 60)),
            io_loop=self.ioloop,
        ).start()
        PeriodicCallback(
            callback=self.upload_throughput,
            callback_time=self._to_msecond(self.config.get('upload_throughput_period', 360)),
            io_loop=self.ioloop,
        ).start()
        # reset on start
        self.ioloop.run_sync(self.update_ss_manager)
        try:
            self.ioloop.start()
        except KeyboardInterrupt:
            print('Bye~')

    @staticmethod
    def _to_msecond(period):
        # s to ms
        return period * 1000