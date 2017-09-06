import os
import signal
import subprocess
from logging import getLogger

import psutil


class SNIProxy:
    def __init__(self, config):
        self.config = config
        self.logger = getLogger()
        self.pid_file = self.config.get('sniproxy_pid_file', '/tmp/sniproxy.pid')
        self.conf_file = self.config.get('sniproxy_conf_file', '/etc/sniproxy.conf')
        self._ports = dict()
        self.logger.info('SNIProxy initializing.')

    @property
    def configuration(self):
        TEMPLATE = '''
pidfile %s

error_log {
syslog daemon
priority notice
}

listener 0.0.0.0:80 {
protocol http
table http
fallback 23.50.93.70:80 # www.apple.com
}

listener 0.0.0.0:443 {
protocol tls
table tls
fallback 23.50.93.70:443 # www.apple.com
}

table http {
%s
}

table tls {
%s
}
'''
        port_list = '\n'.join(map(lambda port, domain: '%s 127.0.0.1:%s' % (domain, port), self._ports.items()))
        return TEMPLATE % (self.pid_file, port_list, port_list)

    def _write_configuration_file(self):
        with open(self.conf_file, 'wt') as f:
            f.write(self.configuration)
        self.logger.info('write SNIProxy configuration file succeed.')

    def _reload(self):
        if self.is_running:
            os.kill(self._pid, signal.SIGHUP)
            self.logger.info('send SIGHUP to SNIProxy.')
        else:
            self._run()

    @property
    def _pid(self):
        with open(self.pid_file, 'rt') as f:
            return int(f.read())

    @property
    def is_running(self):
        try:
            psutil.Process(self._pid)
            return True
        except Exception:
            return False

    @property
    def state(self):
        return self._ports

    def _run(self):
        return subprocess.call(['sniproxy', '-c', self.conf_file]) == 0

    def add(self, port, password):
        self._ports[port] = '{port}.{password}'.format(port=port, password=password)
        self._write_configuration_file()
        self._reload()
        self.logger.info('add port: {} to SNIProxy.'.format(port))

    def remove(self, port):
        del self._ports[port]
        self._write_configuration_file()
        self._reload()
        self.logger.info('remove port: {} from SNIProxy.'.format(port))
