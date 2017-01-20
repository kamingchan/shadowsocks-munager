# shadowsocks-munager
兼容 Mu API 的 shadowsocks-server，通过调用 ss-manager 控制 ss-server，支持流量统计等一系列功能。

## 部署
1. 编译安装 Shadowsocks-libev，推荐使用[秋水逸冰的脚本](https://shadowsocks.be/4.html)
2. 参考 `ss-manager.sh` 的方式启动 ss-manager。
3. 复制 `config_example.py` 为 `config.py`，修改对应参数。
4. `python3 main.py` 运行脚本，在生产环境应该使用 supervisor 进行守护。

**暂时处于开发版，部分功能不可使用，不应该使用在生产环境中。**
