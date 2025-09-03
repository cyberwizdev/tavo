use std::fmt;
use std::path::PathBuf;

#[derive(Debug)]
pub enum SSRError {
    // File system errors
    FileRead(PathBuf, std::io::Error),
    FileNotFound(PathBuf),
    InvalidPath(String),
    
    // Compilation errors
    ParseError(String),
    CodegenError(String),
    
    // Runtime errors
    JsRuntime(String),
    
    // Configuration errors
    InvalidCompileType(String),
    InvalidOutputFormat(String),
    InvalidRoute(String),
    InvalidOutput(String),
    
    // Serialization errors
    SerializationError(String),
    
    External(Box<dyn std::error::Error + Send + Sync>),
}

impl fmt::Display for SSRError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SSRError::FileRead(path, err) => {
                write!(f, "Failed to read file '{}': {}", path.display(), err)
            }
            SSRError::FileNotFound(path) => {
                write!(f, "File not found: {}", path.display())
            }
            SSRError::InvalidPath(msg) => {
                write!(f, "Invalid path: {}", msg)
            }
            SSRError::ParseError(msg) => {
                write!(f, "Parse error: {}", msg)
            }
            SSRError::CodegenError(msg) => {
                write!(f, "Code generation error: {}", msg)
            }
            SSRError::JsRuntime(msg) => {
                write!(f, "JavaScript runtime error: {}", msg)
            }
            SSRError::InvalidCompileType(typ) => {
                write!(f, "Invalid compile type '{}'. Valid options: ssr, hydration, static, debug", typ)
            }
            SSRError::InvalidOutputFormat(format) => {
                write!(f, "Invalid output format '{}'. Valid options: json, text, html", format)
            }
            SSRError::InvalidRoute(route) => {
                write!(f, "Invalid route '{}'. Routes must start with '/'", route)
            }
            SSRError::InvalidOutput(msg) => {
                write!(f, "Invalid output: {}", msg)
            }
            SSRError::SerializationError(msg) => {
                write!(f, "Serialization error: {}", msg)
            }
            SSRError::External(err) => {
                write!(f, "External error: {}", err)
            }
        }
    }
}

impl std::error::Error for SSRError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            SSRError::FileRead(_, err) => Some(err),
            SSRError::External(err) => Some(err.as_ref()),
            _ => None,
        }
    }
}

// Implement From traits for common error conversions
impl From<std::io::Error> for SSRError {
    fn from(err: std::io::Error) -> Self {
        SSRError::External(Box::new(err))
    }
}

impl From<serde_json::Error> for SSRError {
    fn from(err: serde_json::Error) -> Self {
        SSRError::SerializationError(err.to_string())
    }
}

impl From<regex::Error> for SSRError {
    fn from(err: regex::Error) -> Self {
        SSRError::ParseError(format!("Regex error: {}", err))
    }
}

// Helper functions for creating common errors
impl SSRError {
    pub fn file_not_found<P: Into<PathBuf>>(path: P) -> Self {
        SSRError::FileNotFound(path.into())
    }
    
    pub fn parse_error<S: Into<String>>(msg: S) -> Self {
        SSRError::ParseError(msg.into())
    }
    
    pub fn js_runtime_error<S: Into<String>>(msg: S) -> Self {
        SSRError::JsRuntime(msg.into())
    }
}

// Custom result type for convenience
pub type SSRResult<T> = Result<T, SSRError>;