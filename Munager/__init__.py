import json
import logging
from time import time

import numpy
import psutil
from tornado import gen
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.locks import Lock

from Munager.MuAPI import MuAPI
from Munager.SSManager import SSManager


class Munager:
    def __init__(self, config):
        self.config = config

        # get logger
        self.logger = logging.getLogger()

        # log config
        self.logger.debug('config: \n{}'.format(json.dumps(self.config, indent=2)))

        # mix
        self.ioloop = IOLoop.current()
        self.mu_api = MuAPI(self.config)
        self.ss_manager = SSManager(self.config)
        self.logger.debug('Munager initializing.')

        self.client = AsyncHTTPClient()

        self.ss_manager_lock = Lock()

    @property
    @gen.coroutine
    def sys_status(self):
        wait_time = self.config.get('diff_time', 10)
        test_time = self.config.get('test_time', 10)

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

        url = self.config.get('test_url')

        req_para = dict(
            url=url,
            method='HEAD',
            use_gzip=True,
        )
        request = HTTPRequest(**req_para)

        error_counter = 0
        delay = 0
        for _ in range(test_time):
            start = time()
            try:
                yield self.client.fetch(request)
            except Exception as e:
                self.logger.exception(e)
                error_counter += 1
            else:
                delay += (time() - start)
        # s to ms
        delay = delay / (test_time - error_counter) * 1000

        return dict(
            cpu=cpu,
            vir=vir,
            swp=swp,
            upload=upload,
            download=download,
            uptime=uptime,
            delay=delay,
        )

    def delay_info(self, delays):
        delays.remove(max(delays))
        delays.remove(min(delays))

        delay_min = min(delays)
        delay_max = max(delays)
        mean = numpy.mean(delays)
        standard_deviation = numpy.std(delays)
        return dict(
            min=delay_min,
            max=delay_max,
            mean=mean,
            standard_deviation=standard_deviation,
        )

    @gen.coroutine
    def post_load(self):
        # cpu, vir, swp, upload, download, sent_speed, recv_speed = self.sys_status
        data = yield self.sys_status
        result = yield self.mu_api.post_load(data)
        if result:
            self.logger.info('post system load finished.')

    @gen.coroutine
    def post_delay_info(self):
        delays = yield self.mu_api.get_delay()
        data = self.delay_info(delays)
        result = yield self.mu_api.post_delay_info(data)
        if result:
            self.logger.info('post delay info finished.')

    @gen.coroutine
    def update_ss_manager(self):
        with (yield self.ss_manager_lock.acquire()):
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
        with (yield self.ss_manager_lock.acquire()):
            port_state, user_id_state = self.ss_manager.state
            online_amount = 0
            post_data = list()
            for port, info in port_state.items():
                user_id = info.get('user_id')
                cursor = info.get('cursor')
                throughput = info.get('throughput')
                if throughput < cursor:
                    self.logger.warning('error throughput, try fix.')
                    online_amount += 1
                    post_data.append(dict(
                        id=user_id,
                        u=0,
                        d=throughput,
                    ))
                elif throughput > cursor:
                    online_amount += 1
                    dif = throughput - cursor
                    post_data.append(dict(
                        id=user_id,
                        u=0,
                        d=dif,
                    ))
            # upload to MuAPI
            users = yield self.mu_api.upload_throughput(post_data)
            for user_id, msg in users.items():
                if msg == 'ok':
                    # user_id type is str
                    user = user_id_state.get(user_id)
                    throughput = user['throughput']
                    self.ss_manager.set_cursor(user['port'], throughput)
                    self.logger.info('update traffic for user: {}.'.format(user_id))
                else:
                    self.logger.warning('fail to update traffic for user: {}.'.format(user_id))

        # update online users count
        result = yield self.mu_api.post_online_user(online_amount)
        if result:
            self.logger.info('upload online user count: {}.'.format(online_amount))

    @gen.coroutine
    def memory_leak_watcher(self):
        memory = psutil.virtual_memory().percent
        if memory > self.config.get('reset_memory_threshold', 95):
            self.logger.info('current memory is {}, now begin to reset ss-manager.'.format(memory))
            yield self.upload_throughput()
            self.ss_manager.clear()
            yield self.update_ss_manager()
            self.logger.info('current memory is {} after reset ss-manager.'.format(memory))
        else:
            self.logger.info('current memory is {}, need not to reset ss-manager.'.format(memory))

    @staticmethod
    def _to_msecond(period):
        # s to ms
        return period * 1000

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
        PeriodicCallback(
            callback=self.post_delay_info,
            callback_time=self._to_msecond(self.config.get('post_delay_standard_period', 1296)),
            io_loop=self.ioloop,
        ).start()
        PeriodicCallback(
            callback=self.memory_leak_watcher,
            callback_time=self._to_msecond(self.config.get('memory_watcher_period', 600)),
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
