"""
Bino Dev Command

Run dev server: start Python ASGI app, start rust_bundler in watch mode, start HMR websocket server.
"""

import asyncio
import subprocess
import logging
from pathlib import Path
from typing import Optional
import signal
import sys
import threading
import time

from ..utils.npm import ensure_node_modules
from tavo_core.hmr.websocket import HMRWebSocketServer
from tavo_core.hmr.watcher import FileWatcher
from tavo_core.bundler import start_watch_mode

logger = logging.getLogger(__name__)


class DevServer:
    """Development server coordinator that manages multiple processes."""
    
    def __init__(self, host: str = "localhost", port: int = 3000, reload: bool = True):
        self.host = host
        self.port = port
        self.reload = reload
        self.processes: list[subprocess.Popen] = []
        self.hmr_server: Optional[HMRWebSocketServer] = None
        self.file_watcher: Optional[FileWatcher] = None
        self._shutdown_event = threading.Event()
    
    async def start(self) -> None:
        """Start all development services."""
        try:
            # Ensure dependencies are installed
            await self._ensure_dependencies()
            
            # Start HMR WebSocket server
            await self._start_hmr_server()
            
            # Start file watcher
            await self._start_file_watcher()
            
            # Start Rust bundler in watch mode
            await self._start_bundler_watch()
            
            # Start Python ASGI server
            await self._start_asgi_server()
            
            logger.info(f"🚀 Dev server running at http://{self.host}:{self.port}")
            logger.info("Press Ctrl+C to stop")
            
            # Wait for shutdown signal
            await self._wait_for_shutdown()
            
        except Exception as e:
            logger.error(f"Failed to start dev server: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop all development services."""
        logger.info("Stopping development server...")
        
        # Stop file watcher
        if self.file_watcher:
            await self.file_watcher.stop()
        
        # Stop HMR server
        if self.hmr_server:
            await self.hmr_server.stop()
        
        # Terminate subprocesses
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        
        self._shutdown_event.set()
    
    async def _ensure_dependencies(self) -> None:
        """Ensure Node.js dependencies are installed."""
        project_dir = Path.cwd()
        if not ensure_node_modules(project_dir):
            logger.warning("Node modules not found, run 'tavo install' first")
    
    async def _start_hmr_server(self) -> None:
        """Start HMR WebSocket server."""
        hmr_port = self.port + 1
        self.hmr_server = HMRWebSocketServer(port=hmr_port)
        await self.hmr_server.start()
        logger.info(f"HMR server started on port {hmr_port}")
    
    async def _start_file_watcher(self) -> None:
        """Start file watcher for HMR."""
        if not self.reload:
            return
        
        project_dir = Path.cwd()
        self.file_watcher = FileWatcher(
            watch_dirs=[project_dir / "app", project_dir / "api"],
            hmr_server=self.hmr_server
        )
        await self.file_watcher.start()
        logger.info("File watcher started")
    
    async def _start_bundler_watch(self) -> None:
        """Start Rust bundler in watch mode."""
        # TODO: implement actual rust bundler invocation
        logger.info("Starting Rust bundler in watch mode...")
        # This would call the rust_bundler binary with watch command
        # await start_watch_mode()
    
    async def _start_asgi_server(self) -> None:
        """Start Python ASGI development server."""
        cmd = [
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", self.host,
            "--port", str(self.port),
            "--reload" if self.reload else "--no-reload"
        ]
        
        process = subprocess.Popen(
            cmd,
            cwd=Path.cwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        self.processes.append(process)
        logger.info("ASGI server started")
    
    async def _wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Wait for shutdown event
        while not self._shutdown_event.is_set():
            await asyncio.sleep(0.1)


def start_dev_server(host: str = "localhost", port: int = 3000, reload: bool = True) -> None:
    """
    Start the development server with all services.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload and HMR
    """
    dev_server = DevServer(host, port, reload)
    
    try:
        asyncio.run(dev_server.start())
    except KeyboardInterrupt:
        logger.info("Development server stopped by user")
    except Exception as e:
        logger.error(f"Development server error: {e}")
        raise


def check_dev_requirements() -> bool:
    """
    Check if development requirements are met.
    
    Returns:
        True if all requirements are satisfied
    """
    project_dir = Path.cwd()
    
    # Check for main.py (ASGI app)
    if not (project_dir / "main.py").exists():
        logger.error("main.py not found - not a Bino project?")
        return False
    
    # Check for app directory
    if not (project_dir / "app").exists():
        logger.error("app/ directory not found")
        return False
    
    # TODO: Check for rust bundler binary
    
    return True


if __name__ == "__main__":
    # Example usage
    if check_dev_requirements():
        print("Starting development server...")
        start_dev_server()
    else:
        print("❌ Development requirements not met")

# Unit tests as comments:
# 1. test_dev_server_startup() - verify all services start correctly
# 2. test_dev_server_shutdown() - test graceful shutdown of all processes
# 3. test_check_dev_requirements() - verify project structure validation