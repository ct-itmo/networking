use std::env;

use async_std::task;
use env_logger;
use futures::try_join;
use log::info;
use pnet::datalink::NetworkInterface;

use ping::worker::Worker;
use ping::types::Error;

#[tokio::main]
async fn main() -> Result<(), Error> {
    env_logger::init();

    info!("Started");

    let interface_name = env::var("INTERFACE").unwrap_or("eth0".to_string());
    let student_ip = env::var("STUDENT_IP").unwrap();

    info!("Catching pings from {} on {}", student_ip, interface_name);

    let interfaces = pnet::datalink::interfaces();
    let interface = interfaces
        .into_iter()
        .find(|iface: &NetworkInterface| iface.name == interface_name)
        .ok_or(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            format!("interface {} not found", interface_name),
        ))?;

    let worker = Worker::new(interface);
    let task = task::spawn(worker.run());
    try_join!(task)?;

    Ok(())
}
