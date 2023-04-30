use crate::types::{Error, ErrorKind};
use std::str::from_utf8;

use hyper::{Body, Client, Request};
use hyper::body::to_bytes;
use hyperlocal::{UnixClientExt, Uri, UnixConnector};
use log::info;
use std::env;

pub struct LabClient {
    chapter: String,
    user_id: String,
    client: Client<UnixConnector>
}

impl LabClient {
    pub fn new() -> LabClient {
        LabClient { 
            chapter: "dhcp".to_string(),
            user_id: env::var("USER_ID").unwrap(),
            client: Client::unix() 
        }
    }

    pub async fn submit(&self, task: &str) -> Result<(), Error> {
        let url: hyper::Uri = Uri::new(
            "/var/run/quirck.sock",
            &format!(
                "/done?user_id={}&chapter={}&task={}",
                self.user_id, self.chapter, task
            )[..]
        ).into();

        let request = Request::builder()
            .method("POST")
            .uri(url)
            .body(Body::empty())?;

        let response = self.client.request(request).await?;

        let code = response.status().as_u16();

        let body = response.into_body();
        let bytes = to_bytes(body).await?;
        let text = from_utf8(&bytes)?;

        if code != 200 {
            return Err(From::from(
                ErrorKind::Hyper(format!("Server error: code {}, message {}", code, text))));
        }

        info!("Server responded with code {} and message {}", code, text);

        Ok(())
    }
}
