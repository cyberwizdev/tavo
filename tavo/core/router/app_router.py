"""
Tavo App Router

SSR route handler for /app — receives request path and delegates to SSR renderer.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route, Router
import json

from ..ssr import SSRRenderer

logger = logging.getLogger(__name__)


class AppRouter:
    """
    Router for handling SSR app routes.
    """
    
    def __init__(self, app_dir: Path, build_dir: Optional[Path] = None):
        self.app_dir = app_dir
        self.build_dir = build_dir or Path("dist")
        self.ssr_renderer = SSRRenderer(self.build_dir)
        self._router: Optional[Router] = None
    
    def create_router(self) -> Router:
        """
        Create Starlette router for app routes.
        
        Returns:
            Configured Starlette Router
            
        Example:
            >>> app_router = AppRouter(Path("app"))
            >>> router = app_router.create_router()
        """
        if self._router:
            return self._router
        
        # Create catch-all route for SSR
        routes = [
            Route("/{path:path}", self._handle_ssr_route, methods=["GET"])
        ]
        
        self._router = Router(routes)
        logger.info("App router created")
        
        return self._router
    
    async def _handle_ssr_route(self, request: Request) -> Response:
        """
        Handle SSR route rendering.
        
        Args:
            request: Starlette request object
            
        Returns:
            HTML response with rendered content
        """
        route_path = request.path_params.get("path", "")
        if not route_path.startswith("/"):
            route_path = "/" + route_path
        
        # Handle root route
        if route_path == "/":
            route_path = "/"
        
        logger.debug(f"Rendering SSR route: {route_path}")
        
        try:
            # Extract query parameters and headers for SSR context
            ssr_context = self._build_ssr_context(request)
            
            # Render the route
            html_content = await self.ssr_renderer.render_route(
                route_path, 
                context=ssr_context
            )
            
            return HTMLResponse(html_content)
            
        except Exception as e:
            logger.error(f"SSR rendering failed for {route_path}: {e}")
            return await self._handle_ssr_error(request, e)
    
    def _build_ssr_context(self, request: Request) -> Dict[str, Any]:
        """
        Build SSR context from request.
        
        Args:
            request: Starlette request object
            
        Returns:
            SSR context dictionary
        """
        return {
            "url": str(request.url),
            "method": request.method,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
            "path_params": dict(request.path_params),
            "client": {
                "host": request.client.host if request.client else None,
                "port": request.client.port if request.client else None
            }
        }
    
    async def _handle_ssr_error(self, request: Request, error: Exception) -> Response:
        """
        Handle SSR rendering errors.
        
        Args:
            request: Original request
            error: Exception that occurred
            
        Returns:
            Error response
        """
        # In development, show detailed error
        if self._is_development():
            error_html = self._create_error_page(request.url.path, str(error))
            return HTMLResponse(error_html, status_code=500)
        
        # In production, show generic error
        return HTMLResponse(
            "<html><body><h1>500 - Internal Server Error</h1></body></html>",
            status_code=500
        )
    
    def _is_development(self) -> bool:
        """Check if running in development mode."""
        import os
        return os.getenv("TAVO_ENV", "development") == "development"
    
    def _create_error_page(self, route: str, error_message: str) -> str:
        """
        Create HTML error page for development.
        
        Args:
            route: Route that failed
            error_message: Error message to display
            
        Returns:
            HTML error page
        """
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Tavo SSR Error</title>
    <style>
        body {{ font-family: monospace; margin: 40px; background: #1a1a1a; color: #fff; }}
        .error {{ background: #2d1b1b; padding: 20px; border-radius: 8px; border-left: 4px solid #ff6b6b; }}
        .route {{ color: #64b5f6; }}
        .message {{ color: #ff6b6b; margin-top: 10px; }}
        pre {{ background: #0d1117; padding: 15px; border-radius: 6px; overflow-x: auto; }}
    </style>
</head>
<body>
    <h1>🚨 SSR Error</h1>
    <div class="error">
        <div><strong>Route:</strong> <span class="route">{route}</span></div>
        <div class="message"><strong>Error:</strong> {error_message}</div>
    </div>
    <p>This error page is only shown in development mode.</p>
</body>
</html>
"""
    
    def get_route_manifest(self) -> Dict[str, Any]:
        """
        Get manifest of available app routes.
        
        Returns:
            Route manifest with metadata
        """
        # TODO: implement route discovery from app directory
        routes = self._discover_app_routes()
        
        return {
            "routes": routes,
            "total": len(routes),
            "app_dir": str(self.app_dir)
        }
    
    def _discover_app_routes(self) -> List[Dict[str, Any]]:
        """Discover available app routes from file system."""
        routes = []
        
        if not self.app_dir.exists():
            return routes
        
        # Look for page.tsx files
        for page_file in self.app_dir.rglob("page.tsx"):
            relative_path = page_file.relative_to(self.app_dir)
            route_path = self._page_file_to_route(relative_path)
            
            routes.append({
                "path": route_path,
                "file": str(page_file),
                "type": "page"
            })
        
        # Look for layout.tsx files
        for layout_file in self.app_dir.rglob("layout.tsx"):
            relative_path = layout_file.relative_to(self.app_dir)
            route_path = self._layout_file_to_route(relative_path)
            
            routes.append({
                "path": route_path,
                "file": str(layout_file),
                "type": "layout"
            })
        
        return routes
    
    def _page_file_to_route(self, file_path: Path) -> str:
        """Convert page file path to route path."""
        # Remove page.tsx
        parts = list(file_path.parts[:-1])
        
        if not parts:
            return "/"
        
        # Handle dynamic routes
        processed_parts = []
        for part in parts:
            if part.startswith("[") and part.endswith("]"):
                param_name = part[1:-1]
                processed_parts.append(f"{{{param_name}}}")
            else:
                processed_parts.append(part)
        
        return "/" + "/".join(processed_parts)
    
    def _layout_file_to_route(self, file_path: Path) -> str:
        """Convert layout file path to route path."""
        # Similar to page files but for layouts
        parts = list(file_path.parts[:-1])
        return "/" + "/".join(parts) if parts else "/"


