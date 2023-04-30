use std::env;

use env_logger;
use log::info;

use dhcp::lab::LabClient;
use dhcp::types::{Error, ErrorKind};

#[tokio::main]
async fn main() -> Result<(), Error> {
    env_logger::init();

    let client = &LabClient::new();

    let args: Vec<String> = env::args().collect();

    let action = &args[1];

    if action != "add" {
        info!("unhandled action for dhcp-script: {}", action);
        return Ok(())
    }

    let address = &args[3];

    info!("Assigned address {}", address);

    if address.contains('.') {
        client.submit("ip4").await?;
    } else if address.contains(':') {
        client.submit("ip6").await?;
    } else {
        return Err(Error::from(ErrorKind::UnknownAddress(format!("Cannot parse address: {}", address))))
    }

    Ok(())
}
