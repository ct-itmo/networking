#!/bin/bash

set -e

export INTERFACE=eth0

ip link set $INTERFACE promisc on

if [[ -v BOX_IP ]]; then
    echo "IP = $BOX_IP"
    ip addr add $BOX_IP/24 dev $INTERFACE
else
    echo "No IP"
fi
if [[ -v BOX_IP2 ]]; then
    echo "IP = $BOX_IP2"
    ip addr add $BOX_IP2/24 dev $INTERFACE
fi

if [[ -v BOX_GATEWAY ]]; then
    echo "GATEWAY = $BOX_GATEWAY"
    ip route add default via $BOX_GATEWAY dev eth0
fi

if [[ -v STARTUP_TIMEOUT ]]; then
    echo "Sleep for $STARTUP_TIMEOUT while startup"
    sleep $STARTUP_TIMEOUT
fi

mkdir /out

/app/firewall-checker &>> /out/check.log
