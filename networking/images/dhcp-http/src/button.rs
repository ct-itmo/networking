use hyper::{Request, Response, StatusCode, Body, Method};

use crate::types::Error;
use crate::lab::LabClient;

pub struct Button {
    lab: LabClient
}

impl Button {
    pub fn new() -> Button {
        Button { lab: LabClient::new() }
    }

    pub async fn handle(&self, req: Request<Body>) -> Result<Response<Body>, Error> {
        match (req.method(), req.uri().path()) {
            (&Method::GET, "/") => Ok(Response::new(Body::from(
                "<body><form method=post><button>Click me!</button></body>"
            ))),

            (&Method::POST, "/") => {
                self.lab.submit().await?;
                
                Ok(Response::new(Body::from("Well done!")))
            }

            _ => {
                let mut not_found = Response::default();
                *not_found.status_mut() = StatusCode::NOT_FOUND;
                Ok(not_found)
            }
        }
    }
}
