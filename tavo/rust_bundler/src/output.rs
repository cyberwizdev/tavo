use anyhow::Result;
use serde::{Serialize};
use std::collections::HashMap;

#[derive(Serialize)]
pub struct OutputData {
    pub html: String,
    pub js: String,
    pub params: HashMap<String, String>,
}

#[derive(Serialize)]
pub struct ErrorOutput {
    pub error: ErrorDetails,
}

#[derive(Serialize)]
pub struct ErrorDetails {
    pub kind: String,
    pub message: String,
}

pub struct OutputManager {
    format: OutputFormat,
}

enum OutputFormat {
    Json,
    Stdout,
}

impl OutputManager {
    pub fn new(format: String) -> Self {
        let format = match format.as_str() {
            "json" => OutputFormat::Json,
            "stdout" => OutputFormat::Stdout,
            _ => OutputFormat::Json,
        };
        
        Self { format }
    }
    
    pub fn write_output(&self, data: &OutputData) -> Result<()> {
        match self.format {
            OutputFormat::Json => {
                let json = serde_json::to_string_pretty(data)?;
                println!("{}", json);
            }
            OutputFormat::Stdout => {
                println!("HTML:\n{}\n", data.html);
                println!("JavaScript:\n{}\n", data.js);
                println!("Params: {:?}", data.params);
            }
        }
        
        Ok(())
    }
}

pub fn generate_hydration_output(
    transpiled_code: &str,
    params: &HashMap<String, String>,
) -> OutputData {
    let html = generate_html_shell();
    let js = transpiled_code.to_string();
    
    OutputData {
        html,
        js,
        params: params.clone(),
    }
}

pub fn generate_ssr_output(
    rendered_html: &str,
    transpiled_code: &str,
    params: &HashMap<String, String>,
) -> OutputData {
    let html = generate_html_with_content(rendered_html, params);
    let js = generate_hydration_js(transpiled_code, params);
    
    OutputData {
        html,
        js,
        params: params.clone(),
    }
}

fn generate_html_shell() -> String {
    r#"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSR App</title>
</head>
<body>
    <div id="root"></div>
</body>
</html>"#.to_string()
}

fn generate_html_with_content(content: &str, params: &HashMap<String, String>) -> String {
    let params_script = format!(
        r#"<script>window.__TAVO_PARAMS__ = {};</script>"#,
        serde_json::to_string(params).unwrap_or_else(|_| "{}".to_string())
    );
    
    format!(
        r#"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSR App</title>
    {}
</head>
<body>
    <div id="root">{}</div>
</body>
</html>"#,
        params_script, content
    )
}

fn generate_hydration_js(transpiled_code: &str, params: &HashMap<String, String>) -> String {
    let params_injection = format!(
        "window.__TAVO_PARAMS__ = {};",
        serde_json::to_string(params).unwrap_or_else(|_| "{}".to_string())
    );
    
    format!(
        r#"{}

// Hydration bootstrap
if (typeof window !== 'undefined') {{
  const root = document.getElementById('root');
  const params = window.__TAVO_PARAMS__ || {{}};
  if (root) {{
    const {{ createRoot }} = require('react-dom/client');
    createRoot(root).render(React.createElement(App, {{ params }}));
  }}
}}
"#,
        transpiled_code
    )
}