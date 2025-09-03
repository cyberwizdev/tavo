use anyhow::{anyhow, Result};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RouteInfo {
    pub file_path: PathBuf,
    pub params: HashMap<String, String>,
    pub layout_chain: Vec<PathBuf>,
}

pub fn resolve_route(route: &str, app_dir: &str) -> Result<RouteInfo> {
    let app_path = Path::new(app_dir);
    if !app_path.exists() {
        return Err(anyhow!("App directory does not exist: {}", app_dir));
    }

    // Find all page.tsx files
    let page_files = find_page_files(app_path)?;
    
    // Try to match the route
    for page_file in page_files {
        if let Some(route_info) = try_match_route(route, &page_file, app_path)? {
            return Ok(route_info);
        }
    }

    Err(anyhow!("No matching page for route: {}", route))
}

fn find_page_files(app_dir: &Path) -> Result<Vec<PathBuf>> {
    let mut page_files = Vec::new();
    
    for entry in WalkDir::new(app_dir) {
        let entry = entry?;
        let path = entry.path();
        
        if path.file_name().and_then(|s| s.to_str()) == Some("page.tsx") {
            page_files.push(path.to_path_buf());
        }
    }
    
    Ok(page_files)
}

fn try_match_route(route: &str, page_file: &Path, app_dir: &Path) -> Result<Option<RouteInfo>> {
    // Convert file path to route pattern
    let relative_path = page_file.strip_prefix(app_dir)?;
    let route_pattern = file_path_to_route_pattern(relative_path)?;
    
    // Try to match route against pattern
    if let Some(params) = match_route_pattern(&route_pattern, route)? {
        // Find layout chain
        let layout_chain = find_layout_chain(page_file, app_dir)?;
        
        let route_info = RouteInfo {
            file_path: page_file.to_path_buf(),
            params,
            layout_chain,
        };
        
        return Ok(Some(route_info));
    }
    
    Ok(None)
}

fn file_path_to_route_pattern(relative_path: &Path) -> Result<String> {
    let mut pattern = String::new();
    let mut components = relative_path.components().collect::<Vec<_>>();
    
    // Remove page.tsx from the end
    if components.last().and_then(|c| c.as_os_str().to_str()) == Some("page.tsx") {
        components.pop();
    }
    
    for component in components {
        let component_str = component.as_os_str().to_str()
            .ok_or_else(|| anyhow!("Invalid UTF-8 in path component"))?;
            
        pattern.push('/');
        
        // Handle dynamic segments [param]
        if component_str.starts_with('[') && component_str.ends_with(']') {
            let param_name = &component_str[1..component_str.len()-1];
            pattern.push_str(&format!("::{}", param_name));
        } else {
            pattern.push_str(component_str);
        }
    }
    
    if pattern.is_empty() {
        pattern = "/".to_string();
    }
    
    Ok(pattern)
}

fn match_route_pattern(pattern: &str, route: &str) -> Result<Option<HashMap<String, String>>> {
    let mut params = HashMap::new();
    
    // Convert pattern to regex
    let regex_pattern = pattern
        .split('/')
        .map(|segment| {
            if segment.starts_with("::") {
                "([^/]+)".to_string()
            } else {
                regex::escape(segment)
            }
        })
        .collect::<Vec<_>>()
        .join("/");
    
    let regex_pattern = format!("^{}$", regex_pattern);
    let regex = Regex::new(&regex_pattern)?;
    
    if let Some(captures) = regex.captures(route) {
        let param_names: Vec<&str> = pattern
            .split('/')
            .filter_map(|segment| {
                if segment.starts_with("::") {
                    Some(&segment[2..])
                } else {
                    None
                }
            })
            .collect();
        
        for (i, param_name) in param_names.iter().enumerate() {
            if let Some(capture) = captures.get(i + 1) {
                params.insert(param_name.to_string(), capture.as_str().to_string());
            }
        }
        
        return Ok(Some(params));
    }
    
    Ok(None)
}

fn find_layout_chain(page_file: &Path, app_dir: &Path) -> Result<Vec<PathBuf>> {
    let mut layouts = Vec::new();
    let relative_path = page_file.strip_prefix(app_dir)?;
    let mut current_dir = app_dir.to_path_buf();
    
    // Walk up the directory tree looking for layout files
    for component in relative_path.components() {
        current_dir = current_dir.join(component);
        
        let layout_file = current_dir.join("layout.tsx");
        if layout_file.exists() && layout_file != *page_file {
            layouts.push(layout_file);
        }
    }
    
    // Remove the page file itself if it was added
    layouts.retain(|p| p.file_name().and_then(|s| s.to_str()) != Some("page.tsx"));
    
    Ok(layouts)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    
    #[test]
    fn test_file_path_to_route_pattern() {
        assert_eq!(file_path_to_route_pattern(Path::new("page.tsx")).unwrap(), "/");
        assert_eq!(file_path_to_route_pattern(Path::new("about/page.tsx")).unwrap(), "/about");
        assert_eq!(file_path_to_route_pattern(Path::new("blog/[slug]/page.tsx")).unwrap(), "/blog/::slug");
    }
    
    #[test]
    fn test_match_route_pattern() {
        let mut expected = HashMap::new();
        expected.insert("slug".to_string(), "hello-world".to_string());
        
        assert_eq!(
            match_route_pattern("/blog/::slug", "/blog/hello-world").unwrap(),
            Some(expected)
        );
        
        assert_eq!(
            match_route_pattern("/about", "/about").unwrap(),
            Some(HashMap::new())
        );
        
        assert_eq!(
            match_route_pattern("/blog/::slug", "/about").unwrap(),
            None
        );
    }
}