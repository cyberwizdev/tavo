/*!
 * Bundler Configuration
 * 
 * Configuration loading and validation for the Rust bundler.
 */

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BundlerConfig {
    /// Entry points for bundling
    pub entry: EntryConfig,
    
    /// Output configuration
    pub output: OutputConfig,
    
    /// SWC compilation options
    pub swc: SwcConfig,
    
    /// Development server options
    pub dev: DevConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntryConfig {
    /// Client entry point
    pub client: String,
    
    /// Server entry point  
    pub server: String,
    
    /// Additional entry points
    #[serde(default)]
    pub additional: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutputConfig {
    /// Output directory
    pub dir: String,
    
    /// Asset filename pattern
    #[serde(default = "default_filename_pattern")]
    pub filename: String,
    
    /// Chunk filename pattern
    #[serde(default = "default_chunk_pattern")]
    pub chunk_filename: String,
    
    /// Public path for assets
    #[serde(default = "default_public_path")]
    pub public_path: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SwcConfig {
    /// Target ECMAScript version
    #[serde(default = "default_target")]
    pub target: String,
    
    /// Enable minification
    #[serde(default)]
    pub minify: bool,
    
    /// Generate source maps
    #[serde(default = "default_source_maps")]
    pub source_maps: bool,
    
    /// JSX configuration
    pub jsx: JsxConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsxConfig {
    /// JSX runtime ("automatic" or "classic")
    #[serde(default = "default_jsx_runtime")]
    pub runtime: String,
    
    /// Development mode for JSX
    #[serde(default)]
    pub development: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DevConfig {
    /// Development server port
    #[serde(default = "default_dev_port")]
    pub port: u16,
    
    /// HMR WebSocket port
    #[serde(default = "default_hmr_port")]
    pub hmr_port: u16,
    
    /// Enable hot module replacement
    #[serde(default = "default_hmr_enabled")]
    pub hmr: bool,
}

// Default value functions
fn default_filename_pattern() -> String {
    "[name].[hash].js".to_string()
}

fn default_chunk_pattern() -> String {
    "[name].[hash].chunk.js".to_string()
}

fn default_public_path() -> String {
    "/".to_string()
}

fn default_target() -> String {
    "es2020".to_string()
}

fn default_source_maps() -> bool {
    true
}

fn default_jsx_runtime() -> String {
    "automatic".to_string()
}

fn default_dev_port() -> u16 {
    3000
}

fn default_hmr_port() -> u16 {
    3001
}

fn default_hmr_enabled() -> bool {
    true
}

impl Default for BundlerConfig {
    fn default() -> Self {
        Self {
            entry: EntryConfig {
                client: "app/page.tsx".to_string(),
                server: "app/layout.tsx".to_string(),
                additional: HashMap::new(),
            },
            output: OutputConfig {
                dir: "dist".to_string(),
                filename: default_filename_pattern(),
                chunk_filename: default_chunk_pattern(),
                public_path: default_public_path(),
            },
            swc: SwcConfig {
                target: default_target(),
                minify: false,
                source_maps: default_source_maps(),
                jsx: JsxConfig {
                    runtime: default_jsx_runtime(),
                    development: true,
                },
            },
            dev: DevConfig {
                port: default_dev_port(),
                hmr_port: default_hmr_port(),
                hmr: default_hmr_enabled(),
            },
        }
    }
}

impl BundlerConfig {
    /// Load configuration from file or use defaults
    pub fn load(project_dir: &Path) -> Result<Self> {
        let config_file = project_dir.join("bino.config.json");
        
        if config_file.exists() {
            let content = std::fs::read_to_string(&config_file)
                .with_context(|| format!("Failed to read config file: {}", config_file.display()))?;
            
            let config: BundlerConfig = serde_json::from_str(&content)
                .with_context(|| "Failed to parse config file")?;
            
            info!("Loaded configuration from {}", config_file.display());
            Ok(config)
        } else {
            info!("Using default configuration");
            Ok(Self::default())
        }
    }
    
    /// Save configuration to file
    pub fn save(&self, project_dir: &Path) -> Result<()> {
        let config_file = project_dir.join("bino.config.json");
        let content = serde_json::to_string_pretty(self)?;
        
        std::fs::write(&config_file, content)
            .with_context(|| format!("Failed to write config file: {}", config_file.display()))?;
        
        info!("Configuration saved to {}", config_file.display());
        Ok(())
    }
    
    /// Validate configuration
    pub fn validate(&self) -> Result<()> {
        // Validate entry points exist (in a real project)
        // TODO: implement entry point validation
        
        // Validate target is supported
        let supported_targets = ["es5", "es2015", "es2017", "es2018", "es2019", "es2020", "es2021", "es2022"];
        if !supported_targets.contains(&self.swc.target.as_str()) {
            return Err(anyhow::anyhow!("Unsupported target: {}", self.swc.target));
        }
        
        // Validate ports
        if self.dev.port == self.dev.hmr_port {
            return Err(anyhow::anyhow!("Dev port and HMR port cannot be the same"));
        }
        
        Ok(())
    }
    
    /// Get SWC options for compilation
    pub fn get_swc_options(&self, production: bool) -> serde_json::Value {
        serde_json::json!({
            "jsc": {
                "parser": {
                    "syntax": "typescript",
                    "tsx": true,
                    "decorators": false,
                    "dynamicImport": true
                },
                "transform": {
                    "react": {
                        "runtime": self.swc.jsx.runtime,
                        "development": !production && self.swc.jsx.development
                    }
                },
                "target": self.swc.target,
                "minify": {
                    "compress": production && self.swc.minify,
                    "mangle": production && self.swc.minify
                }
            },
            "module": {
                "type": "commonjs"
            },
            "sourceMaps": self.swc.source_maps && !production
        })
    }
    
    /// Merge with another configuration (for overrides)
    pub fn merge(&mut self, other: &BundlerConfig) {
        // TODO: implement deep merge of configuration objects
        // For now, just replace top-level fields
        self.output.dir = other.output.dir.clone();
        self.swc.minify = other.swc.minify;
        self.dev.port = other.dev.port;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;
    
    #[test]
    fn test_default_config() {
        let config = BundlerConfig::default();
        assert_eq!(config.entry.client, "app/page.tsx");
        assert_eq!(config.swc.target, "es2020");
        assert_eq!(config.dev.port, 3000);
    }
    
    #[test]
    fn test_config_validation() {
        let mut config = BundlerConfig::default();
        assert!(config.validate().is_ok());
        
        // Test invalid target
        config.swc.target = "invalid".to_string();
        assert!(config.validate().is_err());
    }
    
    #[test]
    fn test_config_save_load() {
        let temp_dir = TempDir::new().unwrap();
        let project_path = temp_dir.path();
        
        let config = BundlerConfig::default();
        config.save(project_path).unwrap();
        
        let loaded_config = BundlerConfig::load(project_path).unwrap();
        assert_eq!(config.entry.client, loaded_config.entry.client);
    }
}

/*
Unit tests as comments:
1. test_config_merge() - verify configuration merging works correctly
2. test_swc_options_generation() - test SWC options are generated properly for prod/dev
3. test_config_validation_edge_cases() - verify validation catches all invalid configurations
*/