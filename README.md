# shadowsocks-munager

兼容 Mu API 的 shadowsocks-server，通过调用 ss-manager 控制 ss-server，支持流量统计等一系列功能。

## 部署

### 编译安装 Shadowsocks-libev

推荐使用[秋水逸冰的脚本](https://shadowsocks.be/4.html)。

### 启动 ss-manager

在生产环境应该使用 supervisor 进行守护，可以参考 `shadowsocks.conf` 文件。默认监听 IPv4 和 IPv6，不支持 IPv6 的主机请自行取掉；使用 `--acl` 参数，建议启用，防止访问本机以及局域网资源。。

### 编辑 Mu API 配置

复制 `config_example.py` 为 `config.py`，修改对应参数。

- 参数 `FAST_OPEN`，不支持 TCP fast open 的内核请去掉。
- 参数 `PLUGIN` 和 `PLUGIN_OPTS` 启用混淆，有需要请到 [simple-obfs](https://github.com/shadowsocks/simple-obfs) 编译插件。

### 启动 Munager

运行 `python3 main.py` 运行脚本，在生产环境应该使用 supervisor 进行守护，可以参考 `shadowsocks.conf` 文件。

### 屏蔽百度高精度定位 API

<del>建议使用 hosts 文件屏蔽百度高精度定位 API。</del>（ss-server 并不会读取 hosts）

## 已知 Bug

暂未发现。
