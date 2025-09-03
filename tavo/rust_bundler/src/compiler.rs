use anyhow::Result;
use std::path::PathBuf;
use swc_core::common::{SourceMap, GLOBALS, Mark};
use swc_core::common::sync::Lrc;
use swc_core::ecma::ast::{EsVersion, Module, ImportDecl, Stmt};
use swc_core::ecma::codegen::{text_writer::JsWriter, Emitter};
use swc_core::ecma::parser::{lexer::Lexer, Parser, StringInput, Syntax, TsSyntax};
use regex::Regex;

use crate::error::SSRError;

pub struct TSXCompiler {
    source_map: Lrc<SourceMap>,
    component_name_regex: Regex,
}

#[derive(Debug, Clone)]
pub struct CompiledComponent {
    pub route: String,
    pub layouts: Vec<CompiledLayout>,
    pub page_component: String,
    pub combined_js: String,
}

#[derive(Debug, Clone)]
pub struct CompiledLayout {
    pub path: PathBuf,
    pub component_name: String,
    pub compiled_js: String,
}

impl TSXCompiler {
    pub fn new() -> Result<Self, SSRError> {
        let component_name_regex = Regex::new(r"export\s+default\s+function\s+(\w+)")
            .map_err(|e| SSRError::ParseError(format!("Failed to compile regex: {}", e)))?;

        Ok(Self {
            source_map: Lrc::new(SourceMap::default()),
            component_name_regex,
        })
    }

    pub async fn compile_route_with_layouts(
        &self,
        route: &str,
        layouts: &[PathBuf],
    ) -> Result<CompiledComponent, SSRError> {
        let mut compiled_layouts = Vec::new();
        
        for layout_path in layouts {
            let layout_source = std::fs::read_to_string(layout_path)
                .map_err(|e| SSRError::FileRead(layout_path.clone(), e))?;
            
            let compiled_js = self.compile_tsx(&layout_source).await?;
            let component_name = self.extract_component_name(&layout_source)?;
            
            compiled_layouts.push(CompiledLayout {
                path: layout_path.clone(),
                component_name,
                compiled_js,
            });
        }

        let page_path = self.resolve_page_path(route)?;
        let page_source = std::fs::read_to_string(&page_path)
            .map_err(|e| SSRError::FileRead(page_path, e))?;
        
        let page_js = self.compile_tsx(&page_source).await?;
        let combined_js = self.combine_components(&compiled_layouts, &page_js)?;

        Ok(CompiledComponent {
            route: route.to_string(),
            layouts: compiled_layouts,
            page_component: page_js,
            combined_js,
        })
    }

    async fn compile_tsx(&self, source: &str) -> Result<String, SSRError> {
        GLOBALS.set(&Default::default(), || {
            let input = StringInput::new(
                source, 
                swc_core::common::BytePos(0), 
                swc_core::common::BytePos(source.len() as u32)
            );
            
            let lexer = Lexer::new(
                Syntax::Typescript(TsSyntax {
                    tsx: true,
                    decorators: false,
                    dts: false,
                    no_early_errors: false,
                    disallow_ambiguous_jsx_like: false,
                }),
                EsVersion::latest(),
                input,
                None,
            );

            let mut parser = Parser::new_from(lexer);
            let mut module = parser.parse_module()
                .map_err(|e| SSRError::ParseError(format!("{:?}", e)))?;

            // Apply basic transformations
            let unresolved_mark = Mark::new();
            let top_level_mark = Mark::new();

            // 1. Resolve references
            // module = module.fold_with(&mut resolver(unresolved_mark, top_level_mark, false));

            // 2. Strip TypeScript types
            // module = module.fold_with(&mut strip_type());

            // 3. Remove/transform imports for SSR compatibility
            module = self.transform_imports_for_ssr(module)?;

            // Generate the final JavaScript
            let mut buf = Vec::new();
            let writer = JsWriter::new(self.source_map.clone(), "\n", &mut buf, None);
            let mut emitter = Emitter {
                cfg: Default::default(),
                comments: None,
                cm: self.source_map.clone(),
                wr: writer,
            };

            emitter.emit_module(&module)
                .map_err(|e| SSRError::CodegenError(format!("{:?}", e)))?;

            String::from_utf8(buf)
                .map_err(|e| SSRError::CodegenError(format!("UTF-8 error: {}", e)))
        })
    }

