use clap::Parser;

#[derive(Parser, Debug)]
#[command(name = "ssr-bundler")]
#[command(about = "A Rust-based SSR bundler for TypeScript/JSX applications")]
pub struct Args {
    /// The route to render (e.g., /, /about, /blog/hello-world)
    #[arg(long)]
    pub route: String,

    /// Path to the app directory
    #[arg(long, default_value = "./app")]
    pub app_dir: String,

    /// Compilation type
    #[arg(long, default_value = "hydration")]
    #[arg(value_parser = ["hydration", "ssr"])]
    pub compile_type: String,

    /// Output format
    #[arg(long, default_value = "json")]
    #[arg(value_parser = ["json", "stdout"])]
    pub output: String,

    /// Enable code minification
    #[arg(long)]
    pub minify: bool,

    /// Generate source maps
    #[arg(long)]
    pub sourcemap: bool,

    /// Timeout in milliseconds for SSR execution
    #[arg(long, default_value = "120000")]
    pub timeout_ms: u64,

    /// Log level
    #[arg(long, default_value = "warn")]
    #[arg(value_parser = ["error", "warn", "info", "debug", "trace"])]
    pub log_level: String,
}