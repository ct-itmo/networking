use ping::types::Error;
use ping::worker::Worker;

#[tokio::main]
async fn main() -> Result<(), Error> {
    env_logger::init();

    let worker = Worker::new()?;
    worker.run().await?;

    Ok(())
}
