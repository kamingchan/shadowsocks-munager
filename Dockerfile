FROM ubuntu:latest

ENV DEPENDENCIES git-core ca-certificates python3-dev python3-pip python3-setuptools python3-psutil net-tools
ENV BASEDIR /root/shadowsocks-munager

# Set up building environment
RUN apt-get update && apt-get install -y $DEPENDENCIES

# Get the latest shadowsocks-munager code, install
RUN git clone https://github.com/bazingaterry/shadowsocks-munager.git -b tun $BASEDIR
WORKDIR $BASEDIR
RUN pip3 install -r requirements.txt

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
WORKDIR $BASEDIR
CMD python3 run.py
