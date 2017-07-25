import logging

from tornado import gen
from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop, PeriodicCallback

from Munager.MuAPI import MuAPI
from Munager.SSManager import SSManager


class Munager:
    def __init__(self, config):
        self.config = config

        # set logger
        self.logger = logging.getLogger()

        # mix
        self.ioloop = IOLoop.current()
        self.mu_api = MuAPI(self.config)
        self.ss_manager = SSManager(self.config)
        self.logger.info('Munager initializing.')

        self.client = AsyncHTTPClient()

    @gen.coroutine
    def update_ss_manager(self):
        # get from MuAPI and ss-manager
        users = yield self.mu_api.get_users('port')
        state, _ = self.ss_manager.state
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
                        plugin=user.plugin,
                        plugin_opts=user.plugin_opts,
                ):
                    self.logger.info('add user at port: {}.'.format(user.port))

            if user.available and port in state:
                if user.passwd != state.get(port).get('password') or \
                                user.method != state.get(port).get('method') or \
                                user.plugin != state.get(port).get('plugin') or \
                                user.plugin_opts != state.get(port).get('plugin_opts'):
                    if self.ss_manager.remove(user.port) and self.ss_manager.add(
                            user_id=user_id,
                            port=user.port,
                            password=user.passwd,
                            method=user.method,
                            plugin=user.plugin,
                            plugin_opts=user.plugin_opts,
                    ):
                        self.logger.info('reset port {} due to method or password changed.'.format(user.port))
        # check finish
        self.logger.info('check ports finished.')

    @gen.coroutine
    def upload_throughput(self):
        state = self.ss_manager.state
        online_amount = 0
        for port, info in state.items():
            cursor = info.get('cursor')
            throughput = info.get('throughput')
            if throughput < cursor:
                online_amount += 1
                self.logger.warning('error throughput, try fix.')
                self.ss_manager.set_cursor(port, throughput)
            elif throughput > cursor:
                online_amount += 1
                dif = throughput - cursor
                user_id = info.get('user_id')
                result = yield self.mu_api.upload_throughput(user_id, dif)
                if result:
                    self.ss_manager.set_cursor(port, throughput)
                    self.logger.info('update traffic: {} for port: {}.'.format(dif, port))

        # update online users count
        result = yield self.mu_api.post_online_user(online_amount)
        if result:
            self.logger.info('upload online user count: {}.'.format(online_amount))

    @staticmethod
    def _to_msecond(period):
        # s to ms
        return period * 1000

    def run(self):
        # period task
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
        try:
            # Init task
            self.ioloop.run_sync(self.update_ss_manager)
            self.ioloop.start()
        except KeyboardInterrupt:
            del self.mu_api
            del self.ss_manager
            print('Bye~')
