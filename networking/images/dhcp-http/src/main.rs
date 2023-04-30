use std::env;

use env_logger;
use log::info;

use hyper::service::{make_service_fn, service_fn};
use hyper::Server;

use http::button::Button;
use http::types::Error;

#[tokio::main]
async fn main() -> Result<(), Error> {
    env_logger::init();

    info!("Started");

    let bind_address = env::var("BIND").unwrap();
    let host = env::var("HOST").unwrap();

    let addr = bind_address.parse()?;
    let button = std::sync::Arc::new(Button::new(&host));

    let make_svc = make_service_fn(move |_conn| {
        let button = button.clone();
        async {
            Ok::<_, Error>(service_fn(move |req| {
                let button = button.clone();
                async move { button.handle(req).await }
            }))
        }
    });

    let server = Server::try_bind(&addr)?.serve(make_svc);
    info!("Listening on {}", addr);
    server.await?;

    Ok(())
}
