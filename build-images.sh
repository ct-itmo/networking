#!/usr/bin/env bash

BASE="$(dirname "$(realpath "$BASH_SOURCE")")"

docker build -t ct-itmo/quirck-relay $BASE/quirck/quirck/box/relay
docker build -t ct-itmo/labs-networking-ping $BASE/networking/images/ping
