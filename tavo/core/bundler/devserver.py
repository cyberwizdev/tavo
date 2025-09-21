"""
Development server with hot reloading support
"""

import subprocess
import json
import logging
import time
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List, Set
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import threading

from .compiler import SWCCompiler
from .resolver import ImportResolver
from .templates import TemplateManager
from .constants import DEFAULT_DEV_PORT, HMR_WEBSOCKET_PATH
from .utils import write_file_atomic, safe_mkdir

logger = logging.getLogger(__name__)


class HMRWebSocketHandler:
    """Simple WebSocket handler for HMR"""
    
    def __init__(self):
        self.clients: Set[Any] = set()
    
    def add_client(self, client):
        """Add WebSocket client"""
        self.clients.add(client)
        logger.debug(f"HMR client connected. Total: {len(self.clients)}")
    
    def remove_client(self, client):
        """Remove WebSocket client"""
        self.clients.discard(client)
        logger.debug(f"HMR client disconnected. Total: {len(self.clients)}")
    
    def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.clients:
            return
        
        message_str = json.dumps(message)
        disconnected_clients = set()
        
        for client in self.clients:
            try:
                # This is a placeholder - in production would use actual WebSocket library
                # For now just log the message that would be sent
                logger.debug(f"Broadcasting HMR message: {message_str}")
            except Exception as e:
                logger.warning(f"Failed to send HMR message to client: {e}")
                disconnected_clients.add(client)
        
        # Remove disconnected clients
        self.clients -= disconnected_clients


