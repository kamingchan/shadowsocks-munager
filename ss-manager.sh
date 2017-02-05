#!/bin/bash

### BEGIN INIT INFO
# Provides:          Shadowsocks-libev
# Required-Start:    $network $local_fs $remote_fs
# Required-Stop:     $network $local_fs $remote_fs
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Fast tunnel proxy that helps you bypass firewalls
# Description:       Start or stop the Shadowsocks-libev manager
### END INIT INFO

# Author: Teddysun <i@teddysun.com>

if [ -f /usr/local/bin/ss-manager ]; then
    DAEMON=/usr/local/bin/ss-manager
elif [ -f /usr/bin/ss-manager ]; then
    DAEMON=/usr/bin/ss-manager
fi
NAME=Shadowsocks-Manager
PID_DIR=/var/run
PID_FILE=$PID_DIR/ss-manager.pid
RET_VAL=0
SS_SERVER=/usr/local/bin/ss-server
ACL_FILE=/root/shadowsocks-munager/ss.acl

METHOD=rc4-md5
TIMEOUT=360

[ -x $DAEMON ] || exit 0

if [ ! -d $PID_DIR ]; then
    mkdir -p $PID_DIR
    if [ $? -ne 0 ]; then
        echo "Creating PID directory $PID_DIR failed"
        exit 1
    fi
fi

if [ ! -f $CONF ]; then
    echo "$NAME config file $CONF not found"
    exit 1
fi

check_running() {
    if [ -r $PID_FILE ]; then
        read PID < $PID_FILE
        if [ -d "/proc/$PID" ]; then
            return 0
        else
            rm -f $PID_FILE
            return 1
        fi
    else
        return 2
    fi
}

do_status() {
    check_running
    case $? in
        0)
        echo "$NAME (pid $PID) is running..."
        ;;
        1|2)
        echo "$NAME is stopped"
        RET_VAL=1
        ;;
    esac
}

do_start() {
    if check_running; then
        echo "$NAME (pid $PID) is already running..."
        return 0
    fi
    $DAEMON \
    --manager-address 127.0.0.1:8888 \
    --executable $SS_SERVER \
    -s :: -s 0.0.0.0 \
    -u \
    -m $METHOD \
    -t $TIMEOUT \
    -f $PID_FILE \
    --fast-open \
    --acl $ACL_FILE
    if check_running; then
        echo "Starting $NAME success"
    else
        echo "Starting $NAME failed"
        RET_VAL=1
    fi
}

do_stop() {
    if check_running; then
        kill -9 $PID
        rm -f $PID_FILE
        echo "Stopping $NAME success"
    else
        echo "$NAME is stopped"
        RET_VAL=1
    fi
}

do_restart() {
    do_stop
    do_start
}

case "$1" in
    start|stop|restart|status)
    do_$1
    ;;
    *)
    echo "Usage: $0 { start | stop | restart | status }"
    RET_VAL=1
    ;;
esac

exit $RET_VAL
