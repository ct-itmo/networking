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
use std::net::{Ipv4Addr, Ipv6Addr, IpAddr};

pub struct Worker {
    interface_name: String,
    src: String,
    client: LabClient,
    ping_received: bool,
}

impl Worker {
    pub fn new(interface_name: &String) -> Worker {
        Worker {
            interface_name: interface_name.to_string(),
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

        let interface = self.get_interface()?;

        let (_tx, mut rx) = match datalink::channel(&interface, config) {
            Ok(Ethernet(tx, rx)) => (tx, rx),
            Ok(_) => {
                return Err(From::from(
                    ErrorKind::Pnet(format!("Can't open a channel on <{}> interface", &interface.name))))
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

        let icmp = match IcmpPacket::new(ip.payload()) {
            Some(icmp) => icmp,
            None => return Ok(())
        };

        if icmp.get_icmp_type() != IcmpTypes::EchoRequest {
            return Ok(());
        }

        info!("Got ICMP echo request from {} to {}", ip.get_source(), ip.get_destination());

        if !self.is_incoming(IpAddr::V4(ip.get_destination()))? {
            return Ok(());
        }

        if self.src != "any" {
            let expected_src = self.src.parse::<Ipv4Addr>();
            if expected_src.is_err() || ip.get_source() != expected_src? {
                return Ok(());
            }
        }

        if !self.ping_received {
            info!("Valid request received, all following packets will be ignored");
            self.ping_received = true;
            self.client.submit().await?;
        }

        Ok(())
    }


    async fn process_icmpv6<'p>(&mut self, ip: &Ipv6Packet<'p>) -> Result<(), Error> {
        if ip.get_next_header() != IpNextHeaderProtocols::Icmpv6 {
            return Ok(())
        }

        let icmp = match Icmpv6Packet::new(ip.payload()) {
            Some(icmp) => icmp,
            None => return Ok(())
        };

        if icmp.get_icmpv6_type() != Icmpv6Types::EchoRequest {
            return Ok(());
        }

        info!("Got ICMPv6 echo request from {} to {}", ip.get_source(), ip.get_destination());

        if !self.is_incoming(IpAddr::V6(ip.get_destination()))? {
            return Ok(());
        }

        if self.src != "any" {
            let expected_src = self.src.parse::<Ipv6Addr>();
            if expected_src.is_err() || ip.get_source() != expected_src? {
                return Ok(());
            }
        }

        if !self.ping_received {
            info!("Valid request received, all following packets will be ignored");
            self.ping_received = true;
            self.client.submit().await?;
        }

        Ok(())
    }

    fn is_incoming(&self, ip: IpAddr) -> Result<bool, Error> {
        let interfaces = pnet::datalink::interfaces();
        let interface = interfaces
            .into_iter()
            .find(|iface: &NetworkInterface| iface.name == self.interface_name)
            .ok_or(std::io::Error::new(
                std::io::ErrorKind::NotFound,
                format!("interface {} not found", self.interface_name),
            ))?;

        Ok(interface.ips.iter().find(|&net| net.ip() == ip).is_some())
    }

    fn get_interface(&self) -> Result<NetworkInterface, Error> {
        let interfaces = pnet::datalink::interfaces();
        let interface = interfaces
            .into_iter()
            .find(|iface: &NetworkInterface| iface.name == self.interface_name)
            .ok_or(std::io::Error::new(
                std::io::ErrorKind::NotFound,
                format!("interface {} not found", self.interface_name),
            ))?;
        Ok(interface)
    }
}
