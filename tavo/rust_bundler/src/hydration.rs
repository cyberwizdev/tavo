use anyhow::{Result, Context};
use std::collections::HashMap;
use swc_common::{SourceMap, sync::Lrc};
use swc_ecma_minifier::{optimize, ExtraOptions, MinifyOptions};
use swc_ecma_ast::*;
use swc_ecma_parser::{lexer::Lexer, Parser, StringInput, Syntax, TsConfig};

use crate::bundler::Bundle;
use crate::compiler::Compiler;

pub struct HydrationGenerator {
    source_map: Lrc<SourceMap>,
    compiler: Compiler,
}

impl HydrationGenerator {
    pub fn new(source_map: Lrc<SourceMap>) -> Result<Self> {
        Ok(Self {
            source_map,
            compiler: Compiler::new()?,
        })
    }
    
    pub async fn generate(&mut self, bundle: &Bundle) -> Result<String> {
        // Combine all modules into a single script
        let combined_code = self.combine_modules(bundle)?;
        
        // Parse the combined code
        let module = self.compiler.parse_tsx(&combined_code, "hydration_bundle.js")?;
        
        // Minify the code
        let minified = self.minify_module(module)?;
        
        Ok(minified)
    }
    
    fn combine_modules(&self, bundle: &Bundle) -> Result<String> {
        let mut combined = String::new();
        
        // Add React and ReactDOM imports at the top
        combined.push_str(&format!(
            r#"
// React runtime for hydration
const React = {{
    createElement: function(type, props, ...children) {{
        const element = document.createElement(type);
        if (props) {{
            for (const key in props) {{
                if (key === 'className') {{
                    element.className = props[key];
                }} else if (key === 'onClick') {{
                    element.onclick = props[key];
                }} else if (key !== 'children') {{
                    element.setAttribute(key, props[key]);
                }}
            }}
        }}
        
        const allChildren = props && props.children 
            ? [].concat(props.children, children).filter(Boolean)
            : children.filter(Boolean);
        
        allChildren.forEach(child => {{
            if (typeof child === 'string') {{
                element.appendChild(document.createTextNode(child));
            }} else {{
                element.appendChild(child);
            }}
        }});
        
        return element;
    }},
    Fragment: function(props) {{
        const fragment = document.createDocumentFragment();
        if (props.children) {{
            const children = Array.isArray(props.children) ? props.children : [props.children];
            children.forEach(child => {{
                if (typeof child === 'string') {{
                    fragment.appendChild(document.createTextNode(child));
                }} else {{
                    fragment.appendChild(child);
                }}
            }});
        }}
        return fragment;
    }}
}};

const ReactDOM = {{
    hydrateRoot: function(container, element) {{
        container.innerHTML = '';
        container.appendChild(element);
    }}
}};

"#
        ));
        
        // Add all modules except the entry point
        for (module_path, code) in &bundle.modules {
            if module_path != &bundle.entry_point {
                combined.push_str(&format!("// Module: {}\n", module_path));
                combined.push_str(code);
                combined.push_str("\n\n");
            }
        }
        
        // Add the entry point (hydration wrapper) last
        if let Some(entry_code) = bundle.modules.get(&bundle.entry_point) {
            combined.push_str("// Entry point (hydration)\n");
            combined.push_str(entry_code);
        }
        
        Ok(combined)
    }
    
    fn minify_module(&self, module: Module) -> Result<String> {
        let minified = optimize(
            module,
            self.source_map.clone(),
            None,
            None,
            &MinifyOptions {
                compress: Some(Default::default()),
                mangle: Some(Default::default()),
                ..Default::default()
            },
            &ExtraOptions {
                unresolved_mark: swc_common::Mark::new(),
                top_level_mark: swc_common::Mark::new(),
            },
        );
        
        self.compiler.generate_code(&minified)
    }
}