    fn transform_imports_for_ssr(&self, mut module: Module) -> Result<Module, SSRError> {
        use swc_core::ecma::ast::*;
        
        // Filter out import declarations for SSR compatibility
        let mut new_body = Vec::new();
        
        for item in module.body {
            match &item {
                ModuleItem::ModuleDecl(ModuleDecl::Import(import_decl)) => {
                    let import_source = import_decl.src.value.as_str();

                    // Skip React imports - we'll provide these globally
                    if import_source == "react" || import_source == "react-dom/server" || import_source == "react-dom/client" {
                        continue;
                    }

                    // Handle different types of imports for SSR
                    match import_source {
                        // CSS imports - skip in SSR, handle separately
                        s if s.ends_with(".css") || s.ends_with(".scss") || s.ends_with(".sass") => {
                            continue;
                        }
                        
                        // Image imports - convert to require() or skip
                        s if s.ends_with(".png") || s.ends_with(".jpg") || s.ends_with(".jpeg") || 
                             s.ends_with(".gif") || s.ends_with(".svg") || s.ends_with(".webp") => {
                            continue;
                        }
                        
                        // Node.js built-in modules - keep as-is for server-side
                        s if s.starts_with("node:") || matches!(s, 
                            "fs" | "path" | "crypto" | "util" | "url" | "querystring" | 
                            "stream" | "buffer" | "events" | "http" | "https" | "os") => {
                            new_body.push(item);
                        }
                        
                        // Relative imports - these are local components/utilities
                        s if s.starts_with("./") || s.starts_with("../") => {
                            // For now, keep relative imports but in a full implementation
                            // you'd want to resolve and compile these recursively
                            new_body.push(item);
                        }
                        
                        // Absolute imports from project root
                        s if s.starts_with("@/") || s.starts_with("~/") => {
                            // Transform absolute imports to relative paths
                            // This is a simplified transformation
                            new_body.push(item);
                        }
                        
                        // npm package imports
                        _ => {
                            // Check if it's a known SSR-compatible package
                            match import_source {
                                // Common SSR-safe libraries
                                "lodash" | "date-fns" | "uuid" | "classnames" | "clsx" => {
                                    new_body.push(item);
                                }
                                
                                // Next.js specific imports - transform for SSR
                                "next/link" | "next/image" | "next/head" | "next/router" => {
                                    // In a real implementation, you'd provide SSR-compatible alternatives
                                    // For now, we'll create stub implementations
                                    let stub_decl = self.create_stub_import(import_decl, import_source)?;
                                    if let Some(stub) = stub_decl {
                                        new_body.push(ModuleItem::Stmt(stub));
                                    }
                                }
                                
                                // Client-only libraries - skip or provide stubs
                                s if self.is_client_only_library(s) => {
                                    continue;
                                }
                                
                                // Default: assume it's SSR-compatible
                                _ => {
                                    new_body.push(item);
                                }
                            }
                        }
                    }
                }
                _ => {
                    new_body.push(item);
                }
            }
        }
        
        module.body = new_body;
        Ok(module)
    }
    
    fn create_stub_import(&self, import_decl: &ImportDecl, source: &str) -> Result<Option<Stmt>, SSRError> {
        use swc_core::ecma::ast::*;
        
        // Create stub implementations for client-only imports
        let stub_code = match source {
            "next/link" => {
                "const Link = ({ href, children, ...props }) => React.createElement('a', { href, ...props }, children);"
            }
            "next/image" => {
                "const Image = ({ src, alt, width, height, ...props }) => React.createElement('img', { src, alt, width, height, ...props });"
            }
            "next/head" => {
                "const Head = ({ children }) => null;" // SSR will handle head separately
            }
            "next/router" => {
                "const useRouter = () => ({ push: () => {}, replace: () => {}, pathname: '/', query: {} });"
            }
            _ => return Ok(None),
        };
        
        // Parse the stub code into an AST node
        // This is a simplified approach - in a real implementation you'd want proper AST construction
        Ok(None) // For now, return None to skip complex stub creation
    }
    
