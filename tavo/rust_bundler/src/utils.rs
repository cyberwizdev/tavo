use anyhow::{Result, Context};
use std::path::{Path, PathBuf};
use std::fs;

pub fn resolve_import(import_path: &str, current_file: &Path) -> Result<PathBuf> {
    let current_dir = current_file.parent()
        .context("Failed to get parent directory")?;
    
    // Handle relative imports
    if import_path.starts_with("./") || import_path.starts_with("../") {
        let mut resolved = current_dir.join(import_path);
        
        // Try different extensions
        let extensions = ["", ".tsx", ".ts", ".jsx", ".js"];
        for ext in &extensions {
            let path_with_ext = if ext.is_empty() {
                resolved.clone()
            } else {
                resolved.with_extension(&ext[1..]) // Remove the dot
            };
            
            if path_with_ext.exists() {
                return Ok(path_with_ext);
            }
        }
        
        // Try as directory with index file
        for ext in &[".tsx", ".ts", ".jsx", ".js"] {
            let index_path = resolved.join(format!("index{}", ext));
            if index_path.exists() {
                return Ok(index_path);
            }
        }
        
        return Err(anyhow::anyhow!("Could not resolve import: {}", import_path));
    }
    
    // Handle node_modules imports (simplified - just return the import path)
    // In a real implementation, you'd resolve these from node_modules
    Ok(PathBuf::from(import_path))
}

pub fn read_file_content(path: &Path) -> Result<String> {
    fs::read_to_string(path)
        .with_context(|| format!("Failed to read file: {}", path.display()))
}

pub fn ensure_parent_dir(path: &Path) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("Failed to create directory: {}", parent.display()))?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::tempdir;
    
    #[test]
    fn test_resolve_relative_import() {
        let temp_dir = tempdir().unwrap();
        let current_file = temp_dir.path().join("src").join("main.tsx");
        let target_file = temp_dir.path().join("src").join("components").join("App.tsx");
        
        // Create the directory structure
        fs::create_dir_all(target_file.parent().unwrap()).unwrap();
        fs::write(&target_file, "export default function App() {}").unwrap();
        
        let resolved = resolve_import("./components/App", &current_file).unwrap();
        assert_eq!(resolved, target_file);
    }
}