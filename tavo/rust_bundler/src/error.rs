use std::path::PathBuf;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum SSRError {
    #[error("File not found: {0}")]
    FileNotFound(PathBuf),

    #[error("Failed to read file {0}: {1}")]
    FileRead(PathBuf, std::io::Error),

    #[error("Parse error: {0}")]
    ParseError(String),

    #[error("Codegen error: {0}")]
    CodegenError(String),

    #[error("Invalid compile type: {0}")]
    InvalidCompileType(String),

    #[error("Invalid output format: {0}")]
    InvalidOutputFormat(String),

    #[error("Layout resolution error: {0}")]
    LayoutResolutionError(String),

    #[error("Rendering error: {0}")]
    RenderingError(String),

    #[error("JSON serialization error: {0}")]
    JsonError(#[from] serde_json::Error),
}