    fn is_client_only_library(&self, source: &str) -> bool {
        matches!(source,
            // DOM manipulation libraries
            "jquery" | "zepto" | 
            // Browser APIs
            "web-animations-api" |
            // Client-side routing
            "react-router-dom" |
            // Canvas/WebGL libraries
            "three" | "p5" | "fabric" |
            // Service worker libraries
            "workbox-sw" |
            // Browser storage libraries
            "localforage" |
            // Analytics libraries that require DOM
            "react-ga" | "gtag"
        )
    }

    fn extract_component_name(&self, source: &str) -> Result<String, SSRError> {
        // Try multiple patterns for component extraction
        let patterns = vec![
            r"export\s+default\s+function\s+(\w+)",
            r"export\s+default\s+(\w+)",
            r"function\s+(\w+)\s*\([^)]*\)\s*\{",
            r"const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*\{",
            r"const\s+(\w+)\s*=\s*\([^)]*\)\s*=>",
        ];
        
        for pattern in patterns {
            let re = Regex::new(pattern)
                .map_err(|e| SSRError::ParseError(format!("Regex error: {}", e)))?;
            
            if let Some(captures) = re.captures(source) {
                if let Some(name) = captures.get(1) {
                    let component_name = name.as_str().to_string();
                    // Validate component name starts with uppercase (React convention)
                    if component_name.chars().next().unwrap_or('a').is_uppercase() {
                        return Ok(component_name);
                    }
                }
            }
        }
        
        Ok("DefaultComponent".to_string())
    }

    fn resolve_page_path(&self, route: &str) -> Result<PathBuf, SSRError> {
        let mut path = PathBuf::from("app");
        
        if route != "/" {
            let segments: Vec<&str> = route
                .trim_start_matches('/')
                .split('/')
                .filter(|s| !s.is_empty())
                .collect();
                
            for segment in segments {
                path.push(segment);
            }
        }
        
        path.push("page.tsx");
        
        if !path.exists() {
            return Err(SSRError::FileNotFound(path));
        }
        
        Ok(path)
    }

    fn combine_components(&self, layouts: &[CompiledLayout], page_js: &str) -> Result<String, SSRError> {
        let mut combined = String::new();
        
        // Add React globals setup for SSR
        combined.push_str("// React setup for SSR\n");
        combined.push_str("const React = globalThis.React;\n");
        combined.push_str("const ReactDOMServer = globalThis.ReactDOMServer;\n\n");
        
        // Add layout components
        for layout in layouts {
            combined.push_str(&format!("// Layout: {}\n", layout.path.display()));
            combined.push_str(&layout.compiled_js);
            combined.push_str("\n\n");
        }
        
        // Add page component
        combined.push_str("// Page component\n");
        combined.push_str(page_js);
        combined.push_str("\n");
        
        Ok(combined)
    }

    pub async fn compile_for_hydration(&self, component: &CompiledComponent) -> Result<String, SSRError> {
        let mut hydration_js = String::new();
        
        // For hydration, we need browser-compatible code with proper imports
        hydration_js.push_str("// Client-side hydration bundle\n");
        hydration_js.push_str("import React from 'react';\n");
        hydration_js.push_str("import { hydrateRoot } from 'react-dom/client';\n\n");
        
        // Add component code
        hydration_js.push_str(&component.combined_js);
        hydration_js.push_str("\n");
        
        // Add hydration entry point
        hydration_js.push_str("// Hydration entry point\n");
        hydration_js.push_str("const container = document.getElementById('root');\n");
        hydration_js.push_str("if (container) {\n");
        
        let component_name = component
            .layouts
            .last()
            .map(|l| l.component_name.as_str())
            .unwrap_or("DefaultComponent");
            
        hydration_js.push_str(&format!(
            "  hydrateRoot(container, React.createElement({}));\n",
            component_name
        ));
        hydration_js.push_str("} else {\n");
        hydration_js.push_str("  console.error('Root element not found for hydration');\n");
        hydration_js.push_str("}\n");
        
        Ok(hydration_js)
    }
}