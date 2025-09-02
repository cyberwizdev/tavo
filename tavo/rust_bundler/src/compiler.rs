use anyhow::Result;
use std::path::PathBuf;
use swc_core::common::{SourceMap, GLOBALS};
use swc_core::common::sync::Lrc;
use swc_core::ecma::ast::EsVersion;
use swc_core::ecma::codegen::{text_writer::JsWriter, Emitter};
use swc_core::ecma::parser::{lexer::Lexer, Parser, StringInput, Syntax, TsSyntax};


use crate::error::SSRError;

pub struct TSXCompiler {
    source_map: Lrc<SourceMap>,
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
        Ok(Self {
            source_map: Lrc::new(SourceMap::default()),
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
            let module = parser.parse_module()
                .map_err(|e| SSRError::ParseError(format!("{:?}", e)))?;

            // For now, skip transforms and just emit the parsed code
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

    fn extract_component_name(&self, source: &str) -> Result<String, SSRError> {
        let re = regex::Regex::new(r"export\s+default\s+function\s+(\w+)")
            .map_err(|e| SSRError::ParseError(format!("Regex error: {}", e)))?;
        
        if let Some(captures) = re.captures(source) {
            Ok(captures[1].to_string())
        } else {
            Ok("DefaultComponent".to_string())
        }
    }

    fn resolve_page_path(&self, route: &str) -> Result<PathBuf, SSRError> {
        let mut path = PathBuf::from("app");
        
        if route != "/" {
            path.push(route.trim_start_matches('/'));
        }
        
        path.push("page.tsx");
        
        if !path.exists() {
            return Err(SSRError::FileNotFound(path));
        }
        
        Ok(path)
    }

    fn combine_components(&self, layouts: &[CompiledLayout], page_js: &str) -> Result<String, SSRError> {
        let mut combined = String::new();
        
        for layout in layouts {
            combined.push_str(&layout.compiled_js);
            combined.push('\n');
        }
        
        combined.push_str(page_js);
        
        Ok(combined)
    }

    pub async fn compile_for_hydration(&self, component: &CompiledComponent) -> Result<String, SSRError> {
        let mut hydration_js = String::new();
        
        hydration_js.push_str("import { hydrateRoot } from 'react-dom/client';\n");
        hydration_js.push_str(&component.combined_js);
        hydration_js.push_str("\n");
        hydration_js.push_str("const container = document.getElementById('root');\n");
        hydration_js.push_str("if (container) {\n");
        hydration_js.push_str("  hydrateRoot(container, React.createElement(App));\n");
        hydration_js.push_str("}\n");
        
        Ok(hydration_js)
    }
}