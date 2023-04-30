FROM debian:11-slim
RUN apt-get update -q && apt-get install -qy --no-install-recommends dhcpcd5 iproute2 tcpdump net-tools iputils-ping
COPY start.sh /start.sh
COPY dhcpcd.conf /etc/dhcpcd.conf

CMD ["/start.sh"]