class DevServer:
    """Development server with hot reloading"""
    
    def __init__(self, project_root: Path, compiler: SWCCompiler, resolver: ImportResolver):
        self.project_root = Path(project_root).resolve()
        self.compiler = compiler
        self.resolver = resolver
        self.templates = TemplateManager(project_root)
        
        self.hmr_handler = HMRWebSocketHandler()
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.change_callbacks: List[Callable] = []
        
        # State
        self.is_running = False
        self._last_rebuild_time = 0
        self._rebuild_debounce = 0.5  # seconds
    
    def add_change_callback(self, callback: Callable):
        """Add callback for file change events"""
        self.change_callbacks.append(callback)
    
    def on_change(self, callback: Callable):
        """Decorator for change callbacks"""
        self.add_change_callback(callback)
        return callback
    
    def start(self, port: int = DEFAULT_DEV_PORT, host: str = "localhost") -> None:
        """Start the development server"""
        if self.is_running:
            logger.warning("Dev server is already running")
            return
        
        logger.info(f"Starting development server on http://{host}:{port}")
        
        # Create request handler with reference to this server
        def handler_factory(*args, **kwargs):
            return DevRequestHandler(*args, dev_server=self, **kwargs)
        
        try:
            self.server = HTTPServer((host, port), handler_factory)
            self.is_running = True
            
            # Start server in thread
            self.server_thread = threading.Thread(
                target=self.server.serve_forever,
                daemon=True
            )
            self.server_thread.start()
            
            logger.info(f"Development server started successfully on http://{host}:{port}")
            
            # Initial build
            self._initial_build()
            
            # Setup file watching (placeholder - would integrate with actual file watcher)
            self._setup_file_watching()
            
            # Keep main thread alive
            try:
                while self.is_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down development server...")
                self.stop()
            
        except Exception as e:
            logger.error(f"Failed to start development server: {e}")
            self.is_running = False
            raise
    
    def stop(self) -> None:
        """Stop the development server"""
        if not self.is_running:
            return
        
        logger.info("Stopping development server...")
        
        self.is_running = False
        
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5.0)
        
        logger.info("Development server stopped")
    
    def _initial_build(self) -> None:
        """Perform initial build of all routes"""
        logger.info("Performing initial build...")
        
        try:
            routes = self.resolver.resolve_routes()
            built_count = 0
            
            for route in routes:
                try:
                    # Compile for both client and server
                    route_files = list(route.all_files)
                    
                    self.compiler.compile_for_hydration(files=route_files, path=route.route_path)
                    self.compiler.compile_for_ssr(route_files, path=route.route_path)
                    
                    built_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to build route {route.route_path}: {e}")
            
            logger.info(f"Initial build completed: {built_count}/{len(routes)} routes")
            
        except Exception as e:
            logger.error(f"Initial build failed: {e}")
    
    def _setup_file_watching(self) -> None:
        """Setup file watching for hot reloading"""
        # This is a placeholder - in production would integrate with
        # existing watchdog implementation from tavo
        logger.info("File watching setup (placeholder - integrate with tavo watchdog)")
    
    def handle_file_change(self, changed_files: List[Path]) -> None:
        """Handle file change events"""
        current_time = time.time()
        
        # Debounce rapid file changes
        if current_time - self._last_rebuild_time < self._rebuild_debounce:
            return
        
        self._last_rebuild_time = current_time
        
        logger.info(f"Files changed: {[str(f) for f in changed_files]}")
        
        try:
            # Find affected routes
            affected_routes = self._find_affected_routes(changed_files)
            
            if not affected_routes:
                logger.debug("No routes affected by file changes")
                return
            
            # Rebuild affected routes
            rebuilt_routes = []
            for route in affected_routes:
                try:
                    route_files = list(route.all_files)
                    
                    # Recompile
                    client_result = self.compiler.compile_for_hydration(path=route.route_path, files=route_files)
                    server_result = self.compiler.compile_for_ssr(files=route_files, path=route.route_path)
                    
                    rebuilt_routes.append({
                        "route": route.route_path,
                        "client_cache_hit": client_result.cache_hit,
                        "server_cache_hit": server_result.cache_hit
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to rebuild route {route.route_path}: {e}")
            
            # Notify HMR clients
            if rebuilt_routes:
                hmr_message = {
                    "type": "update",
                    "timestamp": current_time,
                    "routes": rebuilt_routes
                }
                self.hmr_handler.broadcast(hmr_message)
            
            # Call change callbacks
            for callback in self.change_callbacks:
                try:
                    callback(changed_files)
                except Exception as e:
                    logger.error(f"Change callback failed: {e}")
            
            logger.info(f"Hot reload completed: {len(rebuilt_routes)} routes updated")
            
        except Exception as e:
            logger.error(f"Failed to handle file changes: {e}")
    
    def _find_affected_routes(self, changed_files: List[Path]) -> List:
        """Find routes affected by changed files"""
        routes = self.resolver.resolve_routes()
        affected = []
        
        changed_file_strs = {str(f) for f in changed_files}
        
        for route in routes:
            route_file_strs = {str(f) for f in route.all_files}
            
            if changed_file_strs & route_file_strs:
                affected.append(route)
        
        return affected
    
    def render_route(self, path: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Render a route with SSR and attach hydration script"""
        try:
            routes = self.resolver.resolve_routes()

            # Find matching route
            matching_route = None
            for route_entry in routes:
                if route_entry.route_path == path or (path == "/" and route_entry.route_path == "/"):
                    matching_route = route_entry
                    break

            if not matching_route:
                return self.render_error_page(f"Route not found: {path}")

            # Compile route for both SSR + Hydration
            route_files = list(matching_route.all_files)
            logger.info(f"Compiling {matching_route.route_path} for SSR + Hydration")
            outputs = self.compiler.compile_for_ssr_and_hydration(route_files, matching_route.route_path)

            ssr_compiled_js = outputs["ssr"].compiled_js
            hydration_compiled_js = outputs["hydration"].compiled_js

            # Prepare for SSR execution
            ssr_html_content = ""
            serialized_context = json.dumps(context) if context else "{}"

            safe_mkdir(self.compiler.debug_dir)
            safe_filename = path.replace('/', '_').strip('_') or 'index'

            # Write SSR JS into temp file
            ssr_temp_file = self.compiler.debug_dir / f"ssr_entry__{safe_filename}.cjs"
            write_file_atomic(ssr_temp_file, ssr_compiled_js)
            ssr_temp_file_uri = ssr_temp_file.as_uri()

            # Node executor for SSR
            ssr_executor_script = f"""
    import React from 'react';
    import ReactDOMServer from 'react-dom/server';
    import * as Component from '{ssr_temp_file_uri}';

    const initialProps = JSON.parse(process.argv[2] || '{{}}');

    try {{
        const element = React.createElement(Component.default, initialProps);
        const html = ReactDOMServer.renderToString(element);
        console.log(html);
    }} catch (e) {{
        console.error(JSON.stringify({{ message: e.message, stack: e.stack }}));
        process.exit(1);
    }}
    """
            ssr_executor_temp_file = self.compiler.debug_dir / "ssr_executor.mjs"
            write_file_atomic(ssr_executor_temp_file, ssr_executor_script)

            # Run Node SSR
            try:
                node_command = ["node", str(ssr_executor_temp_file), serialized_context]
                logger.debug(f"Executing Node.js SSR: {' '.join(node_command)}")

                ssr_process = subprocess.run(
                    node_command,
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=self.project_root,
                    encoding='utf-8',
                    timeout=10
                )
                ssr_html_content = ssr_process.stdout.strip()

                if ssr_process.stderr:
                    logger.warning(f"Node.js SSR stderr: {ssr_process.stderr.strip()}")

            except subprocess.CalledProcessError as e:
                logger.error(f"Node.js SSR execution failed (code {e.returncode}): {e.stderr.strip()}")
                ssr_html_content = ""
            except subprocess.TimeoutExpired:
                logger.error("Node.js SSR execution timed out.")
                ssr_html_content = ""
            except FileNotFoundError:
                logger.error("Node.js not found. Cannot perform SSR execution.")
                ssr_html_content = ""
            except Exception as e:
                logger.error(f"Unexpected error during Node.js SSR execution: {e}")
                ssr_html_content = ""

            # Render HTML with template engine
            html = self.templates.render_html(
                ssr_html=ssr_html_content,
                state=context if context else {},
                hydration_compiled_js=hydration_compiled_js
            )

            # Inject HMR in dev
            html = self.templates.inject_hmr_script(html)
            return html

        except Exception as e:
            logger.exception(f"Error serving route {path}: {e}")
            return self.render_error_page(str(e))

    def render_error_page(self, error_message: str) -> str:
        """Render error page"""
        return self.templates.render_error_page(error_message)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get development server statistics"""
        return {
            "is_running": self.is_running,
            "hmr_clients": len(self.hmr_handler.clients),
            "compiler_stats": self.compiler.get_compilation_stats(),
            "routes_count": len(self.resolver.resolve_routes()),
            "last_rebuild_time": self._last_rebuild_time
        }
    

class DevRequestHandler(SimpleHTTPRequestHandler):
    """Custom request handler for development server"""
    
    def __init__(self, *args, dev_server: Optional[DevServer] =None, **kwargs):
        self.dev_server = dev_server
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        
        # Handle HMR WebSocket upgrade (simplified)
        if parsed_path.path == HMR_WEBSOCKET_PATH:
            self.handle_hmr_connection()
            return
        
        # Handle static files and routes
        if parsed_path.path.startswith('/dist/'):
            # Serve built files
            self.serve_built_file(parsed_path.path)
        elif parsed_path.path.startswith('/public/'):
            # Serve public assets
            self.serve_public_file(parsed_path.path)
        else:
            # Serve route
            self.serve_route(parsed_path.path)
    
    def handle_hmr_connection(self):
        """Handle HMR WebSocket connection"""
        # In production, this would upgrade the connection to WebSocket
        # For now, just acknowledge
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'HMR connection acknowledged')
    
    def serve_built_file(self, path: str):
        """Serve built JavaScript files"""
        if not self.dev_server:
            self.send_error(500, "Dev server not available")
            return
        
        try:
            file_path = self.dev_server.project_root / path[1:]  # Remove leading slash
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/javascript')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
            else:
                self.send_error(404, f"File not found: {path}")
        except Exception as e:
            logger.error(f"Error serving built file {path}: {e}")
            self.send_error(500, str(e))
    
    def serve_public_file(self, path: str):
        """Serve public assets"""
        try:
            # Remove /public/ prefix and serve from public directory
            relative_path = path[8:]  # Remove '/public/'
            file_path = self.dev_server.project_root / "public" / relative_path # type: ignore
            
            if file_path.exists() and file_path.is_file():
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                # Determine content type
                content_type = self.guess_type(str(file_path))
                
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Cache-Control', 'public, max-age=3600')
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, f"Public file not found: {path}")
        except Exception as e:
            logger.error(f"Error serving public file {path}: {e}")
            self.send_error(500, str(e))
    
    def serve_route(self, path: str):
        """Serve route with SSR"""
        if not self.dev_server:
            self.send_error(500, "Dev server not available")
            return
        
        try:
            html_content = self.dev_server.render_route(path)
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(html_content.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error serving route {path}: {e}")
            error_html = self.dev_server.render_error_page(str(e))
            
            self.send_response(500)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(error_html.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"HTTP {format % args}")
