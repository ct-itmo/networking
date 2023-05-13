use std::collections::BTreeSet;
use std::net::{Ipv4Addr, Ipv6Addr, SocketAddr};
use std::str::FromStr;
use std::time::Duration;

use async_trait::async_trait;
use log::info;
use tokio::net::{UdpSocket, TcpStream};
use trust_dns_client::client::{AsyncClient, ClientHandle};
use trust_dns_client::op::DnsResponse;
use trust_dns_client::proto::iocompat::AsyncIoTokioAsStd;
use trust_dns_client::rr::rdata::MX;
use trust_dns_client::rr::{DNSClass, Name, RData, RecordType};
use trust_dns_client::tcp::TcpClientStream;
use trust_dns_client::udp::UdpClientStream;

use crate::lab::LabClient;
use crate::types::{Error, ErrorKind};

pub struct Query {
    name: Name,
    record_type: RecordType
}

impl Query {
    pub fn new(name: &str, record_type: RecordType) -> Result<Query, Error> {
        Ok(Query {
            name: Name::from_str(name)?,
            record_type
        })
    }

    pub async fn execute(&self, client: &mut AsyncClient) -> Result<DnsResponse, Error> {
        let query = client.query(self.name.clone(), DNSClass::IN, self.record_type);
        let response = query.await?;
        info!("{:?}\n{:#?}", response.queries(), response.answers());
        Ok(response)
    }
}

#[async_trait]
trait Test {
    async fn check(&self, client: &mut AsyncClient) -> Result<(), Error>;
}

pub struct FullMatchTest {
    query: Query,
    expected_answer: BTreeSet<RData>
}

impl FullMatchTest {
    pub fn new(query: Query, expected_answer: BTreeSet<RData>) -> FullMatchTest {
        FullMatchTest { query, expected_answer }
    }
}

#[async_trait]
impl Test for FullMatchTest {
    async fn check(&self, client: &mut AsyncClient) -> Result<(), Error> {
        let response = self.query.execute(client).await?;

        if response.answer_count() as u64 != self.expected_answer.len() as u64 {
            return Err(From::from(ErrorKind::WrongResponse("Wrong number of records".to_string())));
        }

        let actual_answer: BTreeSet<_> = response.answers().iter()
            .filter_map(|r| r.data())
            .cloned().collect();

        if actual_answer != self.expected_answer {
            return Err(From::from(ErrorKind::WrongResponse("Wrong records".to_string())));
        }
        
        Ok(())
    }
}

pub struct SoaTest {
    query: Query,
    expected_mname: Name,
    expected_rname: Name
}

impl SoaTest {
    pub fn new(domain_name: &str, expected_mname: &str, expected_rname: &str) -> Result<SoaTest, Error> {
        Ok(SoaTest { 
            query: Query::new(domain_name, RecordType::SOA)?,
            expected_mname: Name::from_str(expected_mname)?,
            expected_rname: Name::from_str(expected_rname)?
        })
    }
}

#[async_trait]
impl Test for SoaTest {
    async fn check(&self, client: &mut AsyncClient) -> Result<(), Error> {
        let response = self.query.execute(client).await?;

        if response.answer_count() != 1 {
            return Err(From::from(ErrorKind::WrongResponse("Wrong number of records".to_string())));
        }

        match response.answers()[0].data() {
            Some(RData::SOA(data)) => {
                if data.mname() != &self.expected_mname ||
                    data.rname() != &self.expected_rname {
                    return Err(From::from(ErrorKind::WrongResponse("Wrong record content".to_string())));
                }
            }
            _ => return Err(From::from(ErrorKind::WrongResponse("Wrong record type".to_string())))
        }
        
        Ok(())
    }
}

pub struct UdpChecker<'u> {
    udp_client: AsyncClient,
    lab_client: &'u LabClient
}

impl <'u> UdpChecker<'u> {
    pub async fn new(
        address: SocketAddr,
        lab_client: &'u LabClient
    ) -> Result<UdpChecker, Error> {
        let stream = UdpClientStream::<UdpSocket>::with_timeout(address, Duration::from_secs(2));
    
        let (udp_client, bg) = match AsyncClient::connect(stream).await {
            Ok(client) => client,
            Err(err) => {
                info!("Cannot connect to DNS: {}", err);
                return Err(From::from(err))
            }
        };

        tokio::spawn(bg);
    
        Ok(UdpChecker { udp_client, lab_client })
    }

