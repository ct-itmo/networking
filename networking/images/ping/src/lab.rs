use crate::types::{Error, ErrorKind};
use std::str::from_utf8;

use hyper::{Body, Client, Request};
use hyper::body::to_bytes;
use hyperlocal::{UnixClientExt, Uri, UnixConnector};
use log::info;
use std::env;

pub struct LabClient {
    chapter: String,
    task: String,
    user_id: String,
    client: Client<UnixConnector>
}

impl LabClient {
    pub fn new() -> LabClient {
        LabClient { 
            chapter: env::var("CHAPTER").unwrap(),
            task: env::var("TASK").unwrap(),
            user_id: env::var("USER_ID").unwrap(),
            client: Client::unix() 
        }
    }

    pub async fn submit(&self) -> Result<(), Error> {
        let url: hyper::Uri = Uri::new(
            "/var/run/quirck.sock",
            &format!(
                "/done?user_id={}&chapter={}&task={}",
                self.user_id, self.chapter, self.task
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
