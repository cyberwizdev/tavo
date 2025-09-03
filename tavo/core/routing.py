"""
Tavo File-Based Routing

Implements file-based routing for API and React SSR routes.
Discovers routes from api/ and app/ directories and maps them to handlers.
"""

import asyncio  # Move this to the top
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from starlette.routing import Route, Router, Match
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from importlib import import_module
from .ssr import SSRRenderer
import sys

logger = logging.getLogger(__name__)

class RouteMatch:
    """Represents a matched route with parameters."""
    def __init__(self, path: str, params: Dict[str, str]):
        self.path = path
        self.params = params


class MethodDispatcher:
    """Handles dispatching to appropriate HTTP method handlers."""
    
    def __init__(self, method_map: Dict[str, Callable]):
        self.method_map = method_map
    
    async def dispatch(self, request: Request):
        """Dispatch request to appropriate method handler."""
        method = request.method.upper()
        handler = self.method_map.get(method)
        
        if not handler:
            # Return 405 Method Not Allowed
            allowed_methods = list(self.method_map.keys())
            return JSONResponse(
                {"error": f"Method {method} not allowed", "allowed_methods": allowed_methods},
                status_code=405,
                headers={"Allow": ", ".join(allowed_methods)}
            )
        
        try:
            # Call the handler with request and any path parameters
            if asyncio.iscoroutinefunction(handler):
                return await handler(request)
            else:
                return handler(request)
        except Exception as e:
            logger.error(f"Error in {method} handler for {request.url.path}: {e}")
            return JSONResponse(
                {"error": "Internal server error", "detail": str(e)},
                status_code=500
            )


