# shadowsocks-munager

~~兼容 Mu API 的 shadowsocks-server~~，新版已不支持原版 Mu API，通过调用 ss-manager 控制 ss-server，支持流量统计等一系列功能。

## 部署

### 编译安装 Shadowsocks-libev

推荐使用[秋水逸冰的脚本](https://shadowsocks.be/4.html)。

### 编辑 Mu API 配置

复制 `config_example.yml` 为 `config.yml`，修改对应参数。

- 参数 `FAST_OPEN`，不支持 TCP fast open 的内核请去掉。
- 参数 `PLUGIN` 和 `PLUGIN_OPTS` 启用混淆，有需要请到 [simple-obfs](https://github.com/shadowsocks/simple-obfs) 编译插件。

### 安装依赖

```bash
apt-get update -y
apt-get install -y gcc redis-server python3-dev python3-pip python3-setuptools python3-psutil
pip3 install -r requirements.txt
# install Node.js v8
curl -sL https://deb.nodesource.com/setup_8.x | sudo -E bash -
apt-get install -y nodejs
npm install -g pm2
pm2 startup
pm2 install pm2-logrotate
```

### 启动 ss-manager 与 Munager

运行 `python3 run.py --config-file=config/config.yml` 运行脚本，在生产环境应该使用 PM2 进行守护，可以参考 `pm2 start config/pm2.yml` 文件。

一切部署成功后 `pm2 save` 保存配置。

## 已知 Bug

暂未发现。
