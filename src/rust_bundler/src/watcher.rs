/*!
 * File Watcher Implementation
 * 
 * File watching functionality for development mode.
 */

use anyhow::Result;
use notify::{Config, Event, RecommendedWatcher, RecursiveMode, Watcher};
use std::path::Path;
use std::sync::mpsc;
use std::time::Duration;
use tokio::sync::broadcast;
use tracing::{info, debug, error};

pub struct FileWatcher {
    watcher: RecommendedWatcher,
    event_sender: broadcast::Sender<FileChangeEvent>,
}

#[derive(Debug, Clone)]
pub struct FileChangeEvent {
    pub path: String,
    pub change_type: String,
    pub timestamp: i64,
}

impl FileWatcher {
    /// Create new file watcher
    pub fn new() -> Result<(Self, broadcast::Receiver<FileChangeEvent>)> {
        let (event_sender, event_receiver) = broadcast::channel(100);
        let sender_clone = event_sender.clone();
        
        let (tx, rx) = mpsc::channel();
        
        let watcher = RecommendedWatcher::new(
            move |res: notify::Result<Event>| {
                if let Ok(event) = res {
                    let _ = tx.send(event);
                }
            },
            Config::default(),
        )?;
        
        // Spawn task to handle file events
        let event_sender_task = sender_clone.clone();
        tokio::spawn(async move {
            while let Ok(event) = rx.recv() {
                if let Some(change_event) = Self::process_notify_event(event) {
                    let _ = event_sender_task.send(change_event);
                }
            }
        });
        
        Ok((
            Self {
                watcher,
                event_sender: sender_clone,
            },
            event_receiver,
        ))
    }
    
    /// Start watching a directory
    pub fn watch_directory(&mut self, path: &Path) -> Result<()> {
        info!("Watching directory: {}", path.display());
        self.watcher.watch(path, RecursiveMode::Recursive)?;
        Ok(())
    }
    
    /// Stop watching a directory
    pub fn unwatch_directory(&mut self, path: &Path) -> Result<()> {
        info!("Stopped watching directory: {}", path.display());
        self.watcher.unwatch(path)?;
        Ok(())
    }
    
    /// Process notify event into our event type
    fn process_notify_event(event: Event) -> Option<FileChangeEvent> {
        use notify::EventKind;
        
        let change_type = match event.kind {
            EventKind::Create(_) => "created",
            EventKind::Modify(_) => "modified", 
            EventKind::Remove(_) => "deleted",
            _ => return None,
        };
        
        // Get first path from event
        let path = event.paths.first()?.to_string_lossy().to_string();
        
        // Filter out irrelevant files
        if Self::should_ignore_path(&path) {
            return None;
        }
        
        Some(FileChangeEvent {
            path,
            change_type: change_type.to_string(),
            timestamp: chrono::Utc::now().timestamp(),
        })
    }
    
    /// Check if path should be ignored
    fn should_ignore_path(path: &str) -> bool {
        let ignore_patterns = [
            "node_modules",
            ".git",
            "__pycache__",
            ".venv",
            "dist",
            ".DS_Store",
            ".tmp",
            ".swp",
        ];
        
        ignore_patterns.iter().any(|pattern| path.contains(pattern))
    }
    
    /// Get event sender for broadcasting
    pub fn get_event_sender(&self) -> broadcast::Sender<FileChangeEvent> {
        self.event_sender.clone()
    }
}

/// Watch multiple directories and handle file changes
pub async fn watch_project_directories(
    project_dir: &Path,
    hmr_port: u16,
) -> Result<()> {
    let (mut watcher, mut event_receiver) = FileWatcher::new()?;
    
    // Watch key directories
    let watch_dirs = ["app", "api", "components", "lib"];
    
    for dir_name in watch_dirs {
        let dir_path = project_dir.join(dir_name);
        if dir_path.exists() {
            watcher.watch_directory(&dir_path)?;
        }
    }
    
    info!("File watcher started for project directories");
    
    // Handle file change events
    while let Ok(event) = event_receiver.recv().await {
        debug!("File change detected: {:?}", event);
        
        // TODO: trigger appropriate rebuild based on file type
        match event.change_type.as_str() {
            "created" | "modified" => {
                if event.path.ends_with(".tsx") || event.path.ends_with(".ts") {
                    info!("TypeScript file changed, triggering rebuild...");
                    // TODO: trigger incremental rebuild
                }
            }
            "deleted" => {
                info!("File deleted: {}", event.path);
                // TODO: handle file deletion
            }
            _ => {}
        }
        
        // TODO: send HMR update to connected clients
        send_hmr_update(&event, hmr_port).await?;
    }
    
    Ok(())
}

/// Send HMR update to connected clients
async fn send_hmr_update(event: &FileChangeEvent, hmr_port: u16) -> Result<()> {
    // TODO: implement WebSocket client to send updates to HMR server
    debug!("Sending HMR update for: {}", event.path);
    
    // This would connect to the Python HMR WebSocket server
    // and send the file change notification
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;
    
    #[test]
    fn test_file_watcher_creation() {
        let result = FileWatcher::new();
        assert!(result.is_ok());
    }
    
    #[test]
    fn test_should_ignore_path() {
        assert!(FileWatcher::should_ignore_path("node_modules/react/index.js"));
        assert!(FileWatcher::should_ignore_path(".git/config"));
        assert!(!FileWatcher::should_ignore_path("app/page.tsx"));
    }
    
    #[tokio::test]
    async fn test_watch_directory() {
        let temp_dir = TempDir::new().unwrap();
        let (mut watcher, _receiver) = FileWatcher::new().unwrap();
        
        let result = watcher.watch_directory(temp_dir.path());
        assert!(result.is_ok());
    }
}

/*
Unit tests as comments:
1. test_file_change_event_processing() - verify file events are processed correctly
2. test_watch_multiple_directories() - test watching multiple directories simultaneously  
3. test_hmr_update_sending() - verify HMR updates are sent to correct port
*/