#!/bin/bash

set -e

sed -i 's/$DOMAIN/'"$DOMAIN"'/g' /etc/nsd.conf
sed -i 's/$HOSTIP/'"$HOSTIP"'/g' /etc/nsd.conf
sed -i 's/$DOMAIN/'"$DOMAIN"'/g' /etc/zone
sed -i 's/$HOSTIP/'"$HOSTIP"'/g' /etc/zone
sed -i 's/$AAAAIP/'"$AAAAIP"'/g' /etc/zone

ip -6 addr add $HOSTIP/64 dev eth0

sleep 1

exec nsd -d -c /etc/nsd.conf