async def handle_static_assets(request: Request) -> Response:
    """
    Handle static asset requests.
    
    Args:
        request: Starlette request for static asset
        
    Returns:
        Static file response or 404
    """
    # TODO: implement static asset serving
    # This would serve files from the build directory
    
    from starlette.responses import FileResponse
    from starlette.exceptions import HTTPException
    
    # Extract file path from URL
    file_path = request.path_params.get("path", "")
    
    # Security: prevent directory traversal
    if ".." in file_path or file_path.startswith("/"):
        raise HTTPException(status_code=404)
    
    # TODO: serve from actual build directory
    static_file = Path("dist") / "static" / file_path
    
    if static_file.exists() and static_file.is_file():
        return FileResponse(static_file)
    
    raise HTTPException(status_code=404)


def create_app_router(project_dir: Path, build_dir: Optional[Path] = None) -> AppRouter:
    """
    Create an app router for the project.
    
    Args:
        project_dir: Project root directory
        build_dir: Build output directory
        
    Returns:
        Configured AppRouter instance
    """
    app_dir = project_dir / "app"
    return AppRouter(app_dir, build_dir)


if __name__ == "__main__":
    # Example usage
    project_dir = Path.cwd()
    app_router = create_app_router(project_dir)
    
    router = app_router.create_router()
    manifest = app_router.get_route_manifest()
    
    print(f"App router created with {manifest['total']} routes")
    for route in manifest['routes']:
        print(f"  {route['path']} ({route['type']})")

# Unit tests as comments:
# 1. test_file_path_to_route_path() - verify file paths convert to correct routes
# 2. test_handle_ssr_route() - test SSR route handling with various inputs
# 3. test_discover_app_routes() - verify route discovery finds all page/layout files