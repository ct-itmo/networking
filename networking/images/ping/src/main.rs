use std::env;

use async_std::task;
use env_logger;
use futures::try_join;
use log::info;

use ping::worker::Worker;
use ping::types::Error;

#[tokio::main]
async fn main() -> Result<(), Error> {
    env_logger::init();

    info!("Started");

    let interface_name = env::var("INTERFACE").unwrap_or("eth0".to_string());
    let student_ip = env::var("STUDENT_IP").unwrap();

    info!("Catching pings from {} on {}", student_ip, interface_name);

    let worker = Worker::new(&interface_name);
    let task = task::spawn(worker.run());
    try_join!(task)?;

    Ok(())
}