    pub async fn check_recursive(&mut self) -> Result<(), Error> {
        let test1 = FullMatchTest::new(
            Query::new("example.com.", RecordType::A)?,
            BTreeSet::from([RData::A(Ipv4Addr::new(93, 184, 216, 34))])
        );
        test1.check(&mut self.udp_client).await?;

        let test2 = FullMatchTest::new(
            Query::new("itmo.ru.", RecordType::NS)?,
            BTreeSet::from([
                RData::NS(Name::from_str("ns.itmo.ru.")?),
                RData::NS(Name::from_str("ns2.itmo.ru.")?),
                RData::NS(Name::from_str("ns3.itmo.ru.")?),
                RData::NS(Name::from_str("ns5.itmo.ru.")?)
            ])
        );
        test2.check(&mut self.udp_client).await?;

        let test3 = FullMatchTest::new(
            Query::new("stanford.edu.", RecordType::AAAA)?,
            BTreeSet::from([
                RData::AAAA(Ipv6Addr::from_str("2607:f6d0:0:925a::ab43:d7c8").unwrap())
            ])
        );
        test3.check(&mut self.udp_client).await?;

        let test4 = FullMatchTest::new(
            Query::new("runnet.ru.", RecordType::A)?,
            BTreeSet::from([RData::A(Ipv4Addr::new(85, 142, 29, 26))])
        );
        test4.check(&mut self.udp_client).await?;

        let test5 = SoaTest::new(".", "a.root-servers.net.", "nstld.verisign-grs.com.")?;
        test5.check(&mut self.udp_client).await?;

        let test6 = FullMatchTest::new(
            Query::new("abacaba.ba.", RecordType::A)?,
            BTreeSet::new()
        );
        test6.check(&mut self.udp_client).await?;

        self.lab_client.submit("recursive").await?;
        Ok(())
    }

    pub async fn check_authoritative(&mut self) -> Result<(), Error> {
        let domain = std::env::var("DOMAIN")?;
        let ip4 = std::env::var("IP4")?;
        let ip6 = std::env::var("IP6")?;

        let test1 = FullMatchTest::new(
            Query::new(domain.as_str(), RecordType::A)?,
            BTreeSet::from([RData::A(Ipv4Addr::from_str(ip4.as_str()).unwrap())])
        );
        test1.check(&mut self.udp_client).await?;

        let test2 = FullMatchTest::new(
            Query::new(domain.as_str(), RecordType::AAAA)?,
            BTreeSet::from([RData::AAAA(Ipv6Addr::from_str(ip6.as_str()).unwrap())])
        );
        test2.check(&mut self.udp_client).await?;

        self.lab_client.submit("authoritative").await?;
        Ok(())
    }

    pub async fn check_mail(&mut self) -> Result<(), Error> {
        let domain = std::env::var("DOMAIN")?;

        let test = FullMatchTest::new(
            Query::new(domain.as_str(), RecordType::MX)?,
            BTreeSet::from([RData::MX(MX::new(10, Name::from_str("mx.example.org.")?))])
        );
        test.check(&mut self.udp_client).await?;

        self.lab_client.submit("mail").await?;
        Ok(())
    }

    pub async fn check_subdomain(&mut self) -> Result<(), Error> {
        let domain = std::env::var("DOMAIN")?;
        let ns_domain = format!("ns.{}", domain);
        
        let test1 = FullMatchTest::new(
            Query::new(ns_domain.as_str(), RecordType::A)?,
            BTreeSet::from([RData::A(Ipv4Addr::new(10, 52, 1, 1))])
        );
        test1.check(&mut self.udp_client).await?;

        let test2 = FullMatchTest::new(
            Query::new(domain.as_str(), RecordType::NS)?,
            BTreeSet::from([RData::NS(Name::from_str(ns_domain.as_str())?)]),
        );
        test2.check(&mut self.udp_client).await?;

        let test3 = SoaTest::new(
            domain.as_str(),
            format!("ns.{}.", domain).as_str(),
            format!("noreply.{}.", domain).as_str()
        )?;
        test3.check(&mut self.udp_client).await?;

        let subdomain = std::env::var("SUBDOMAIN")?;
        let ip6 = std::env::var("SUBIP6")?;

        let test4 = FullMatchTest::new(
            Query::new(subdomain.as_str(), RecordType::AAAA)?,
            BTreeSet::from([RData::AAAA(Ipv6Addr::from_str(ip6.as_str()).unwrap())])
        );
        test4.check(&mut self.udp_client).await?;

        self.lab_client.submit("subdomain").await?;
        Ok(())
    }
}

