use std::net::SocketAddr;

use env_logger;

use dns::lab::LabClient;
use dns::check::{UdpChecker, TcpChecker};
use dns::types::Error;

async fn check_udp(address: SocketAddr, lab_client: &LabClient) -> Result<(), Error> {
    let mut udp_checker = UdpChecker::new(address, lab_client).await?;

    udp_checker.check_recursive().await?;
    udp_checker.check_authoritative().await?;
    udp_checker.check_mail().await?;
    udp_checker.check_subdomain().await?;    

    Ok(())
}

async fn check_tcp(address: SocketAddr, lab_client: &LabClient) -> Result<(), Error> {
    let mut tcp_checker = TcpChecker::new(address, lab_client).await?;

    tcp_checker.check_transfer().await?;

    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    env_logger::init();

    let lab_client = LabClient::new();

    let address = ([10, 52, 1, 1], 53).into();

    check_udp(address, &lab_client).await?;
    check_tcp(address, &lab_client).await?;

    Ok(())
}
