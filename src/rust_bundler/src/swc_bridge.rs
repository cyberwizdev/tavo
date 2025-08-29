/*!
 * SWC Bridge Implementation
 * 
 * Encapsulate calling SWC libraries to compile client and server bundles, produce manifest mapping routes to assets.
 */

use anyhow::{Result, Context};
use serde_json::Value;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use swc_core::common::{SourceMap, GLOBALS};
use swc_core::ecma::parser::{lexer::Lexer, Parser, StringInput, Syntax, TsConfig};
use swc_core::ecma::transforms::base::resolver;
use swc_core::ecma::visit::FoldWith;
use tracing::{info, debug, error};

use crate::config::BundlerConfig;
use crate::manifest::{BuildManifest, AssetInfo};

pub struct SwcBundler {
    config: BundlerConfig,
    source_map: SourceMap,
}

impl SwcBundler {
    /// Create new SWC bundler instance
    pub fn new(config: BundlerConfig) -> Self {
        Self {
            config,
            source_map: SourceMap::default(),
        }
    }
    
    /// Build project for production
    pub async fn build(
        &self,
        project_dir: &Path,
        output_dir: &Path,
        production: bool,
    ) -> Result<BuildManifest> {
        info!("Starting SWC build process...");
        
        // Create output directory
        tokio::fs::create_dir_all(output_dir).await?;
        
        // Build client bundle
        let client_assets = self.build_client_bundle(project_dir, output_dir, production).await?;
        
        // Build server bundle
        let server_assets = self.build_server_bundle(project_dir, output_dir, production).await?;
        
        // Discover routes
        let routes = self.discover_routes(project_dir).await?;
        
        // Create build manifest
        let manifest = BuildManifest {
            client: client_assets,
            server: server_assets,
            routes,
            timestamp: chrono::Utc::now().timestamp(),
        };
        
        info!("✅ SWC build completed");
        Ok(manifest)
    }
    
