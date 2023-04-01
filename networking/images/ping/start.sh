#!/bin/bash

set -e

export INTERFACE=eth0
export RUST_LOG=info
export RUST_BACKTRACE=full

ip link set $INTERFACE promisc on

if [[ -v BOX_IP ]]; then
    echo "IP = $BOX_IP"

    if [[ $BOX_IP == *:* ]]; then
        ip -6 addr add $BOX_IP/64 dev $INTERFACE
    else
        ip addr add $BOX_IP/24 dev $INTERFACE
    fi
else
    echo "No IP (only link-local)"
fi

if [[ -v MTU ]]; then
    echo "MTU = $MTU"
    nft -f - <<HERE
    table inet f_$INTERFACE {}
    delete table inet f_$INTERFACE
    table inet f_$INTERFACE {
        chain INPUT {
            type filter hook input priority 0;
            meta length > $MTU drop
        }
        chain OUTPUT {
            type filter hook output priority 0;
            meta length > $MTU drop
        }
    }
HERE
else
    echo "No MTU (set to system defaults)"
fi

exec /app/ping eth0
