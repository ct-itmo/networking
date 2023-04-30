#!/bin/bash

set -e

export INTERFACE=eth0
export RUST_LOG=info
export RUST_BACKTRACE=full

sed -i 's/$DHCP4/'"$DHCP4"'/g' /etc/dnsmasq.conf
sed -i 's/$DHCP6/'"$DHCP6"'/g' /etc/dnsmasq.conf
sed -i 's/$DNS6/'"$DNS6"'/g' /etc/dnsmasq.conf
sed -i 's/$SLAAC/'"$SLAAC"'/g' /etc/dnsmasq.conf

ip addr add $ADDRESS4/24 dev eth0
ip -6 addr add $ADDRESS6_1/64 dev eth0
ip -6 addr add $ADDRESS6_2/64 dev eth0

exec dnsmasq -k
