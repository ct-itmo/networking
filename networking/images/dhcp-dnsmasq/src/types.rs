use core::{fmt, result};
use std::error;
use std::ffi::OsString;
use std::fmt::Formatter;
use std::num::ParseIntError;
use std::str::Utf8Error;

#[derive(Debug)]
pub enum Error {
    Regular(ErrorKind),
    Utf(Utf8Error),
    OsUtf(OsString),
    ParseInt(ParseIntError),
    Reqwest(reqwest::Error),
}

#[derive(Debug)]
pub enum ErrorKind {
    UnknownAddress(String),
    MissingVariable(String),
    MissingArguments(String),
    Http(String),
}

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

impl From<reqwest::Error> for Error {
    fn from(err: reqwest::Error) -> Self {
        Error::Reqwest(err)
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
            Error::Reqwest(err) => {
                write!(f, "HTTP client error: {}", err)
            }
        }
    }
}

impl error::Error for Error {}

pub type Result<T> = result::Result<T, Error>;
