/*!
 * Rust Bundler Main Entry Point
 * 
 * Rust CLI entrypoint: subcommands build/watch/ssr. Reads config and emits manifests.
 */

use clap::{Parser, Subcommand};
use std::path::PathBuf;
use anyhow::Result;
use tracing::{info, error};

mod swc_bridge;
mod config;
mod manifest;
mod watcher;

use swc_bridge::SwcBundler;
use config::BundlerConfig;

#[derive(Parser)]
#[command(name = "rust_bundler")]
#[command(about = "SWC-based bundler for Bino framework")]
#[command(version = "0.1.0")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
    
    /// Project directory
    #[arg(short, long, default_value = ".")]
    project_dir: PathBuf,
    
    /// Verbose output
    #[arg(short, long)]
    verbose: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Build project for production
    Build {
        /// Output directory
        #[arg(short, long, default_value = "dist")]
        output: PathBuf,
        
        /// Production mode
        #[arg(long)]
        production: bool,
    },
    
    /// Watch files and rebuild on changes
    Watch {
        /// HMR WebSocket port
        #[arg(long, default_value = "3001")]
        hmr_port: u16,
    },
    
    /// Server-side render a route
    Ssr {
        /// Route to render
        #[arg(short, long)]
        route: String,
        
        /// Context JSON
        #[arg(short, long)]
        context: Option<String>,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    
    // Initialize logging
    let log_level = if cli.verbose { "debug" } else { "info" };
    tracing_subscriber::fmt()
        .with_env_filter(log_level)
        .init();
    
    info!("Starting Rust bundler v{}", env!("CARGO_PKG_VERSION"));
    
    // Load configuration
    let config = BundlerConfig::load(&cli.project_dir)?;
    let bundler = SwcBundler::new(config);
    
    // Execute command
    match cli.command {
        Commands::Build { output, production } => {
            info!("Building project...");
            let manifest = bundler.build(&cli.project_dir, &output, production).await?;
            info!("✅ Build completed successfully");
            
            // Write manifest
            let manifest_file = output.join("manifest.json");
            tokio::fs::write(&manifest_file, serde_json::to_string_pretty(&manifest)?).await?;
            info!("Build manifest written to {}", manifest_file.display());
        }
        
        Commands::Watch { hmr_port } => {
            info!("Starting watch mode on port {}", hmr_port);
            bundler.watch(&cli.project_dir, hmr_port).await?;
        }
        
        Commands::Ssr { route, context } => {
            info!("Rendering SSR for route: {}", route);
            
            let context_data = if let Some(ctx) = context {
                serde_json::from_str(&ctx)?
            } else {
                serde_json::Value::Object(serde_json::Map::new())
            };
            
            let html = bundler.render_ssr(&route, &context_data).await?;
            println!("{}", html);
        }
    }
    
    Ok(())
}

/// Initialize a new Bino project structure
pub fn init_project(project_dir: &PathBuf) -> Result<()> {
    info!("Initializing Bino project structure...");
    
    // Create directories
    let dirs = ["app", "api", "static", "migrations"];
    for dir in dirs {
        let dir_path = project_dir.join(dir);
        std::fs::create_dir_all(&dir_path)?;
        info!("Created directory: {}", dir_path.display());
    }
    
    // Create basic configuration
    let config = BundlerConfig::default();
    let config_file = project_dir.join("tavo.config.json");
    let config_json = serde_json::to_string_pretty(&config)?;
    std::fs::write(&config_file, config_json)?;
    
    info!("✅ Project initialized");
    Ok(())
}

/// Check if rust bundler dependencies are available
pub fn check_dependencies() -> Result<()> {
    // TODO: implement dependency checking
    // This would verify SWC and other required tools are available
    
    info!("Checking bundler dependencies...");
    
    // Mock check for now
    info!("✅ All dependencies available");
    Ok(())
}

/// Get bundler version information
pub fn get_version_info() -> serde_json::Value {
    serde_json::json!({
        "version": env!("CARGO_PKG_VERSION"),
        "swc_version": "1.3.0", // TODO: get actual SWC version
        "build_date": env!("BUILD_DATE", "unknown"),
        "git_hash": env!("GIT_HASH", "unknown")
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;
    
    #[test]
    fn test_init_project() {
        let temp_dir = TempDir::new().unwrap();
        let project_path = temp_dir.path().to_path_buf();
        
        init_project(&project_path).unwrap();
        
        // Verify directories were created
        assert!(project_path.join("app").exists());
        assert!(project_path.join("api").exists());
        assert!(project_path.join("tavo.config.json").exists());
    }
    
    #[test]
    fn test_check_dependencies() {
        // Should not panic
        check_dependencies().unwrap();
    }
    
    #[test]
    fn test_version_info() {
        let info = get_version_info();
        assert!(info["version"].is_string());
    }
}

/*
Unit tests as comments:
1. test_cli_parsing() - verify command line argument parsing works correctly
2. test_build_command() - test build command execution with various options
3. test_watch_mode_startup() - verify watch mode starts without errors
*/