class FileBasedRouter:
    """
    File-based router for Tavo applications.
    
    Discovers routes from filesystem and maps them to handlers for both
    API endpoints (Python) and SSR pages (React components).
    """
    
    def __init__(self, root_dir: Path, prefix: str = "", renderer: Optional[SSRRenderer] = None):
        """
        Initialize the file-based router.
        
        Args:
            root_dir: Directory containing route definitions (api/ or app/)
            prefix: URL prefix for routes (e.g., "/api" for API routes)
            renderer: SSRRenderer instance for app routes (optional)
        """
        self.root_dir = Path(root_dir)
        self.prefix = prefix.rstrip("/")
        self.renderer = renderer
        self.routes: List[Route] = []
        self.logger = logger
        
    async def discover_routes(self) -> None:
        """
        Discover routes from filesystem and populate self.routes.
        For API routes: imports Python modules from api/routes/
        For app routes: discovers .tsx files from app/ and uses SSR renderer
        """
        self.routes = []
        
        if self.renderer:  # App routes (React SSR)
            await self._discover_app_routes()
        else:  # API routes
            await self._discover_api_routes()
            
        self.logger.info(f"Discovered {len(self.routes)} routes in {self.root_dir}")
    
    async def _discover_api_routes(self) -> None:
        """
        Discover API routes from api/routes/ directory.
        Each .py file can export either:
        - a `handler` function (all methods handled internally)
        - or individual HTTP method functions (`get`, `post`, `put`, `delete`, etc.)
        """
        routes_dir = self.root_dir / "routes"
        if not routes_dir.exists():
            self.logger.warning(f"No routes directory found at {routes_dir}")
            return

        for py_file in routes_dir.glob("**/*.py"):
            if py_file.name == "__init__.py":
                continue

            # Convert filesystem path to URL path
            relative_path = py_file.relative_to(routes_dir).with_suffix("")
            route_path = f"/{relative_path.as_posix()}"  # Remove prefix here since it's added by Mount
            
            # Clean up double slashes
            route_path = re.sub(r'/+', '/', route_path)

            # Handle dynamic routes (e.g., [id].py -> {id})
            route_path = re.sub(r'\[([^\]]+)\]', r'{\1}', route_path)

            try:
                # Import the route module
                module_path = self._get_module_path(py_file, routes_dir)
                module = import_module(module_path)

                # Case 1: single `handler` function
                handler = getattr(module, "handler", None)
                if callable(handler):
                    # Wrap handler to handle async
                    async def wrapped_handler(request: Request, handler_fn=handler):
                        try:
                            if asyncio.iscoroutinefunction(handler_fn):
                                return await handler_fn(request)
                            else:
                                return handler_fn(request)
                        except Exception as e:
                            logger.error(f"Error in handler for {request.url.path}: {e}")
                            return JSONResponse(
                                {"error": "Internal server error", "detail": str(e)},
                                status_code=500
                            )
                    
                    self.routes.append(Route(route_path, wrapped_handler))
                    self.logger.debug(f"Registered API route (handler): {route_path}")
                    continue

                # Case 2: per-method functions (`get`, `post`, etc.)
                method_map = {}
                for method in ["get", "post", "put", "delete", "patch", "options", "head"]:
                    fn = getattr(module, method, None)
                    if callable(fn):
                        method_map[method.upper()] = fn

                if method_map:
                    dispatcher = MethodDispatcher(method_map)
                    methods = list(method_map.keys())
                    
                    self.routes.append(Route(route_path, dispatcher.dispatch, methods=methods))
                    self.logger.debug(f"Registered API route (methods): {route_path} -> {methods}")
                else:
                    self.logger.warning(f"No handler or method functions found in {py_file}")

            except Exception as e:
                self.logger.error(f"Failed to load route {py_file}: {e}")
                import traceback
                traceback.print_exc()

    def _get_module_path(self, py_file: Path, routes_dir: Path) -> str:
        """Get the correct module path for importing."""
        # Get the relative path from routes directory
        relative_path = py_file.relative_to(routes_dir).with_suffix("")
        
        # Get the project root (parent of api directory)
        api_dir = routes_dir.parent  # This should be the 'api' directory
        project_root = api_dir.parent  # This should be 'new_app'
        
        # Add project root to Python path if not already there
        project_root_str = str(project_root)
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)
        
        # Build the module path: api.routes.filename (without .py extension)
        module_parts = []
        module_parts.append(api_dir.name)  # 'api'
        module_parts.append(routes_dir.name)  # 'routes'
        module_parts.extend(relative_path.parts)  # subdirectories and filename
        
        return ".".join(module_parts)

    def _import_route_module_safely(self, py_file: Path, routes_dir: Path):
        """Safely import a route module with better error handling."""
        try:
            # Method 1: Try standard import
            module_path = self._get_module_path(py_file, routes_dir)
            return import_module(module_path)
        except ImportError as e1:
            self.logger.debug(f"Standard import failed for {py_file}: {e1}")
            
            try:
                # Method 2: Try direct file loading
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    f"route_{py_file.stem}", py_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    return module
            except Exception as e2:
                self.logger.debug(f"Direct file loading failed for {py_file}: {e2}")
                
            # Re-raise the original import error
            raise e1


    async def _discover_app_routes(self) -> None:
        """
        Discover React SSR routes from app/ directory.
        Only `page.tsx` files are treated as routable pages.
        """
        if not self.renderer:
            self.logger.error("SSRRenderer required for app routes")
            return

        for tsx_file in self.root_dir.glob("**/page.tsx"):
            # Convert filesystem path to URL path
            relative_path = tsx_file.relative_to(self.root_dir).parent
            route_path = (
                f"{self.prefix}/{relative_path.as_posix()}"
                if relative_path.as_posix() != "."
                else (self.prefix or "/")
            )
            
            # Clean up path
            route_path = re.sub(r'/+', '/', route_path)

            # Handle dynamic routes (e.g., [id]/page.tsx -> {id})
            route_path = re.sub(r"\[([^\]]+)\]", r"{\1}", route_path)

            # Create SSR handler for this route
            async def create_ssr_handler(path: str):
                async def ssr_handler(request: Request) -> Response:
                    try:
                        ssr_context = {
                            "url": str(request.url),
                            "method": request.method,
                            "headers": dict(request.headers),
                            "query_params": dict(request.query_params),
                            "route_params": request.path_params,
                        }
                        html_content = await self.renderer.render_route(path, ssr_context) # type: ignore
                        return Response(content=html_content, media_type="text/html")
                    except Exception as e:
                        self.logger.error(f"SSR error for {path}: {e}")
                        return JSONResponse(
                            {"error": f"Failed to render {path}", "detail": str(e)},
                            status_code=500,
                        )
                return ssr_handler

            handler = await create_ssr_handler(route_path)
            self.routes.append(Route(route_path, handler))
            self.logger.debug(f"Registered SSR route: {route_path}")

    def get_starlette_routes(self) -> Router:
        """
        Get Starlette Router instance with all discovered routes.
        
        Returns:
            Starlette Router containing all routes
        """
        return Router(routes=self.routes)
    
    def match_route(self, path: str) -> Optional[RouteMatch]:
        """
        Match a path against registered routes and extract parameters.
        
        Args:
            path: URL path to match
            
        Returns:
            RouteMatch object with path and parameters if matched, None otherwise
        """
        for route in self.routes:
            match, params = route.matches({"type": "http", "path": path, "method": "GET"})
            if match == Match.FULL:
                return RouteMatch(route.path, params) # type: ignore
        return None
    
    def get_route_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all registered routes.
        
        Returns:
            List of dictionaries containing route details
        """
        return [
            {
                "path": route.path,
                "methods": list(route.methods) if route.methods else ["GET"],
                "type": "ssr" if self.renderer else "api"
            }
            for route in self.routes
        ]


if __name__ == "__main__":
    # Example usage
    async def main():
        # Example for API router
        api_router = FileBasedRouter(Path("api"), prefix="/api")
        await api_router.discover_routes()
        print("API Routes:", api_router.get_route_info())
        
        # Example for App router
        app_router = FileBasedRouter(Path("app"), renderer=SSRRenderer(Path("dist")))
        await app_router.discover_routes()
        print("App Routes:", app_router.get_route_info())
    
    asyncio.run(main())

# Unit tests as comments:
# 1. test_api_route_discovery() - verify API routes are correctly discovered from api/routes/
# 2. test_app_route_discovery() - verify SSR routes are correctly discovered from app/
# 3. test_dynamic_route_parsing() - test handling of dynamic routes ([id].py/tsx)
# 4. test_route_matching() - verify route matching and parameter extraction
# 5. test_error_handling() - test handling of invalid route files