use std::env;

use axum::Router;
use axum::routing::{get, post};
use http::button::Button;
use http::types::{Error, ErrorKind};
use log::info;

#[tokio::main]
async fn main() -> Result<(), Error> {
    env_logger::init();

    info!("Started");

    let bind_address =
        env::var("BIND").map_err(|_| ErrorKind::MissingVariable("BIND".to_string()))?;
    let host = env::var("HOST").map_err(|_| ErrorKind::MissingVariable("HOST".to_string()))?;

    let button = Button::new(&host)?;

    let app = Router::new()
        .route("/", get(Button::get_handler))
        .route("/", post(Button::post_handler))
        .with_state(button);

    let listener = tokio::net::TcpListener::bind(&bind_address).await?;
    info!("Listening on {}", bind_address);

    axum::serve(listener, app).await?;

    Ok(())
}
