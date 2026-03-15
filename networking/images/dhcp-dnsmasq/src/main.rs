use std::env;

use dhcp::lab::LabClient;
use dhcp::types::{Error, ErrorKind};
use log::info;

#[tokio::main]
async fn main() -> Result<(), Error> {
    env_logger::init();

    let client = &LabClient::new()?;

    let args: Vec<String> = env::args().collect();
    if args.len() < 4 || args.len() > 5 {
        return Err(Error::from(ErrorKind::MissingArguments(
            "Expected 3 or 4 arguments, see man dnsmasq for usage".to_string(),
        )));
    }

    let action = &args[1];

    if action != "add" {
        info!("unhandled action for dhcp-script: {}", action);
        return Ok(());
    }

    let address = &args[3];

    info!("Assigned address {}", address);

    if address.contains('.') {
        client.submit("ip4").await?;
    } else if address.contains(':') {
        client.submit("ip6").await?;
    } else {
        return Err(Error::from(ErrorKind::UnknownAddress(format!(
            "Cannot parse address: {}",
            address
        ))));
    }

    Ok(())
}
