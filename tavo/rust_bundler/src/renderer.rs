use crate::compiler::CompiledComponent;
use crate::error::SSRError;
use rquickjs::{Context, Runtime};
use std::collections::HashMap;
use crate::compiler::TSXCompiler;
use regex::Regex;

#[derive(Debug)]

pub struct SSRRenderer {
    react_bundle: String,
    react_dom_bundle: String,
}

impl SSRRenderer {
    pub fn new() -> Result<Self, SSRError> {
        // Load React and ReactDOM bundles (you'll need to bundle these separately)
        // For now, we'll use a simplified approach
        Ok(Self {
            react_bundle: include_str!("../bundles/react.js").to_string(),
            react_dom_bundle: include_str!("../bundles/react-dom-server.js").to_string(),
        })
    }

    pub async fn render_to_html(&self, component: &CompiledComponent) -> Result<String, SSRError> {
        let rt = Runtime::new().map_err(|e| SSRError::JsRuntime(e.to_string()))?;
        let ctx = Context::full(&rt).map_err(|e| SSRError::JsRuntime(e.to_string()))?;

        let result = ctx.with(|ctx| -> Result<String, SSRError> {
            // Setup React runtime
            self.setup_react_runtime(&ctx)?;
            
            // Convert ES6 imports to global variables
            let converted_js = self.convert_imports_to_globals(&component.combined_js)?;
            
            // Execute the component code
            ctx.eval::<(), &str>(&converted_js)
                .map_err(|e| SSRError::JsRuntime(format!("Component eval failed: {:?}", e)))?;

            // Get the component name to render
            let component_name = component
                .layouts
                .last()
                .map(|l| l.component_name.as_str())
                .unwrap_or("DefaultComponent");

            // Render the component to HTML
            let render_script = format!(
                r#"
                (function() {{
                    try {{
                        const element = React.createElement({});
                        return ReactDOMServer.renderToString(element);
                    }} catch (error) {{
                        throw new Error('Render failed: ' + error.message);
                    }}
                }})()
                "#,
                component_name
            );

            let html: String = ctx.eval::<String, &str>(&render_script)
                .map_err(|e| SSRError::JsRuntime(format!("Render eval failed: {:?}", e)))?;

            Ok(html)
        })?;

        Ok(result)
    }

    pub async fn render_to_static_html(&self, component: &CompiledComponent) -> Result<String, SSRError> {
        let rt = Runtime::new().map_err(|e| SSRError::JsRuntime(e.to_string()))?;
        let ctx = Context::full(&rt).map_err(|e| SSRError::JsRuntime(e.to_string()))?;

        let result = ctx.with(|ctx| -> Result<String, SSRError> {
            self.setup_react_runtime(&ctx)?;
            
            let converted_js = self.convert_imports_to_globals(&component.combined_js)?;
            
            ctx.eval::<(), &str>(&converted_js)
                .map_err(|e| SSRError::JsRuntime(format!("Component eval failed: {:?}", e)))?;

            let component_name = component
                .layouts
                .last()
                .map(|l| l.component_name.as_str())
                .unwrap_or("DefaultComponent");

            let render_script = format!(
                r#"
                (function() {{
                    try {{
                        const element = React.createElement({});
                        return ReactDOMServer.renderToStaticMarkup(element);
                    }} catch (error) {{
                        throw new Error('Static render failed: ' + error.message);
                    }}
                }})()
                "#,
                component_name
            );

            let html: String = ctx.eval::<String, &str>(&render_script)
                .map_err(|e| SSRError::JsRuntime(format!("Static render eval failed: {:?}", e)))?;

            Ok(html)
        })?;

        Ok(result)
    }

    fn setup_react_runtime(&self, ctx: &rquickjs::Ctx) -> Result<(), SSRError> {
        // Load React into the global scope
        ctx.eval::<(), &str>(&format!(
            r#"
// Setup global React
{};
globalThis.React = React;

// Setup ReactDOMServer
{};
globalThis.ReactDOMServer = ReactDOMServer;

// Setup console for debugging
globalThis.console = {{
    log: function(...args) {{
        // You can implement actual logging here
    }},
    error: function(...args) {{
        throw new Error('Console error: ' + args.join(' '));
    }},
    warn: function(...args) {{
        // Handle warnings
    }}
}};
"#,
            self.react_bundle,
            self.react_dom_bundle
        ))
        .map_err(|e| SSRError::JsRuntime(format!("Failed to setup React runtime: {:?}", e)))?;

        Ok(())
    }

