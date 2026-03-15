use core::{fmt, result};
use std::env::VarError;
use std::error;
use std::ffi::OsString;
use std::fmt::Formatter;
use std::net::AddrParseError;
use std::num::ParseIntError;
use std::str::Utf8Error;

use hickory_client::ClientError;
use hickory_client::proto::ProtoError;

#[derive(Debug)]
pub enum Error {
    Regular(ErrorKind),
    Utf(Utf8Error),
    OsUtf(OsString),
    Environment(VarError),
    ParseInt(ParseIntError),
    Reqwest(reqwest::Error),
    ProtoError(ProtoError),
    DNSError(ClientError),
    AddrError(AddrParseError),
}

#[derive(Debug)]
pub enum ErrorKind {
    WrongResponse(String),
    Http(String),
    MissingVariable(String),
}

impl From<OsString> for Error {
    fn from(str: OsString) -> Self {
        Error::OsUtf(str)
    }
}

impl From<VarError> for Error {
    fn from(err: VarError) -> Self {
        Error::Environment(err)
    }
}

impl From<ErrorKind> for Error {
    fn from(kind: ErrorKind) -> Self {
        Error::Regular(kind)
    }
}

impl From<Utf8Error> for Error {
    fn from(err: Utf8Error) -> Self {
        Error::Utf(err)
    }
}

impl From<reqwest::Error> for Error {
    fn from(err: reqwest::Error) -> Self {
        Error::Reqwest(err)
    }
}

impl From<ProtoError> for Error {
    fn from(err: ProtoError) -> Self {
        Error::ProtoError(err)
    }
}

impl From<ClientError> for Error {
    fn from(err: ClientError) -> Self {
        Error::DNSError(err)
    }
}

impl From<AddrParseError> for Error {
    fn from(err: AddrParseError) -> Self {
        Error::AddrError(err)
    }
}

impl fmt::Display for ErrorKind {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(f, "error")
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut Formatter) -> fmt::Result {
        match self {
            Error::Regular(err) => {
                write!(f, "{}", err)
            }
            Error::Environment(err) => {
                write!(f, "No environment variable: {}", err)
            }
            Error::OsUtf(str) => {
                write!(f, "UTF conversion error for variable {:?}", str)
            }
            Error::Utf(err) => {
                write!(f, "UTF conversion error: {}", err)
            }
            Error::ParseInt(err) => {
                write!(f, "Integer parse error: {}", err)
            }
            Error::Reqwest(err) => {
                write!(f, "HTTP client error: {}", err)
            }
            Error::ProtoError(err) => {
                write!(f, "DNS error: {}", err)
            }
            Error::DNSError(err) => {
                write!(f, "DNS error: {}", err)
            }
            Error::AddrError(err) => {
                write!(f, "Address parse error: {}", err)
            }
        }
    }
}

impl error::Error for Error {}

pub type Result<T> = result::Result<T, Error>;
