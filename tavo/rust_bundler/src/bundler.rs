use anyhow::Result;
use std::fs;
use crate::cli::Args;
use crate::fs_router::RouteInfo;

pub fn generate_virtual_entry(route_info: &RouteInfo, args: &Args) -> Result<String> {
    let mut entry_code = String::new();
    
    // Add React imports
    entry_code.push_str("import React from 'react';\n");
    entry_code.push_str("import { createRoot } from 'react-dom/client';\n\n");
    
    // Generate layout imports
    let mut layout_imports = Vec::new();
    for (i, layout_path) in route_info.layout_chain.iter().enumerate() {
        let layout_content = fs::read_to_string(layout_path)?;
        entry_code.push_str(&format!("// Layout {}\n", i));
        entry_code.push_str(&layout_content);
        entry_code.push('\n');
        layout_imports.push(format!("Layout{}", i));
    }
    
    // Generate page import
    let page_content = fs::read_to_string(&route_info.file_path)?;
    entry_code.push_str("// Page Component\n");
    entry_code.push_str(&page_content);
    entry_code.push('\n');
    
    // Generate the App component that wraps layouts and page
    entry_code.push_str("function App({ params }) {\n");
    
    if args.compile_type == "hydration" {
        // Inject params global for client-side
        entry_code.push_str(&format!(
            "  if (typeof window !== 'undefined') {{\n    window.__TAVO_PARAMS__ = {};\n  }}\n",
            serde_json::to_string(&route_info.params)?
        ));
    }
    
    // Build nested component structure
    let mut component_jsx = "React.createElement(Page, { params })".to_string();
    
    for (i, _) in layout_imports.iter().enumerate().rev() {
        component_jsx = format!(
            "React.createElement(Layout{}, {{ params }}, {})",
            i, component_jsx
        );
    }
    
    entry_code.push_str(&format!("  return {};\n", component_jsx));
    entry_code.push_str("}\n\n");
    
    // Add hydration bootstrap for client-side
    if args.compile_type == "hydration" {
        entry_code.push_str(&generate_hydration_bootstrap());
    } else {
        // For SSR, export the App component
        entry_code.push_str("export default App;\n");
    }
    
    // Add custom useParams hook
    entry_code.push_str(&generate_use_params_hook());
    
    Ok(entry_code)
}

fn generate_hydration_bootstrap() -> &'static str {
    r#"
// Hydration bootstrap
if (typeof window !== 'undefined') {
  const root = document.getElementById('root');
  const params = window.__TAVO_PARAMS__ || {};
  if (root) {
    createRoot(root).render(React.createElement(App, { params }));
  }
}
"#
}

fn generate_use_params_hook() -> &'static str {
    r#"
// Custom useParams hook
export function useParams() {
  if (typeof window !== 'undefined') {
    return window.__TAVO_PARAMS__ || {};
  }
  return {};
}
"#
}