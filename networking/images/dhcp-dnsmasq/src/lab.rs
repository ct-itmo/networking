use std::env;

use log::info;

use crate::types::{Error, ErrorKind};

pub struct LabClient {
    chapter: String,
    user_id: String,
    client: reqwest::Client,
}

impl LabClient {
    pub fn new() -> Result<LabClient, Error> {
        let client = reqwest::Client::builder()
            .unix_socket("/var/run/quirck.sock")
            .build()?;

        Ok(LabClient {
            chapter: "dhcp".to_string(),
            user_id: env::var("USER_ID")
                .map_err(|_| ErrorKind::MissingVariable("USER_ID".to_string()))?,
            client,
        })
    }

    pub async fn submit(&self, task: &str) -> Result<(), Error> {
        let url = format!(
            "http://localhost/done?user_id={}&chapter={}&task={}",
            self.user_id, self.chapter, task
        );

        let response = self.client.post(&url).send().await?;

        let code = response.status().as_u16();
        let text = response.text().await?;

        if code != 200 {
            return Err(From::from(ErrorKind::Http(format!(
                "Server error: code {}, message {}",
                code, text
            ))));
        }

        info!("Server responded with code {} and message {}", code, text);

        Ok(())
    }
}