pub struct TcpChecker<'t> {
    tcp_client: AsyncClient,
    lab_client: &'t LabClient
}

impl <'t> TcpChecker<'t> {
    pub async fn new(
        address: SocketAddr,
        lab_client: &'t LabClient
    ) -> Result<TcpChecker, Error> {
        let (stream, sender) = TcpClientStream::<AsyncIoTokioAsStd<TcpStream>>::with_timeout(address, Duration::from_secs(2));
    
        let (tcp_client, bg) = match AsyncClient::new(stream, sender, None).await {
            Ok(client) => client,
            Err(err) => {
                info!("Cannot connect to DNS: {}", err);
                return Err(From::from(err))
            }
        };

        tokio::spawn(bg);
    
        Ok(TcpChecker { tcp_client, lab_client })
    }

    pub async fn check_transfer(&mut self) -> Result<(), Error> {
        let domain = format!("{}.", std::env::var("DOMAIN")?);
        let ns_domain = format!("ns.{}", domain);
        let ip4 = std::env::var("IP4")?;
        let ip6 = std::env::var("IP6")?;
        let subdomain = format!("{}.", std::env::var("SUBDOMAIN")?);
        let subdomain_ip6 = std::env::var("SUBIP6")?;

        let query = Query::new(domain.as_str(), RecordType::AXFR)?;
        let response = query.execute(&mut self.tcp_client).await?;

        let zone_length = response.answer_count() as usize;

        if zone_length < 2 {
            return Err(From::from(ErrorKind::WrongResponse("Invalid zone transfer".to_string())));
        }

        let first = response.answers().first().unwrap();
        let last = response.answers().last().unwrap();

        if first.data() != last.data() {
            return Err(From::from(ErrorKind::WrongResponse("Invalid zone transfer".to_string())));
        }

        match first.data() {
            Some(RData::SOA(data)) => {
                if data.mname().to_string() != ns_domain ||
                    data.rname().to_string() != format!("noreply.{}", domain) {
                    return Err(From::from(ErrorKind::WrongResponse("Wrong SOA record content".to_string())));
                }
            }
            _ => return Err(From::from(ErrorKind::WrongResponse("Wrong SOA record type".to_string())))
        }

        let records: BTreeSet<_> = response.answers()[1 .. zone_length - 1].iter()
            .filter(|r| r.data().is_some())
            .map(|r| (r.name().clone(), r.data().unwrap().clone()))
            .collect();

        let expected = BTreeSet::from([
            (Name::from_str(domain.as_str())?, RData::NS(Name::from_str(ns_domain.as_str())?)),
            (Name::from_str(domain.as_str())?, RData::A(Ipv4Addr::from_str(ip4.as_str()).unwrap())),
            (Name::from_str(domain.as_str())?, RData::AAAA(Ipv6Addr::from_str(ip6.as_str()).unwrap())),
            (Name::from_str(domain.as_str())?, RData::MX(MX::new(10, Name::from_str("mx.example.org.")?))),

            (Name::from_str(ns_domain.as_str())?, RData::A(Ipv4Addr::new(10, 52, 1, 1))),

            (Name::from_str(subdomain.as_str())?, RData::AAAA(Ipv6Addr::from_str(subdomain_ip6.as_str()).unwrap()))
        ]);

        if !records.is_superset(&expected) {
            return Err(From::from(ErrorKind::WrongResponse("Wrong records".to_string())));
        }

        self.lab_client.submit("transfer").await?;
        Ok(())
    }
}