    /// Start watch mode for development
    pub async fn watch(&self, project_dir: &Path, hmr_port: u16) -> Result<()> {
        info!("Starting SWC watch mode...");
        
        // TODO: implement file watching and incremental compilation
        // This would use notify crate to watch for file changes
        // and trigger selective rebuilds
        
        // Mock implementation
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
            debug!("Watching for changes...");
        }
    }
    
    /// Render route server-side
    pub async fn render_ssr(&self, route: &str, context: &Value) -> Result<String> {
        info!("Rendering SSR for route: {}", route);
        
        // TODO: implement actual SSR rendering
        // This would:
        // 1. Load the server bundle
        // 2. Execute React rendering for the route
        // 3. Return HTML string
        
        // Mock implementation
        let html = format!(
            r#"<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Tavo App - {}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
    <div id="root">
        <h1>Route: {}</h1>
        <p>Server-side rendered content</p>
    </div>
    <script>window.__TAVO_CONTEXT__ = {};</script>
</body>
</html>"#,
            route, route, context
        );
        
        Ok(html)
    }
    
    /// Build client-side bundle
    async fn build_client_bundle(
        &self,
        project_dir: &Path,
        output_dir: &Path,
        production: bool,
    ) -> Result<AssetInfo> {
        info!("Building client bundle...");
        
        let entry_file = project_dir.join("app").join("page.tsx");
        if !entry_file.exists() {
            return Err(anyhow::anyhow!("Client entry file not found: {}", entry_file.display()));
        }
        
        // Compile TypeScript/React to JavaScript
        let compiled_js = self.compile_typescript(&entry_file).await?;
        
        // Write client bundle
        let client_file = output_dir.join("client.js");
        tokio::fs::write(&client_file, compiled_js).await?;
        
        // TODO: implement CSS extraction and bundling
        let css_content = "/* Generated CSS */\nbody { margin: 0; font-family: system-ui; }";
        let css_file = output_dir.join("client.css");
        tokio::fs::write(&css_file, css_content).await?;
        
        Ok(AssetInfo {
            entry: "client.js".to_string(),
            assets: vec!["client.js".to_string(), "client.css".to_string()],
            chunks: HashMap::new(),
        })
    }
    
    /// Build server-side bundle
    async fn build_server_bundle(
        &self,
        project_dir: &Path,
        output_dir: &Path,
        production: bool,
    ) -> Result<AssetInfo> {
        info!("Building server bundle...");
        
        let layout_file = project_dir.join("app").join("layout.tsx");
        if !layout_file.exists() {
            return Err(anyhow::anyhow!("Server entry file not found: {}", layout_file.display()));
        }
        
        // Compile for server-side rendering
        let compiled_js = self.compile_typescript(&layout_file).await?;
        
        // Write server bundle
        let server_file = output_dir.join("server.js");
        tokio::fs::write(&server_file, compiled_js).await?;
        
        Ok(AssetInfo {
            entry: "server.js".to_string(),
            assets: vec!["server.js".to_string()],
            chunks: HashMap::new(),
        })
    }
    
    /// Compile TypeScript file using SWC
    async fn compile_typescript(&self, file_path: &Path) -> Result<String> {
        debug!("Compiling TypeScript file: {}", file_path.display());
        
        // Read source file
        let source_code = tokio::fs::read_to_string(file_path).await
            .with_context(|| format!("Failed to read file: {}", file_path.display()))?;
        
        // TODO: implement actual SWC compilation
        // This would use SWC to parse and transform TypeScript/React code
        
        GLOBALS.set(&Default::default(), || {
            // Mock compilation for now
            let compiled = format!(
                r#"// Compiled from {}
const React = require('react');

function Component() {{
    return React.createElement('div', null, 'Hello from Tavo!');
}}

module.exports = Component;
"#,
                file_path.display()
            );
            
            Ok(compiled)
        })
    }
    
    /// Discover routes from app directory
    async fn discover_routes(&self, project_dir: &Path) -> Result<HashMap<String, String>> {
        let app_dir = project_dir.join("app");
        let mut routes = HashMap::new();
        
        if !app_dir.exists() {
            return Ok(routes);
        }
        
        // Find page.tsx files
        let mut entries = tokio::fs::read_dir(&app_dir).await?;
        
        while let Some(entry) = entries.next_entry().await? {
            let path = entry.path();
            
            if path.is_file() && path.file_name().unwrap_or_default() == "page.tsx" {
                // Convert file path to route
                let route_path = self.file_path_to_route(&path, &app_dir)?;
                let asset_name = format!("{}.js", path.file_stem().unwrap().to_string_lossy());
                
                routes.insert(route_path, asset_name);
            }
        }
        
        // Add root route if not present
        if !routes.contains_key("/") {
            routes.insert("/".to_string(), "page.js".to_string());
        }
        
        info!("Discovered {} routes", routes.len());
        Ok(routes)
    }
    
    /// Convert file path to route path
    fn file_path_to_route(&self, file_path: &Path, base_dir: &Path) -> Result<String> {
        let relative_path = file_path.strip_prefix(base_dir)?;
        let mut route_parts = Vec::new();
        
        for component in relative_path.components() {
            let part = component.as_os_str().to_string_lossy();
            
            // Skip page.tsx filename
            if part == "page.tsx" {
                continue;
            }
            
            // Handle dynamic routes [param]
            if part.starts_with('[') && part.ends_with(']') {
                let param_name = &part[1..part.len()-1];
                route_parts.push(format!("{{{}}}", param_name));
            } else {
                route_parts.push(part.to_string());
            }
        }
        
        let route = if route_parts.is_empty() {
            "/".to_string()
        } else {
            format!("/{}", route_parts.join("/"))
        };
        
        Ok(route)
    }
}

/// Initialize SWC with default configuration
fn init_swc() -> Result<()> {
    // TODO: implement SWC initialization
    // This would set up SWC with appropriate transforms for React/TypeScript
    
    info!("SWC initialized");
    Ok(())
}

/// Get SWC compilation options
fn get_swc_options(production: bool) -> serde_json::Value {
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
                    "runtime": "automatic",
                    "development": !production
                }
            },
            "target": "es2020",
            "minify": {
                "compress": production,
                "mangle": production
            }
        },
        "module": {
            "type": "commonjs"
        },
        "sourceMaps": !production
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;
    
    #[tokio::test]
    async fn test_bundler_creation() {
        let config = BundlerConfig::default();
        let bundler = SwcBundler::new(config);
        
        // Should not panic
        assert!(true);
    }
    
    #[test]
    fn test_file_path_to_route() {
        let config = BundlerConfig::default();
        let bundler = SwcBundler::new(config);
        
        let base_dir = Path::new("app");
        let file_path = Path::new("app/users/page.tsx");
        
        let route = bundler.file_path_to_route(file_path, base_dir).unwrap();
        assert_eq!(route, "/users");
    }
    
    #[test]
    fn test_swc_options() {
        let options = get_swc_options(true);
        assert!(options["jsc"]["minify"]["compress"].as_bool().unwrap());
        
        let dev_options = get_swc_options(false);
        assert!(!dev_options["jsc"]["minify"]["compress"].as_bool().unwrap());
    }
}

/*
Unit tests as comments:
1. test_compile_typescript() - verify TypeScript compilation produces valid JavaScript
2. test_discover_routes() - test route discovery from file system
3. test_build_manifest_generation() - verify build manifest contains correct asset mappings
*/