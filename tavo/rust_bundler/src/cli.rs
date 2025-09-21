use clap::Parser;
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "myssr")]
#[command(about = "A Rust-based SSR + Hydration compiler for React components using SWC")]
pub struct Args {
    /// Entry point file (e.g., src/App.tsx)
    #[arg(long, value_name = "FILE")]
    pub entry: PathBuf,
    
    /// Generate SSR HTML output
    #[arg(long)]
    pub ssr: bool,
    
    /// Generate hydration JavaScript bundle
    #[arg(long)]
    pub hydrate: bool,
    
    /// Output file path
    #[arg(long, short, value_name = "FILE")]
    pub out: Option<PathBuf>,
}