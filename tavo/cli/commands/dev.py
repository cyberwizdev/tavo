"""
Tavo Dev Command with Integrated Routing

Run dev server: create ASGI app with routing, start HMR websocket server, start file watcher.
"""

import asyncio
import subprocess
import logging
from pathlib import Path
from typing import Optional
import signal
import sys
import threading

from starlette.applications import Starlette
from starlette.staticfiles import StaticFiles
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, Mount
from starlette.requests import Request
import uvicorn

from ..utils.npm import ensure_node_modules
from tavo.core.hmr.websocket import HMRWebSocketServer
from tavo.core.hmr.watcher import FileWatcher
from tavo.core.utils.bundler import get_bundler_path, BundlerNotFound
from tavo.core.ssr import SSRRenderer
from tavo.core.middleware import TavoMiddleware
from tavo.core.routing import FileBasedRouter

logger = logging.getLogger(__name__)


class DevServer:
    """Development server that creates and manages the complete ASGI application."""
    
    def __init__(self, host: str = "localhost", port: int = 3000, reload: bool = True, verbose: bool = False):
        self.host = host
        self.port = port
        self.reload = reload
        self.verbose = verbose
        self.processes: list[subprocess.Popen] = []
        self.hmr_server: Optional[HMRWebSocketServer] = None
        self.file_watcher: Optional[FileWatcher] = None
        self._shutdown_event = threading.Event()
        
        # Application components
        self.app: Optional[Starlette] = None
        self.ssr_renderer: Optional[SSRRenderer] = None
        self.api_router: Optional[FileBasedRouter] = None
        self.app_router: Optional[FileBasedRouter] = None
        
        # Project paths
        self.project_root = Path.cwd()
        self.app_dir = self.project_root / "app"
        self.api_dir = self.project_root / "api"
        self.public_dir = self.project_root / "public"
        
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
            
            # Create the ASGI application with routing
            await self._create_application()
            
            # Start services
            await self._start_hmr_server()
            await self._start_file_watcher()
            await self._verify_bundler()
            
            # Start the ASGI server
            await self._start_integrated_server()
            
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
        if not ensure_node_modules(self.project_root):
            if self.verbose:
                logger.warning("Node modules not found, run 'tavo install' first")
    
    async def _create_application(self) -> None:
        """Create the complete Starlette application with routing."""
        logger.info("Setting up application routing...")
        
        # Initialize SSR renderer
        self.ssr_renderer = SSRRenderer(app_dir=self.app_dir)
        
        # Initialize routers
        self.api_router = FileBasedRouter(self.api_dir, prefix="/api")
        self.app_router = FileBasedRouter(self.app_dir, renderer=self.ssr_renderer)
        
        # Discover routes
        await self.api_router.discover_routes()
        await self.app_router.discover_routes()
        
        # Create initial routes
        initial_routes: list[Route | Mount] = [
            Route("/health", self._health_check),
            Route("/_routes", self._routes_info),
            Route("/_hmr", self._hmr_endpoint),
        ]
        
        # Add static files if public directory exists
        if self.public_dir.exists():
            initial_routes.extend([
                Mount("/static", StaticFiles(directory=self.public_dir), name="static"),
                Mount("/favicon.ico", StaticFiles(directory=self.public_dir), name="favicon")
            ])
        
        # Create the application
        self.app = Starlette(debug=True, routes=initial_routes)
        
        # Add middleware
        self.app.add_middleware(TavoMiddleware)
        
        # Mount API routes
        if self.api_router.routes:
            api_mount = Mount("/api", self.api_router.get_starlette_routes())
            self.app.router.routes.insert(0, api_mount)
            logger.info(f"Mounted {len(self.api_router.routes)} API routes")
        
        # Add SSR catch-all route LAST
        self.app.router.routes.append(Route("/{path:path}", self._ssr_handler))
        
        # Log route summary
        self._log_routes()
    
    async def _health_check(self, request: Request):
        """Health check endpoint."""
        return JSONResponse({
            "status": "healthy",
            "app": "Tavo Dev Server",
            "routes": {
                "api": len(self.api_router.routes) if self.api_router else 0,
                "pages": len(self.app_router.routes) if self.app_router else 0,
            },
        })
    
    async def _routes_info(self, request: Request):
        """Return detailed route information."""
        try:
            api_routes = []
            page_routes = []
            
            # Get API route info
            if self.api_router:
                api_routes = self.api_router.get_route_info()
            
            # Get page route info
            if self.app_router:
                page_routes = self.app_router.get_route_info()
            
            return JSONResponse({
                "api": api_routes,
                "pages": page_routes,
                "total": len(api_routes) + len(page_routes)
            })
            
        except Exception as e:
            logger.error(f"Error getting route info: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)
    
    async def _hmr_endpoint(self, request: Request):
        """HMR status endpoint."""
        return JSONResponse({
            "hmr": "enabled" if self.reload else "disabled",
            "websocket": f"ws://localhost:{self.port + 1}",
            "bundler_available": self._check_bundler_available(),
        })
    
    async def _not_found(self, request: Request):
        """Catch-all 404 handler."""
        return JSONResponse({"error": "Route not found"}, status_code=404)
    
    async def _ssr_handler(self, request: Request):
        """SSR catch-all handler for page routes."""
        path = request.url.path
        
        # Skip API routes
        if path.startswith('/api/'):
            return JSONResponse({"error": "Route not found"}, status_code=404)
        
        try:
            # Check if the corresponding page file exists
            page_file_path = self._get_page_file_path(path)
            if not page_file_path:
                # No matching page file found, return 404
                return HTMLResponse(content=self._get_not_found_html(path), status_code=404)
            
            # Find matching route
            route_match = self.app_router.match_route(path) if self.app_router else None
            
            # Prepare SSR context
            ssr_context = {
                "url": str(request.url),
                "method": request.method,
                "headers": dict(request.headers),
                "query_params": dict(request.query_params),
                "route_params": route_match.params if route_match else {},
                "development": True,
                "hmr_port": self.port + 1 if self.reload else None,
                "page_file": str(page_file_path),
            }
            
            # Render the route
            if self.ssr_renderer:
                html_content = await self.ssr_renderer.render_route(path, ssr_context)
                return HTMLResponse(content=html_content)
            else:
                # Fallback HTML
                fallback_html = self._get_fallback_html(path)
                return HTMLResponse(content=fallback_html)
                
        except Exception as e:
            logger.error(f"SSR error for path '{path}': {e}")
            fallback_html = self._get_fallback_html(path, error=str(e))
            return HTMLResponse(content=fallback_html, status_code=500)

    def _get_page_file_path(self, path: str) -> Optional[Path]:
        """
        Check if a page file exists for the given path.
        Only looks for page.tsx or page.jsx files.
        
        Args:
            path: The request path (e.g., "/", "/about", "/users/123")
        
        Returns:
            Path to the page file if it exists, None otherwise
        """
        logger.debug(f"Checking page file path for route: {path}")
        logger.debug(f"App directory: {self.app_dir}")
        logger.debug(f"App directory exists: {self.app_dir.exists()}")
        
        if not self.app_dir.exists():
            logger.debug("App directory does not exist")
            return None
        
        # List contents of app directory for debugging
        if self.app_dir.exists():
            app_contents = list(self.app_dir.iterdir())
            logger.debug(f"App directory contents: {[f.name for f in app_contents]}")
        
        # Normalize path
        clean_path = path.strip('/')
        logger.debug(f"Clean path: '{clean_path}'")
        
        # Handle root path
        if not clean_path:
            # Check for app/page.tsx or app/page.jsx
            for filename in ['page.tsx', 'page.jsx']:
                page_file = self.app_dir / filename
                logger.debug(f"Checking root page file: {page_file}")
                logger.debug(f"Root page file exists: {page_file.exists()}")
                if page_file.exists():
                    logger.debug(f"Found root page file: {page_file}")
                    return page_file
            logger.debug("No root page file found")
            return None
        
        # Handle nested paths (e.g., "/about" -> "app/about/page.tsx")
        path_parts = clean_path.split('/')
        logger.debug(f"Path parts: {path_parts}")
        
        # Only check for page.tsx and page.jsx in the directory structure
        for extension in ['tsx', 'jsx']:
            page_file = self.app_dir
            for part in path_parts:
                page_file = page_file / part
            page_file = page_file / f'page.{extension}'
            
            logger.debug(f"Checking nested page file: {page_file}")
            logger.debug(f"Nested page file exists: {page_file.exists()}")
            if page_file.exists():
                logger.debug(f"Found nested page file: {page_file}")
                return page_file
        
        logger.debug("No page file found for path")
        return None

    def _get_not_found_html(self, path: str = "/") -> str:
        """Generate a proper 404 Not Found HTML page."""
        hmr_script = ""
        if self.reload:
            hmr_script = f"""
    <script>
    // HMR WebSocket connection
    const ws = new WebSocket('ws://localhost:{self.port + 1}');
    ws.onmessage = (event) => {{
        const data = JSON.parse(event.data);
        if (data.type === 'reload') {{
        window.location.reload();
        }}
    }};
    </script>"""
        
        return f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>404 - Page Not Found | Tavo App</title>
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                margin: 0; padding: 2rem; background: #f5f5f5;
                display: flex; align-items: center; justify-content: center;
                min-height: 100vh;
            }}
            .container {{ 
                max-width: 500px; background: white; 
                padding: 3rem 2rem; border-radius: 12px; 
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                text-align: center;
            }}
            .error-code {{
                font-size: 4rem; font-weight: bold; 
                color: #dc2626; margin: 0;
            }}
            .error-title {{
                font-size: 1.5rem; color: #374151;
                margin: 0.5rem 0 1rem 0;
            }}
            .error-message {{
                color: #6b7280; margin-bottom: 2rem;
                line-height: 1.6;
            }}
            .path-info {{
                background: #f3f4f6; padding: 0.75rem 1rem;
                border-radius: 6px; font-family: 'Courier New', monospace;
                font-size: 0.9rem; color: #374151;
                word-break: break-all; margin: 1rem 0;
            }}
            .suggestions {{
                text-align: left; background: #fefce8;
                padding: 1rem; border-radius: 6px;
                border-left: 4px solid #eab308;
            }}
            .suggestions h4 {{
                margin: 0 0 0.5rem 0; color: #92400e;
            }}
            .suggestions ul {{
                margin: 0; padding-left: 1.2rem;
                color: #92400e;
            }}
            .suggestions li {{
                margin: 0.25rem 0;
            }}
            .home-link {{
                display: inline-block; margin-top: 2rem;
                padding: 0.75rem 1.5rem; background: #3b82f6;
                color: white; text-decoration: none;
                border-radius: 6px; transition: background 0.2s;
            }}
            .home-link:hover {{
                background: #2563eb;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="error-code">404</h1>
            <h2 class="error-title">Page Not Found</h2>
            <p class="error-message">
                The page you're looking for doesn't exist or hasn't been created yet.
            </p>
            
            <div class="path-info">
                Requested path: {path}
            </div>
            
            <div class="suggestions">
                <h4>To create this page:</h4>
                <ul>
                    <li>Create <code>app{path if path != '/' else ''}/page.tsx</code> or <code>app{path if path != '/' else ''}/page.jsx</code></li>
                    <li>Make sure the file exports a React component as default</li>
                </ul>
            </div>
            
            <a href="/" class="home-link">← Back to Home</a>
            
            <div id="root"></div>
        </div>
        {hmr_script}
    </body>
    </html>"""    
    def _get_fallback_html(self, path: str = "/", error: Optional[str] = None) -> str:
        """Generate fallback HTML when SSR fails."""
        hmr_script = ""
        if self.reload:
            hmr_script = f"""
<script>
  // HMR WebSocket connection
  const ws = new WebSocket('ws://localhost:{self.port + 1}');
  ws.onmessage = (event) => {{
    const data = JSON.parse(event.data);
    if (data.type === 'reload') {{
      window.location.reload();
    }}
  }};
</script>"""
        
        error_message = f"<p>Error: {error}</p>" if error else ""
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tavo App - {path}</title>
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 0; padding: 2rem; background: #f5f5f5;
        }}
        .container {{ 
            max-width: 600px; margin: 0 auto; background: white; 
            padding: 2rem; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .error {{ color: #dc2626; background: #fef2f2; padding: 1rem; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Tavo Development Server</h1>
        <p>Route: <code>{path}</code></p>
        {error_message}
        <p>SSR not available - using fallback HTML</p>
        <div id="root"></div>
    </div>
    {hmr_script}
</body>
</html>"""
    
    async def _start_hmr_server(self) -> None:
        """Start HMR WebSocket server."""
        if not self.reload:
            return
            
        hmr_port = self.port + 1
        self.hmr_server = HMRWebSocketServer(port=hmr_port)
        await self.hmr_server.start()
        
        logger.info(f"HMR server started on ws://localhost:{hmr_port}")
    
    async def _start_file_watcher(self) -> None:
        """Start file watcher for HMR."""
        if not self.reload:
            return
        
        watch_dirs = []
        if self.app_dir.exists():
            watch_dirs.append(self.app_dir)
        if self.api_dir.exists():
            watch_dirs.append(self.api_dir)
        
        if watch_dirs:
            self.file_watcher = FileWatcher(
                watch_dirs=watch_dirs,
                hmr_server=self.hmr_server
            )
            await self.file_watcher.start()
            logger.info(f"File watcher started for {len(watch_dirs)} directories")
    
    def _check_bundler_available(self) -> bool:
        """Check if the Rust bundler binary is available."""
        try:
            get_bundler_path()
            return True
        except BundlerNotFound:
            return False
    
    async def _verify_bundler(self) -> None:
        """Verify bundler availability."""
        bundler_available = self._check_bundler_available()
        
        if bundler_available:
            bundler_path = get_bundler_path()
            logger.info(f"Rust bundler available at: {bundler_path}")
        else:
            logger.warning("Rust bundler not found - using fallback HTML for SSR routes")
    
    async def _start_integrated_server(self) -> None:
        """Start the integrated ASGI server."""
        if not self.app:
            raise RuntimeError("Application not created")
        
        logger.info(f"Development server starting on http://{self.host}:{self.port}")
        logger.info(f"Hot reload: {'enabled' if self.reload else 'disabled'}")
        
        # Create uvicorn config
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info" if self.verbose else "warning",
            access_log=self.verbose,
        )
        
        # Start server
        server = uvicorn.Server(config)
        
        # Set up signal handlers
        def signal_handler(signum, frame):
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            await server.serve()
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
    
    def _log_routes(self) -> None:
        """Log registered routes."""
        if not self.verbose:
            return
            
        logger.info("Registered routes:")
        
        if self.app:
            for route in self.app.routes:
                if isinstance(route, Route):
                    methods = list(route.methods) if route.methods else ["GET"]
                    logger.info(f"  {route.path} [{', '.join(methods)}]")
                elif isinstance(route, Mount):
                    logger.info(f"  Mount: {route.path}")
                    if hasattr(route, 'routes'):
                        for sub_route in route.routes:
                            if isinstance(sub_route, Route):
                                methods = list(sub_route.methods) if sub_route.methods else ["GET"]
                                logger.info(f"    {sub_route.path} [{', '.join(methods)}]")


def start_dev_server(
    host: str = "localhost", 
    port: int = 3000, 
    reload: bool = True, 
    verbose: bool = False
) -> None:
    """
    Start the development server with integrated routing.
    
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
    
    # Check for app or api directory
    has_app = (project_dir / "app").exists()
    has_api = (project_dir / "api").exists()
    
    if not (has_app or has_api):
        logger.error("Neither app/ nor api/ directory found - not a Tavo project?")
        return False
    
    return True


if __name__ == "__main__":
    # Example usage
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    if check_dev_requirements():
        start_dev_server(verbose=verbose)
    else:
        logger.error("Development requirements not met")