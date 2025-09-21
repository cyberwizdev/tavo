use anyhow::{Result, Context};
use std::path::{Path, PathBuf};
use std::collections::HashMap;
use swc_common::{Globals, Mark, GLOBALS};
use swc_ecma_ast::*;
use swc_ecma_parser::{lexer::Lexer, Parser, StringInput, Syntax, TsConfig};
use swc_ecma_transforms::{
    react::{react, Options as ReactOptions},
    typescript::strip,
    resolver,
};
use swc_ecma_codegen::{text_writer::JsWriter, Emitter};
use swc_common::{SourceMap, sync::Lrc};

use crate::bundler::Bundler;
use crate::ssr::SSRRenderer;
use crate::hydration::HydrationGenerator;
use crate::utils::resolve_import;

pub struct Compiler {
    source_map: Lrc<SourceMap>,
    bundler: Bundler,
    ssr_renderer: SSRRenderer,
    hydration_generator: HydrationGenerator,
}

impl Compiler {
    pub fn new() -> Result<Self> {
        let source_map = Lrc::new(SourceMap::default());
        
        Ok(Self {
            source_map: source_map.clone(),
            bundler: Bundler::new(source_map.clone())?,
            ssr_renderer: SSRRenderer::new()?,
            hydration_generator: HydrationGenerator::new(source_map.clone())?,
        })
    }
    
    pub async fn render_ssr(&mut self, entry: &Path) -> Result<String> {
        let bundle = self.bundler.bundle_for_ssr(entry).await?;
        self.ssr_renderer.render(&bundle).await
    }
    
    pub async fn generate_hydration_script(&mut self, entry: &Path) -> Result<String> {
        let bundle = self.bundler.bundle_for_hydration(entry).await?;
        self.hydration_generator.generate(&bundle).await
    }
    
    pub fn combine_html_and_script(&self, html: &str, js: &str) -> Result<String> {
        let full_html = format!(
            r#"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSR App</title>
</head>
<body>
    <div id="root">{}</div>
    <script>{}</script>
</body>
</html>"#,
            html, js
        );
        
        Ok(full_html)
    }
    
    pub fn parse_tsx(&self, code: &str, filename: &str) -> Result<Module> {
        let source_file = self.source_map.new_source_file(
            swc_common::FileName::Real(PathBuf::from(filename)),
            code.to_string(),
        );
        
        let lexer = Lexer::new(
            Syntax::Typescript(TsConfig {
                tsx: true,
                decorators: false,
                dts: false,
                no_early_errors: true,
                disallow_ambiguous_jsx_like: false,
            }),
            EsVersion::Es2022,
            StringInput::from(&*source_file),
            None,
        );
        
        let mut parser = Parser::new_from(lexer);
        
        parser
            .parse_module()
            .map_err(|e| anyhow::anyhow!("Parse error: {:?}", e))
    }
    
    pub fn transform_tsx(&self, mut module: Module) -> Result<Module> {
        GLOBALS.set(&Globals::new(), || {
            let unresolved_mark = Mark::new();
            let top_level_mark = Mark::new();
            
            // Apply resolver first
            module = module.fold_with(&mut resolver(unresolved_mark, top_level_mark, true));
            
            // Strip TypeScript types
            module = module.fold_with(&mut strip(top_level_mark));
            
            // Transform JSX to React.createElement calls
            module = module.fold_with(&mut react(
                self.source_map.clone(),
                None,
                ReactOptions {
                    pragma: Some("React.createElement".to_string()),
                    pragma_frag: Some("React.Fragment".to_string()),
                    throw_if_namespace: false,
                    development: false,
                    use_builtins: false,
                    use_spread: false,
                    refresh: None,
                    runtime: None,
                    import_source: None,
                    next: false,
                },
                top_level_mark,
                unresolved_mark,
            ));
            
            Ok(module)
        })?
    }
    
    pub fn generate_code(&self, module: &Module) -> Result<String> {
        let mut buf = Vec::new();
        {
            let writer = JsWriter::new(self.source_map.clone(), "\n", &mut buf, None);
            let mut emitter = Emitter {
                cfg: swc_ecma_codegen::Config::default(),
                cm: self.source_map.clone(),
                comments: None,
                wr: writer,
            };
            
            emitter.emit_module(module)?;
        }
        
        String::from_utf8(buf).context("Generated code is not valid UTF-8")
    }
}