    fn convert_imports_to_globals(&self, js_code: &str) -> Result<String, SSRError> {
        // Convert ES6 imports to global variable assignments
        let mut converted = js_code.to_string();

        // Map of import patterns to global variable assignments
        let import_mappings = vec![
            // import React from 'react' -> const React = globalThis.React
            (r#"import\s+React\s+from\s+['"]react['"];\s*"#, "const React = globalThis.React;\n"),
            // import { useState, useEffect } from 'react'
            (r#"import\s*\{\s*([^}]+)\s*\}\s*from\s+['"]react['"];\s*"#, "const { $1 } = globalThis.React;\n"),
            // import ReactDOMServer from 'react-dom/server'
            (r#"import\s+ReactDOMServer\s+from\s+['"]react-dom/server['"];\s*"#, "const ReactDOMServer = globalThis.ReactDOMServer;\n"),
            // Remove other imports for now (you can extend this)
            (r#"import\s+[^;]+from\s+['"][^'"]+['"];\s*"#, ""),
        ];

        for (pattern, replacement) in import_mappings {
            let re = Regex::new(pattern)
                .map_err(|e| SSRError::ParseError(format!("Regex compilation failed: {}", e)))?;
            converted = re.replace_all(&converted, replacement).to_string();
        }

        Ok(converted)
    }

    pub async fn render_route(&self, route: &str, _context: &SSRContext) -> Result<String, SSRError> {
        // This method should be called from your routing system
        // For now, it's a placeholder that would use your compiler
        
        // 1. Discover layouts for the route
        let layouts = self.discover_layouts_for_route(route)?;
        
        // 2. Compile the route with layouts (you'd use your TSXCompiler here)
        let compiler = TSXCompiler::new()?;
        let component = compiler.compile_route_with_layouts(route, &layouts).await?;
        
        // 3. Render to HTML
        let html = self.render_to_html(&component).await?;

        Ok(html)
    }

    fn discover_layouts_for_route(&self, route: &str) -> Result<Vec<std::path::PathBuf>, SSRError> {
        // Discover layout files for a given route
        // This should walk up the directory tree looking for layout.tsx files
        let mut layouts = Vec::new();
        let mut current_path = std::path::PathBuf::from("app");
        
        // Add root layout if exists
        let root_layout = current_path.join("layout.tsx");
        if root_layout.exists() {
            layouts.push(root_layout);
        }
        
        // Add nested layouts based on route segments
        if route != "/" {
            let segments: Vec<&str> = route
                .trim_start_matches('/')
                .split('/')
                .filter(|s| !s.is_empty())
                .collect();
            
            for segment in segments {
                current_path.push(segment);
                let layout_path = current_path.join("layout.tsx");
                if layout_path.exists() {
                    layouts.push(layout_path);
                }
            }
        }
        
        Ok(layouts)
    }
}

#[derive(Debug)]
pub struct SSRContext {
    pub url: String,
    pub method: String,
    pub headers: HashMap<String, String>,
    pub query_params: HashMap<String, String>,
    pub route_params: HashMap<String, String>,
}

// Alternative implementation using a simpler approach
pub struct SimpleSSRRenderer;

impl SimpleSSRRenderer {
    pub fn new() -> Self {
        Self
    }

    pub async fn render_component_simple(&self, component: &CompiledComponent) -> Result<String, SSRError> {
        // For debugging: just return the compiled JS wrapped in a basic HTML template
        let component_name = component
            .layouts
            .last()
            .map(|l| l.component_name.as_str())
            .unwrap_or("DefaultComponent");

        let html = format!(
            r#"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tavo App</title>
</head>
<body>
    <div id="root">
        <!-- Component: {} -->
        <div>Loading...</div>
    </div>
    <script>
        // Debug: Component code
        /*
        {}
        */
        console.log('Component ready for hydration');
    </script>
</body>
</html>"#,
            component_name,
            component.combined_js.replace("*/", "*\\/") // Escape comment endings
        );

        Ok(html)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_import_conversion() {
        let renderer = SSRRenderer::new().unwrap();
        let input = r#"
import React from 'react';
import { useState } from 'react';
import ReactDOMServer from 'react-dom/server';

function MyComponent() {
    return React.createElement('div', null, 'Hello');
}
"#;
        
        let result = renderer.convert_imports_to_globals(input).unwrap();
        assert!(result.contains("const React = globalThis.React"));
        assert!(result.contains("const { useState } = globalThis.React"));
        assert!(!result.contains("import React from"));
    }
}