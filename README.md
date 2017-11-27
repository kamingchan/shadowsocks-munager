# shadowsocks-munager

Yat another port of shadowsocks-mu.

## Deploy

### Install Docker & Docker Compose

```bash
curl -sSL get.docker.com | sh
curl -L https://github.com/docker/compose/releases/download/1.17.1/docker-compose-`uname -s`-`uname -m` > /usr/local/bin/docker-compose
chmod a+x /usr/local/bin/docker-compose
```

### Edit a `docker-compose.yml` file

```
version: '3.4'

services:
  redis:
    image: 'redis'
    restart: 'always'
    network_mode: 'host'

  ss-manager:
    image: 'bazingaterry/shadowsocks-docker'
    restart: 'always'
    network_mode: 'host'
    environment:
      - 'LISTEN=-s 0.0.0.0 -s ::'

  shadowmanager:
    image: 'bazingaterry/shadowsocks-munager'
    restart: 'always'
    stop_signal: 'SIGINT'
    network_mode: 'host'
    depends_on:
      - 'redis'
      - 'ss-manager'
    environment:
      - 'manager_host=127.0.0.1'
      - 'redis_host=127.0.0.1'
      - 'sspanel_url=https://api.example.com'
```

### Run it

```bash
docker-compose up -d
```

### Show logs

```bash
docker-compose logs
```

## Update images from Docker Hub

```bash
docker-compose pull
docker-compose kill
docker-compose up -d
```
