"""
Tavo File Watcher

File watcher (watchfiles/watchdog) that triggers bundler rebuilds and HMR pushes.
"""

import asyncio
import logging
from pathlib import Path
from typing import Set, Optional, Dict, Any, List
import time
from dataclasses import dataclass

try:
    from watchfiles import awatch
    WATCHFILES_AVAILABLE = True
except ImportError:
    WATCHFILES_AVAILABLE = False
    # Fallback to polling if watchfiles not available

logger = logging.getLogger(__name__)


@dataclass
class FileChangeEvent:
    """Represents a file change event."""
    path: Path
    change_type: str  # "created", "modified", "deleted"
    timestamp: float


class FileWatcher:
    """
    File watcher that monitors project files and triggers HMR updates.
    """
    
    def __init__(
        self, 
        watch_dirs: List[Path],
        hmr_server: Optional[Any] = None,
        ignore_patterns: Optional[Set[str]] = None
    ):
        self.watch_dirs = watch_dirs
        self.hmr_server = hmr_server
        self.ignore_patterns = ignore_patterns or {
            "node_modules", ".git", "__pycache__", ".venv", "dist", ".next"
        }
        self._running = False
        self._watch_task: Optional[asyncio.Task] = None
        self._last_change_time = 0.0
        self._debounce_delay = 0.1  # 100ms debounce
    
    async def start(self) -> None:
        """Start watching for file changes."""
        if self._running:
            logger.warning("File watcher already running")
            return
        
        self._running = True
        
        if WATCHFILES_AVAILABLE:
            self._watch_task = asyncio.create_task(self._watch_with_watchfiles())
        else:
            self._watch_task = asyncio.create_task(self._watch_with_polling())
        
        logger.info(f"File watcher started for {len(self.watch_dirs)} directories")
    
    async def stop(self) -> None:
        """Stop watching for file changes."""
        self._running = False
        
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        
        logger.info("File watcher stopped")
    
    async def _watch_with_watchfiles(self) -> None:
        """Watch files using the watchfiles library."""
        try:
            async for changes in awatch(*self.watch_dirs, stop_event=None):
                if not self._running:
                    break
                
                await self._handle_changes(changes)
                
        except Exception as e:
            logger.error(f"File watcher error: {e}")
            if self._running:
                # Restart watcher
                await asyncio.sleep(1)
                await self.start()
    
    async def _watch_with_polling(self) -> None:
        """Fallback polling-based file watcher."""
        logger.warning("Using polling file watcher (install watchfiles for better performance)")
        
        file_mtimes: Dict[Path, float] = {}
        
        while self._running:
            try:
                changes = []
                
                for watch_dir in self.watch_dirs:
                    if not watch_dir.exists():
                        continue
                    
                    for file_path in watch_dir.rglob("*"):
                        if not file_path.is_file() or self._should_ignore(file_path):
                            continue
                        
                        try:
                            mtime = file_path.stat().st_mtime
                            
                            if file_path not in file_mtimes:
                                file_mtimes[file_path] = mtime
                            elif file_mtimes[file_path] != mtime:
                                changes.append((str(file_path), "modified"))
                                file_mtimes[file_path] = mtime
                                
                        except OSError:
                            # File might have been deleted
                            if file_path in file_mtimes:
                                changes.append((str(file_path), "deleted"))
                                del file_mtimes[file_path]
                
                if changes:
                    await self._handle_changes(changes)
                
                await asyncio.sleep(0.5)  # Poll every 500ms
                
            except Exception as e:
                logger.error(f"Polling watcher error: {e}")
                await asyncio.sleep(1)
    
    async def _handle_changes(self, changes: Any) -> None:
        """
        Handle file change events.
        
        Args:
            changes: File change events from watcher
        """
        current_time = time.time()
        
        # Debounce rapid changes
        if current_time - self._last_change_time < self._debounce_delay:
            return
        
        self._last_change_time = current_time
        
        # Filter and process changes
        relevant_changes = []
        
        for change in changes:
            if WATCHFILES_AVAILABLE:
                change_type, file_path = change
                file_path = Path(file_path)
            else:
                file_path, change_type = change
                file_path = Path(file_path)
            
            if self._should_ignore(file_path):
                continue
            
            relevant_changes.append(FileChangeEvent(
                path=file_path,
                change_type=change_type,
                timestamp=current_time
            ))
        
        if relevant_changes:
            await self._notify_changes(relevant_changes)
    
    def _should_ignore(self, file_path: Path) -> bool:
        """Check if file should be ignored."""
        path_str = str(file_path)
        
        for pattern in self.ignore_patterns:
            if pattern in path_str:
                return True
        
        # Ignore temporary files
        if file_path.name.startswith('.') and file_path.suffix in {'.tmp', '.swp'}:
            return True
        
        return False
    
    async def _notify_changes(self, changes: List[FileChangeEvent]) -> None:
        """
        Notify HMR server about file changes.
        
        Args:
            changes: List of file change events
        """
        logger.debug(f"File changes detected: {len(changes)} files")
        
        # Group changes by type
        modified_files = [c.path for c in changes if c.change_type == "modified"]
        created_files = [c.path for c in changes if c.change_type == "created"]
        deleted_files = [c.path for c in changes if c.change_type == "deleted"]
        
        # Notify HMR server
        if self.hmr_server:
            await self._send_hmr_update(modified_files, created_files, deleted_files)
        
        # TODO: Trigger bundler rebuild
        await self._trigger_rebuild(changes)
    
    async def _send_hmr_update(
        self, 
        modified: List[Path], 
        created: List[Path], 
        deleted: List[Path]
    ) -> None:
        """Send HMR update to connected clients."""
        try:
            update_data = {
                "type": "file-change",
                "modified": [str(p) for p in modified],
                "created": [str(p) for p in created],
                "deleted": [str(p) for p in deleted],
                "timestamp": time.time()
            }
            
            await self.hmr_server.broadcast(update_data) # type: ignore
            logger.debug("HMR update sent")
            
        except Exception as e:
            logger.error(f"Failed to send HMR update: {e}")
    
    async def _trigger_rebuild(self, changes: List[FileChangeEvent]) -> None:
        """Trigger bundler rebuild for changed files."""
        # TODO: implement selective rebuild based on changed files
        logger.debug("Triggering rebuild...")


def create_file_watcher(
    project_dir: Path, 
    hmr_server: Optional[Any] = None
) -> FileWatcher:
    """
    Create a file watcher for the project.
    
    Args:
        project_dir: Project directory to watch
        hmr_server: Optional HMR server for notifications
        
    Returns:
        Configured FileWatcher instance
    """
    watch_dirs = []
    
    # Add standard directories to watch
    for dir_name in ["app", "api", "components", "lib", "styles"]:
        dir_path = project_dir / dir_name
        if dir_path.exists():
            watch_dirs.append(dir_path)
    
    return FileWatcher(watch_dirs, hmr_server)


if __name__ == "__main__":
    # Example usage
    async def main():
        project_dir = Path.cwd()
        watcher = create_file_watcher(project_dir)
        
        try:
            await watcher.start()
            print("File watcher started. Press Ctrl+C to stop.")
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("Stopping file watcher...")
            await watcher.stop()
    
    asyncio.run(main())

# Unit tests as comments:
# 1. test_file_watcher_detects_changes() - verify file changes are detected correctly
# 2. test_ignore_patterns() - test that ignored files/directories are skipped
# 3. test_debounce_rapid_changes() - verify rapid changes are debounced properly