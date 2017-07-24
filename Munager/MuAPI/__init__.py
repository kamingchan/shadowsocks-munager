import json
from logging import getLogger
from urllib.parse import urljoin, urlencode

from tornado import gen
from tornado.httpclient import AsyncHTTPClient, HTTPRequest


class MuAPIError(Exception):
    pass


class User:
    def __init__(self, **entries):
        # for IDE hint
        self.id = None
        self.user_name = None
        self.passwd = None
        self.port = None
        self.method = None
        self.enable = None
        self.u = None
        self.d = None
        self.transfer_enable = None
        self.plugin = None
        self.plugin_opts = None
        self.__dict__.update(entries)
        # from Mu api
        # passwd: ss password
        # method: ss method

    @property
    def available(self):
        return self.u + self.d < self.transfer_enable and self.enable == 1


class MuAPI:
    def __init__(self, config):
        self.logger = getLogger()
        self.config = config
        self.url_base = self.config.get('sspanel_url')
        self.delay_sample = self.config.get('delay_sample')
        self.client = AsyncHTTPClient()

    def _get_request(self, path, query=dict(), method='GET', json_data=None, form_data=None):
        query_s = urlencode(query)
        url = urljoin(self.url_base, path) + '?' + query_s
        req_para = dict(
            url=url,
            method=method,
            use_gzip=True,
        )
        if json_data:
            req_para.update(
                body=json.dumps(json_data),
                headers={
                    'Content-Type': 'application/json; charset=utf-8',
                }
            )
        elif form_data:
            req_para.update(
                body=urlencode(form_data),
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
                }
            )

        return HTTPRequest(**req_para)

    @gen.coroutine
    def _make_fetch(self, _request):
        try:
            response = yield self.client.fetch(_request)
            content = response.body.decode('utf-8')
            cont_json = json.loads(content, encoding='utf-8')
            if cont_json.get('ret') != 1:
                return False
            else:
                return True
        except Exception as e:
            self.logger.exception(e)
            return False

    @gen.coroutine
    def get_users(self, key) -> dict:
        request = self._get_request('/mu/v2/users')
        response = yield self.client.fetch(request)
        content = response.body.decode('utf-8')
        cont_json = json.loads(content, encoding='utf-8')
        if cont_json.get('ret') != 1:
            raise MuAPIError(cont_json)
        ret = dict()
        for user in cont_json.get('data'):
            ret[user.get(key)] = User(**user)
        return ret

    @gen.coroutine
    def get_delay(self) -> list:
        request = self._get_request(
            path='/mu/v2/node/delay',
            query=dict(
                sample=self.delay_sample,
            ),
        )
        response = yield self.client.fetch(request)
        content = response.body.decode('utf-8')
        cont_json = json.loads(content, encoding='utf-8')
        if cont_json.get('ret') != 1:
            raise MuAPIError(cont_json)
        return cont_json.get('data', [])

    @gen.coroutine
    def post_delay_info(self, formdata):
        request = self._get_request(
            path='/mu/v2/node/delay_info',
            method='POST',
            form_data=formdata,
        )
        result = yield self._make_fetch(request)
        return result

    @gen.coroutine
    def post_load(self, formdata):
        request = self._get_request(
            path='/mu/v2/node/info',
            method='POST',
            form_data=formdata,
        )
        result = yield self._make_fetch(request)
        return result

    @gen.coroutine
    def post_online_user(self, amount):
        request = self._get_request(
            path='/mu/v2/node/online_count',
            method='POST',
            form_data={
                'count': amount,
            }
        )
        result = yield self._make_fetch(request)
        return result

    @gen.coroutine
    def upload_throughput(self, users) -> dict:
        """
        :param users: [{"id":1, "u":100, "d": 150}, ...]
        :return:
        """
        request = self._get_request('/mu/v2/users/traffic', method='POST', json_data=users)
        response = yield self.client.fetch(request)
        content = response.body.decode('utf-8')
        cont_json = json.loads(content, encoding='utf-8')
        if cont_json.get('ret') != 1:
            raise MuAPIError(cont_json)
        return cont_json.get('data')
