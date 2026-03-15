use axum::extract::State;
use axum::http::{HeaderMap, StatusCode};
use axum::response::{Html, IntoResponse, Response};
use log::error;

use crate::lab::LabClient;
use crate::types::Error;

#[derive(Clone)]
pub struct Button {
    lab: LabClient,
    host: String,
}

impl Button {
    pub fn new(host: &String) -> Result<Button, Error> {
        Ok(Button {
            lab: LabClient::new()?,
            host: host.to_string(),
        })
    }

    pub async fn get_handler(State(button): State<Button>, headers: HeaderMap) -> Response {
        if !button.check_host(&headers) {
            return (StatusCode::NOT_FOUND, "").into_response();
        }

        Html("<body><form method=post><button>Click me!</button></body>").into_response()
    }

    pub async fn post_handler(State(button): State<Button>, headers: HeaderMap) -> Response {
        if !button.check_host(&headers) {
            return (StatusCode::NOT_FOUND, "").into_response();
        }

        match button.lab.submit().await {
            Ok(_) => Html("Well done!").into_response(),
            Err(err) => {
                error!("Error reporting click: {}", err);
                (StatusCode::INTERNAL_SERVER_ERROR, "Error").into_response()
            }
        }
    }

    fn check_host(&self, headers: &HeaderMap) -> bool {
        headers
            .get("host")
            .and_then(|h| h.to_str().ok())
            .map(|h| h == self.host)
            .unwrap_or(false)
    }
}
