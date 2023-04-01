use crate::lab::LabClient;
use crate::types::{Error, ErrorKind};
use log::info;
use pnet::datalink;
use pnet::datalink::{NetworkInterface, Config};
use pnet::datalink::Channel::Ethernet;
use pnet::packet::ethernet::{EtherTypes, EthernetPacket};
use pnet::packet::Packet;
use pnet::packet::icmp::{IcmpPacket, IcmpTypes};
use pnet::packet::icmpv6::{Icmpv6Packet, Icmpv6Types};
use pnet::packet::ip::IpNextHeaderProtocols;
use pnet::packet::ipv4::Ipv4Packet;
use pnet::packet::ipv6::Ipv6Packet;
use std::env;
use std::net::{Ipv4Addr, Ipv6Addr};

pub struct Worker {
    interface: NetworkInterface,
    src: String,
    client: LabClient,
    ping_received: bool,
}

impl Worker {
    pub fn new(interface: NetworkInterface) -> Worker {
        Worker {
            interface,
            src: env::var("STUDENT_IP").unwrap(),
            ping_received: false,
            client: LabClient::new(),
        }
    }

    pub async fn run(mut self) -> Result<(), Error> {
        let config = Config {
            promiscuous: false,
            ..Default::default()
        };

        let (_tx, mut rx) = match datalink::channel(&self.interface, config) {
            Ok(Ethernet(tx, rx)) => (tx, rx),
            Ok(_) => {
                return Err(From::from(
                    ErrorKind::Pnet(format!("Can't open a channel on <{}> interface", &self.interface.name))))
            }
            Err(e) => {
                info!("{}", e);
                return Err(Error::Io(e));
            }
        };

        info!("Receiving pings");

        loop {
            match rx.next() {
                Ok(packet) => {
                    if let Some(frame) = EthernetPacket::new(packet) {
                        match frame.get_ethertype() {
                            EtherTypes::Ipv4 => {
                                if let Some(ip) = Ipv4Packet::new(frame.payload()) {
                                    self.process_icmpv4(&ip).await?;
                                }
                            }
                            EtherTypes::Ipv6 => {
                                if let Some(ip) = Ipv6Packet::new(frame.payload()) {
                                    self.process_icmpv6(&ip).await?;
                                }
                            }
                            _ => {}
                        }
                    }
                }
                Err(err) => {
                    return Err(Error::from(err))
                }
            }
        }
    }

    async fn process_icmpv4<'p>(&mut self, ip: &Ipv4Packet<'p>) -> Result<(), Error> {
        if ip.get_next_level_protocol() != IpNextHeaderProtocols::Icmp {
            return Ok(())
        }

        info!(
            "Got ICMP packet, src = {}, dst = {}",
            ip.get_source(),
            ip.get_destination()
        );

        if self.interface.ips.iter().find(|&net| net.ip() == ip.get_destination()).is_none() {
            return Ok(())
        }

        let expected_src = self.src.parse::<Ipv4Addr>();

        if self.src != "any" && (expected_src.is_err() || ip.get_source() != expected_src?) {
            return Ok(())
        }

        if let Some(icmp) = IcmpPacket::new(ip.payload()) {
            match (icmp.get_icmp_type(), self.ping_received) {
                (IcmpTypes::EchoRequest, false) => {
                    info!("Found echo request, will ignore all following pings");
                    self.ping_received = true;
                    self.client.submit().await?;
                }
                _ => {}
            }
        }
        Ok(())
    }


    async fn process_icmpv6<'p>(&mut self, ip: &Ipv6Packet<'p>) -> Result<(), Error> {
        if ip.get_next_header() != IpNextHeaderProtocols::Icmpv6 {
            return Ok(())
        }

        info!(
            "Got ICMPv6 packet, src = {}, dst = {}",
            ip.get_source(),
            ip.get_destination()
        );

        if self.interface.ips.iter().find(|&net| net.ip() == ip.get_destination()).is_none() {
            return Ok(())
        }

        let expected_src = self.src.parse::<Ipv6Addr>();

        if self.src != "any" && (expected_src.is_err() || ip.get_source() != expected_src?) {
            return Ok(())
        }

        if let Some(icmp) = Icmpv6Packet::new(ip.payload()) {
            match (icmp.get_icmpv6_type(), self.ping_received) {
                (Icmpv6Types::EchoRequest, false) => {
                    info!("Found echo request, will ignore all following pings");
                    self.ping_received = true;
                    self.client.submit().await?;
                }
                _ => {}
            }
        }
        Ok(())
    }
}
