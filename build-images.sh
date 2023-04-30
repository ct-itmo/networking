#!/usr/bin/env bash

set -e

BASE="$(dirname "$(realpath "$BASH_SOURCE")")"

docker build -t ct-itmo/quirck-relay $BASE/quirck/quirck/box/relay
docker build -t ct-itmo/labs-networking-ping $BASE/networking/images/ping
docker build -t ct-itmo/labs-networking-dhcp-dnsmasq $BASE/networking/images/dhcp-dnsmasq
docker build -t ct-itmo/labs-networking-dhcp-http $BASE/networking/images/dhcp-http
docker build -t ct-itmo/labs-networking-dhcp-nsd $BASE/networking/images/dhcp-nsd
