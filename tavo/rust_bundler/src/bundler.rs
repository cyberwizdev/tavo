use anyhow::{Result, Context};
use std::path::{Path, PathBuf};
use std::collections::{HashMap, HashSet};
use swc_common::{SourceMap, sync::Lrc};
use swc_ecma_ast::*;

use crate::utils::{resolve_import, read_file_content};
use crate::compiler::Compiler;

pub struct Bundle {
    pub modules: HashMap<String, String>,
    pub entry_point: String,
}

pub struct Bundler {
    source_map: Lrc<SourceMap>,
    compiler: Compiler,
}

impl Bundler {
    pub fn new(source_map: Lrc<SourceMap>) -> Result<Self> {
        Ok(Self {
            source_map,
            compiler: Compiler::new()?,
        })
    }
    
    pub async fn bundle_for_ssr(&mut self, entry: &Path) -> Result<Bundle> {
        let mut modules = HashMap::new();
        let mut visited = HashSet::new();
        
        self.collect_dependencies(entry, &mut modules, &mut visited).await?;
        
        Ok(Bundle {
            modules,
            entry_point: entry.to_string_lossy().to_string(),
        })
    }
    
    pub async fn bundle_for_hydration(&mut self, entry: &Path) -> Result<Bundle> {
        let mut modules = HashMap::new();
        let mut visited = HashSet::new();
        
        // Add hydration wrapper
        let hydration_code = self.generate_hydration_wrapper(entry)?;
        modules.insert("__hydration_entry__".to_string(), hydration_code);
        
        self.collect_dependencies(entry, &mut modules, &mut visited).await?;
        
        Ok(Bundle {
            modules,
            entry_point: "__hydration_entry__".to_string(),
        })
    }
    
    async fn collect_dependencies(
        &mut self,
        file_path: &Path,
        modules: &mut HashMap<String, String>,
        visited: &mut HashSet<PathBuf>,
    ) -> Result<()> {
        let absolute_path = file_path.canonicalize()
            .context("Failed to canonicalize path")?;
        
        if visited.contains(&absolute_path) {
            return Ok(());
        }
        visited.insert(absolute_path.clone());
        
        let content = read_file_content(&absolute_path)?;
        let module = self.compiler.parse_tsx(&content, &absolute_path.to_string_lossy())?;
        
        // Extract imports
        let imports = self.extract_imports(&module);
        
        // Transform the module
        let transformed = self.compiler.transform_tsx(module)?;
        let code = self.compiler.generate_code(&transformed)?;
        
        modules.insert(absolute_path.to_string_lossy().to_string(), code);
        
        // Recursively process imports
        for import_path in imports {
            if let Ok(resolved_path) = resolve_import(&import_path, &absolute_path) {
                self.collect_dependencies(&resolved_path, modules, visited).await?;
            }
        }
        
        Ok(())
    }
    
    fn extract_imports(&self, module: &Module) -> Vec<String> {
        let mut imports = Vec::new();
        
        for item in &module.body {
            match item {
                ModuleItem::ModuleDecl(ModuleDecl::Import(import_decl)) => {
                    imports.push(import_decl.src.value.to_string());
                }
                ModuleItem::ModuleDecl(ModuleDecl::ExportAll(export_all)) => {
                    imports.push(export_all.src.value.to_string());
                }
                ModuleItem::ModuleDecl(ModuleDecl::ExportNamed(export_named)) => {
                    if let Some(src) = &export_named.src {
                        imports.push(src.value.to_string());
                    }
                }
                _ => {}
            }
        }
        
        imports
    }
    
    fn generate_hydration_wrapper(&self, entry: &Path) -> Result<String> {
        let entry_name = entry.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("App");
        
        let wrapper = format!(
            r#"
import React from "react";
import {{ hydrateRoot }} from "react-dom/client";
import {} from "{}";

const rootElement = document.getElementById("root");
if (rootElement) {{
    hydrateRoot(rootElement, React.createElement({}));
}}
"#,
            entry_name,
            entry.to_string_lossy(),
            entry_name
        );
        
        Ok(wrapper)
    }
}