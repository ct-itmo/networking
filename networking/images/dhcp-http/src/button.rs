use hyper::{Request, Response, StatusCode, Body, Method};

use crate::types::Error;
use crate::lab::LabClient;

pub struct Button {
    lab: LabClient,
    host: String
}

impl Button {
    pub fn new(host: &String) -> Button {
        Button {
            lab: LabClient::new(),
            host: host.to_string()
        }
    }

    pub async fn handle(&self, req: Request<Body>) -> Result<Response<Body>, Error> {
        let http_host = match req.headers().get("Host") {
            Some(value) => value.to_str(),
            None => return Ok(self.error(StatusCode::NOT_FOUND))
        };

        if http_host.is_err() || http_host.unwrap() != self.host {
            return Ok(self.error(StatusCode::NOT_FOUND));
        }

        if req.uri().path() != "/" {
            return Ok(self.error(StatusCode::NOT_FOUND));
        }

        match req.method() {
            &Method::GET => Ok(Response::new(Body::from(
                "<body><form method=post><button>Click me!</button></body>"
            ))),
            &Method::POST => {
                self.lab.submit().await?;
                Ok(Response::new(Body::from("Well done!")))
            },
            _ => Ok(self.error(StatusCode::METHOD_NOT_ALLOWED))
        }
    }

    fn error(&self, status: StatusCode) -> Response<Body> {
        let mut result = Response::default();
        *result.status_mut() = status;
        result
    }
}
