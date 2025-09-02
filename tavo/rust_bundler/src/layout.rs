use std::path::PathBuf;

use crate::error::SSRError;

pub struct LayoutResolver {
    app_dir: PathBuf,
}

impl LayoutResolver {
    pub fn new(app_dir: PathBuf) -> Self {
        Self { app_dir }
    }

    pub fn resolve_layouts(&self, route: &str) -> Result<Vec<PathBuf>, SSRError> {
        let mut layouts = Vec::new();
        let mut current_path = self.app_dir.clone();
        
        // Always check for root layout
        let root_layout = current_path.join("layout.tsx");
        if root_layout.exists() {
            layouts.push(root_layout);
        }
        
        // Parse route segments
        let segments: Vec<&str> = route
            .trim_start_matches('/')
            .split('/')
            .filter(|s| !s.is_empty())
            .collect();
        
        // Check for layout.tsx in each nested directory
        for segment in segments {
            current_path.push(segment);
            let layout_path = current_path.join("layout.tsx");
            
            if layout_path.exists() {
                layouts.push(layout_path);
            }
        }
        
        Ok(layouts)
    }
}
