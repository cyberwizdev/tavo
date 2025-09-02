"""
Tavo Dev Command

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
import shutil
import os

from ..utils.npm import ensure_node_modules
from tavo.core.hmr.websocket import HMRWebSocketServer
from tavo.core.hmr.watcher import FileWatcher
from tavo.core.utils.bundler import get_bundler_path, BundlerNotFound

logger = logging.getLogger(__name__)


class DevServer:
    """Development server coordinator that manages multiple processes."""
    
    def __init__(self, host: str = "localhost", port: int = 3000, reload: bool = True, verbose: bool = False):
        self.host = host
        self.port = port
        self.reload = reload
        self.verbose = verbose
        self.processes: list[subprocess.Popen] = []
        self.hmr_server: Optional[HMRWebSocketServer] = None
        self.file_watcher: Optional[FileWatcher] = None
        self._shutdown_event = threading.Event()
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure logging levels based on verbose mode."""
        if self.verbose:
            logging.getLogger("tavo").setLevel(logging.DEBUG)
        else:
            # Reduce noise in production mode
            logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
            logging.getLogger("watchfiles").setLevel(logging.WARNING)
    
    async def start(self) -> None:
        """Start all development services."""
        try:
            logger.info("Starting Tavo development server...")
            
            # Ensure dependencies are installed
            await self._ensure_dependencies()
            
            # Start services
            await self._start_hmr_server()
            await self._start_file_watcher()
            await self._start_bundler_watch()
            await self._start_asgi_server()
            
            # Log server info and route summary
            await self._log_server_status()
            
            # Wait for shutdown signal
            await self._wait_for_shutdown()
            
        except Exception as e:
            logger.error(f"Failed to start dev server: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop all development services."""
        logger.info("Shutting down development server...")
        
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
        logger.info("Development server stopped")
    
    async def _ensure_dependencies(self) -> None:
        """Ensure Node.js dependencies are installed."""
        project_dir = Path.cwd()
        if not ensure_node_modules(project_dir):
            if self.verbose:
                logger.warning("Node modules not found, run 'tavo install' first")
    
    async def _start_hmr_server(self) -> None:
        """Start HMR WebSocket server."""
        hmr_port = self.port + 1
        self.hmr_server = HMRWebSocketServer(port=hmr_port)
        await self.hmr_server.start()
        
        if self.verbose:
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
        
        if self.verbose:
            logger.info("File watcher started")
    
    def _check_bundler_available(self) -> bool:
        """Check if the Rust bundler binary is available."""
        try:
            get_bundler_path()
            return True
        except BundlerNotFound:
            return False
    
    async def _start_bundler_watch(self) -> None:
        """Start Rust bundler in development mode."""
        try:
            bundler_path = get_bundler_path()
        except BundlerNotFound as e:
            if self.verbose:
                logger.warning(str(e))
                logger.warning("Running without asset bundling")
            return

        try:
            # Use the SSR bundler with appropriate arguments for development
            # This will compile routes for hydration mode
            project_dir = Path.cwd()
            app_dir = project_dir / "app"
            
            if not app_dir.exists():
                logger.warning("No app directory found, skipping bundler")
                return
            
            # For development, we'll run the bundler on-demand rather than in watch mode
            # since the current bundler doesn't have a watch mode implemented
            cmd = [
                str(bundler_path), 
                "--route", "/",  # Default route for now
                "--app-dir", str(app_dir),
                "--compile-type", "hydration",
                "--output", "json"
            ]
            
            # Test run the bundler to ensure it works
            process = subprocess.Popen(
                cmd,
                cwd=project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # Wait for initial compilation
            stdout, _ = process.communicate(timeout=30)
            
            if process.returncode == 0:
                if self.verbose:
                    logger.info(f"Rust bundler test compilation successful")
                    logger.debug(f"Bundler output: {stdout}")
            else:
                logger.warning(f"Bundler test failed: {stdout}")
                return
                
            # In a real implementation, you'd want to integrate this with file watching
            # For now, we'll just verify the bundler works
            if self.verbose:
                logger.info(f"Rust bundler available at: {bundler_path}")

        except subprocess.TimeoutExpired:
            logger.warning("Bundler test compilation timed out")
            process.kill()
        except Exception as e:
            logger.warning(f"Failed to test Rust bundler: {e}")
            if self.verbose:
                logger.warning("Continuing without asset bundling...")

    def _monitor_bundler_output(self, process: subprocess.Popen) -> None:
        """Log bundler output if verbose mode is on."""
        if not process.stdout:
            return
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            if self.verbose:
                logger.info(f"Bundler: {line.strip()}")

    async def _start_asgi_server(self) -> None:
        """Start Python ASGI development server."""
        project_dir = Path.cwd()
        main_module = "main:app"
        
        if (project_dir / "backend" / "main.py").exists():
            main_module = "backend.main:app"
        elif not (project_dir / "main.py").exists():
            logger.error("No main.py found in project root or backend/ directory")
            raise FileNotFoundError("ASGI application entry point not found")
        
        # Set environment variable to enable route logging
        env = os.environ.copy()
        env["TAVO_LOG_ROUTES"] = "1"
        
        cmd = [
            sys.executable, "-m", "uvicorn",
            main_module,
            "--host", self.host,
            "--port", str(self.port),
            "--log-level", "warning",  # Reduce uvicorn noise
        ]
        
        if self.reload:
            cmd.append("--reload")
        
        process = subprocess.Popen(
            cmd,
            cwd=project_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        self.processes.append(process)
        
        # Monitor ASGI server output for route information
        threading.Thread(target=self._monitor_asgi_output, args=(process,), daemon=True).start()
    
    def _monitor_asgi_output(self, process: subprocess.Popen) -> None:
        """Monitor ASGI server output and extract route information."""
        if not process.stdout:
            return
        
        routes_logged = False
        
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            
            line = line.strip()
            
            # Look for application startup complete
            if "Application startup complete" in line and not routes_logged:
                routes_logged = True
                # Give the app a moment to finish startup
                time.sleep(0.5)
                self._fetch_and_log_routes()
            
            # Log important messages
            if any(keyword in line.lower() for keyword in ["error", "warning", "started", "listening"]):
                if self.verbose or "error" in line.lower():
                    logger.info(f"ASGI: {line}")
    
    def _fetch_and_log_routes(self) -> None:
        """Fetch route information from the running server and log it."""
        try:
            import requests
            response = requests.get(f"http://{self.host}:{self.port}/health", timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                api_count = data.get("routes", {}).get("api", 0)
                page_count = data.get("routes", {}).get("pages", 0)
                
                logger.info(f"Server ready at http://{self.host}:{self.port}")
                logger.info(f"Routes: {api_count} API endpoints, {page_count} pages")
                
                # Try to get detailed route info if available
                self._log_detailed_routes()
                
        except Exception as e:
            if self.verbose:
                logger.debug(f"Could not fetch route info: {e}")
    
    def _log_detailed_routes(self) -> None:
        """Log detailed route information."""
        try:
            import requests
            
            # Try to get route details (this would need to be implemented in main.py)
            response = requests.get(f"http://{self.host}:{self.port}/_routes", timeout=1)
            
            if response.status_code == 200:
                routes = response.json()
                
                logger.info("Registered routes:")
                for route in routes.get("api", []):
                    methods = ", ".join(route.get("methods", ["GET"]))
                    logger.info(f"  API  {route['path']} [{methods}]")
                
                for route in routes.get("pages", []):
                    logger.info(f"  PAGE {route['path']}")
                    
        except Exception:
            # Silently fail - detailed routes are optional
            pass
    
    async def _log_server_status(self) -> None:
        """Log server status and configuration."""
        bundler_status = check_bundler_status()
        
        logger.info(f"Development server starting on http://{self.host}:{self.port}")
        
        if bundler_status["available"]:
            logger.info(f"Asset bundling: enabled ({bundler_status['type']})")
        else:
            logger.info("Asset bundling: disabled (bundler not found)")
        
        logger.info(f"Hot reload: {'enabled' if self.reload else 'disabled'}")
        
        if not self.verbose:
            logger.info("Use --verbose for detailed logging")
    
    async def _wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        def signal_handler(signum, frame):
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Wait for shutdown event
        while not self._shutdown_event.is_set():
            await asyncio.sleep(0.1)


def start_dev_server(
    host: str = "localhost", 
    port: int = 3000, 
    reload: bool = True, 
    verbose: bool = False
) -> None:
    """
    Start the development server with all services.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload and HMR
        verbose: Enable verbose logging
    """
    dev_server = DevServer(host, port, reload, verbose)
    
    try:
        asyncio.run(dev_server.start())
    except KeyboardInterrupt:
        logger.info("Development server stopped")
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
    
    # Check for main.py (ASGI app) in root or backend/
    main_py_locations = [
        project_dir / "main.py",
        project_dir / "backend" / "main.py"
    ]
    
    if not any(loc.exists() for loc in main_py_locations):
        logger.error("main.py not found - not a Tavo project?")
        return False
    
    # Check for app directory
    if not (project_dir / "app").exists():
        logger.error("app/ directory not found")
        return False
    
    return True


def check_bundler_status() -> dict:
    """Check bundler availability and return status info."""
    try:
        path = get_bundler_path()
        return {
            "available": True,
            "location": str(path),
            "type": "local",
        }
    except BundlerNotFound:
        return {
            "available": False,
            "location": None,
            "type": None,
        }


if __name__ == "__main__":
    # Example usage
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    if check_dev_requirements():
        bundler_status = check_bundler_status()
        
        if verbose:
            if bundler_status["available"]:
                print(f"Rust bundler found: {bundler_status['location']}")
            else:
                print("Rust bundler not found - will run without asset bundling")
        
        start_dev_server(verbose=verbose)
    else:
        logger.error("Development requirements not met")

# Unit tests as comments:
# 1. test_dev_server_startup() - verify all services start correctly
# 2. test_dev_server_shutdown() - test graceful shutdown of all processes
# 3. test_check_dev_requirements() - verify project structure validation
# 4. test_bundler_detection() - test bundler binary detection
# 5. test_fallback_mode() - test running without bundler
# 6. test_verbose_mode() - test verbose vs quiet logging modes