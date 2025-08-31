/*!
 * Build Manifest Types
 * 
 * Data structures for build manifests and asset information.
 */

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BuildManifest {
    /// Client-side assets
    pub client: AssetInfo,
    
    /// Server-side assets
    pub server: AssetInfo,
    
    /// Route to asset mapping
    pub routes: HashMap<String, String>,
    
    /// Build timestamp
    pub timestamp: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssetInfo {
    /// Main entry file
    pub entry: String,
    
    /// All generated assets
    pub assets: Vec<String>,
    
    /// Code splitting chunks
    pub chunks: HashMap<String, ChunkInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChunkInfo {
    /// Chunk filename
    pub filename: String,
    
    /// Files included in this chunk
    pub files: Vec<String>,
    
    /// Chunk dependencies
    pub dependencies: Vec<String>,
}

impl BuildManifest {
    /// Create new empty manifest
    pub fn new() -> Self {
        Self {
            client: AssetInfo::new(),
            server: AssetInfo::new(),
            routes: HashMap::new(),
            timestamp: chrono::Utc::now().timestamp(),
        }
    }
    
    /// Add route mapping
    pub fn add_route(&mut self, route: String, asset: String) {
        self.routes.insert(route, asset);
    }
    
    /// Get asset for route
    pub fn get_route_asset(&self, route: &str) -> Option<&String> {
        self.routes.get(route)
    }
    
    /// Get all CSS assets
    pub fn get_css_assets(&self) -> Vec<&String> {
        self.client.assets
            .iter()
            .filter(|asset| asset.ends_with(".css"))
            .collect()
    }
    
    /// Get all JS assets
    pub fn get_js_assets(&self) -> Vec<&String> {
        self.client.assets
            .iter()
            .filter(|asset| asset.ends_with(".js"))
            .collect()
    }
}

impl AssetInfo {
    /// Create new empty asset info
    pub fn new() -> Self {
        Self {
            entry: String::new(),
            assets: Vec::new(),
            chunks: HashMap::new(),
        }
    }
    
    /// Add asset to the list
    pub fn add_asset(&mut self, asset: String) {
        if !self.assets.contains(&asset) {
            self.assets.push(asset);
        }
    }
    
    /// Add chunk information
    pub fn add_chunk(&mut self, name: String, chunk: ChunkInfo) {
        self.chunks.insert(name, chunk);
    }
    
    /// Get total asset size (would require file system access)
    pub fn get_total_size(&self) -> u64 {
        // TODO: implement actual size calculation
        0
    }
}

impl ChunkInfo {
    /// Create new chunk info
    pub fn new(filename: String) -> Self {
        Self {
            filename,
            files: Vec::new(),
            dependencies: Vec::new(),
        }
    }
    
    /// Add file to chunk
    pub fn add_file(&mut self, file: String) {
        if !self.files.contains(&file) {
            self.files.push(file);
        }
    }
    
    /// Add dependency
    pub fn add_dependency(&mut self, dep: String) {
        if !self.dependencies.contains(&dep) {
            self.dependencies.push(dep);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_build_manifest_creation() {
        let mut manifest = BuildManifest::new();
        manifest.add_route("/".to_string(), "page.js".to_string());
        
        assert_eq!(manifest.get_route_asset("/"), Some(&"page.js".to_string()));
    }
    
    #[test]
    fn test_asset_info() {
        let mut assets = AssetInfo::new();
        assets.add_asset("main.js".to_string());
        assets.add_asset("main.css".to_string());
        
        assert_eq!(assets.assets.len(), 2);
        assert!(assets.assets.contains(&"main.js".to_string()));
    }
    
    #[test]
    fn test_chunk_info() {
        let mut chunk = ChunkInfo::new("vendor.js".to_string());
        chunk.add_file("react.js".to_string());
        chunk.add_dependency("react".to_string());
        
        assert_eq!(chunk.files.len(), 1);
        assert_eq!(chunk.dependencies.len(), 1);
    }
}