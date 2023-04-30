use core::{fmt, result};
use std::error;
use std::ffi::OsString;
use std::fmt::Formatter;
use std::str::Utf8Error;
use std::num::ParseIntError;

use hyper::{Error as HyperError};
use hyper::http::{Error as HyperHTTPError};

#[derive(Debug)]
pub enum Error {
    Regular(ErrorKind),
    Utf(Utf8Error),
    OsUtf(OsString),
    ParseInt(ParseIntError),
    Hyper(HyperError),
    HyperHTTP(HyperHTTPError)
}

#[derive(Debug)]
pub enum ErrorKind {
    UnknownAddress(String),
    MissingVariable(String),
    // HTTP,
    // Pnet(String),
    // JsonLog(String),
    // Systemd(String),
    // CheckJob(String),
    Hyper(String)
}

/*impl From<AddrParseError> for Error {
    fn from(err: AddrParseError) -> Self {
        Error::Ip(err)
    }
}

impl From<Infallible> for Error {
    fn from(err: Infallible) -> Self {
        Error::Convert(err)
    }
}*/

impl From<OsString> for Error {
    fn from(str: OsString) -> Self {
        Error::OsUtf(str)
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

impl From<HyperError> for Error {
    fn from(err: HyperError) -> Self {
        Error::Hyper(err)
    }
}

impl From<HyperHTTPError> for Error {
    fn from(err: HyperHTTPError) -> Self {
        Error::HyperHTTP(err)
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
            Error::OsUtf(str) => {
                write!(f, "UTF conversion error for variable {:?}", str)
            }
            Error::Utf(err) => {
                write!(f, "UTF conversion error: {}", err)
            }
            Error::ParseInt(err) => {
                write!(f, "Integer parse error: {}", err)
            }
            Error::Hyper(err) => {
                write!(f, "HTTP client error: {}", err)
            }
            Error::HyperHTTP(err) => {
                write!(f, "HTTP request error: {}", err)
            }
        }
    }
}

impl error::Error for Error {}

pub type Result<T> = result::Result<T, Error>;
