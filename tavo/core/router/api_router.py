"""
Bino API Router

File-based router loader for /api — dynamically imports python modules and wires Starlette-compatible endpoints.
"""

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List
from starlette.routing import Route, Router
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
import asyncio

logger = logging.getLogger(__name__)


class APIRouter:
    """
    File-based API router that dynamically loads Python modules as endpoints.
    """
    
    def __init__(self, api_dir: Path):
        self.api_dir = api_dir
        self.routes: List[Route] = []
        self._router: Optional[Router] = None
    
    def load_routes(self) -> Router:
        """
        Load all API routes from the api directory.
        
        Returns:
            Starlette Router with loaded routes
            
        Raises:
            ImportError: If route module cannot be imported
            
        Example:
            >>> router = APIRouter(Path("api"))
            >>> app_router = router.load_routes()
        """
        if self._router:
            return self._router
        
        logger.info(f"Loading API routes from {self.api_dir}")
        
        if not self.api_dir.exists():
            logger.warning(f"API directory not found: {self.api_dir}")
            self._router = Router([])
            return self._router
        
        # Discover and load route files
        route_files = self._discover_route_files()
        
        for route_file in route_files:
            try:
                self._load_route_file(route_file)
            except Exception as e:
                logger.error(f"Failed to load route {route_file}: {e}")
        
        self._router = Router(self.routes)
        logger.info(f"Loaded {len(self.routes)} API routes")
        
        return self._router
    
    def _discover_route_files(self) -> List[Path]:
        """Discover Python files that should be loaded as routes."""
        route_files = []
        
        for py_file in self.api_dir.rglob("*.py"):
            # Skip __init__.py and private files
            if py_file.name.startswith("_"):
                continue
            
            route_files.append(py_file)
        
        return sorted(route_files)
    
    def _load_route_file(self, route_file: Path) -> None:
        """
        Load a single route file and extract endpoints.
        
        Args:
            route_file: Python file to load as route
        """
        # Calculate route path from file path
        relative_path = route_file.relative_to(self.api_dir)
        route_path = self._file_path_to_route_path(relative_path)
        
        # Import the module
        module = self._import_route_module(route_file)
        
        # Extract HTTP method handlers
        handlers = self._extract_handlers(module)
        
        if handlers:
            # Create route with multiple methods
            route = Route(
                route_path,
                self._create_route_handler(handlers),
                methods=list(handlers.keys())
            )
            self.routes.append(route)
            logger.debug(f"Loaded route: {route_path} ({', '.join(handlers.keys())})")
    
    def _file_path_to_route_path(self, file_path: Path) -> str:
        """
        Convert file path to URL route path.
        
        Args:
            file_path: Relative file path
            
        Returns:
            URL route path
            
        Example:
            >>> router._file_path_to_route_path(Path("users/profile.py"))
            "/users/profile"
        """
        # Remove .py extension
        path_parts = list(file_path.parts[:-1]) + [file_path.stem]
        
        # Handle index files
        if path_parts[-1] == "index":
            path_parts = path_parts[:-1]
        
        # Handle dynamic routes (files with [param] syntax)
        processed_parts = []
        for part in path_parts:
            if part.startswith("[") and part.endswith("]"):
                # Convert [id] to {id}
                param_name = part[1:-1]
                processed_parts.append(f"{{{param_name}}}")
            else:
                processed_parts.append(part)
        
        route_path = "/" + "/".join(processed_parts)
        
        # Ensure route starts with /
        if not route_path.startswith("/"):
            route_path = "/" + route_path
        
        # Handle root route
        if route_path == "/":
            route_path = "/"
        
        return route_path
    
    def _import_route_module(self, route_file: Path) -> Any:
        """Import Python module from file path."""
        module_name = f"api_route_{route_file.stem}"
        
        spec = importlib.util.spec_from_file_location(module_name, route_file)
        if not spec or not spec.loader:
            raise ImportError(f"Cannot load module from {route_file}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        return module
    
    def _extract_handlers(self, module: Any) -> Dict[str, Callable]:
        """
        Extract HTTP method handlers from module.
        
        Args:
            module: Imported route module
            
        Returns:
            Dictionary mapping HTTP methods to handler functions
        """
        handlers = {}
        
        # Look for standard HTTP method functions
        http_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        
        for method in http_methods:
            handler_name = method.lower()
            if hasattr(module, handler_name):
                handler = getattr(module, handler_name)
                if callable(handler):
                    handlers[method] = handler
        
        return handlers
    
    def _create_route_handler(self, handlers: Dict[str, Callable]) -> Callable:
        """
        Create a unified route handler that dispatches to method-specific handlers.
        
        Args:
            handlers: Dictionary of HTTP method handlers
            
        Returns:
            Starlette-compatible route handler
        """
        async def route_handler(request: Request) -> Response:
            method = request.method
            handler = handlers.get(method)
            
            if not handler:
                return JSONResponse(
                    {"error": f"Method {method} not allowed"},
                    status_code=405
                )
            
            try:
                # Call handler (support both sync and async)
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(request)
                else:
                    result = handler(request)
                
                # Convert result to Response if needed
                if isinstance(result, Response):
                    return result
                elif isinstance(result, dict):
                    return JSONResponse(result)
                else:
                    return JSONResponse({"data": result})
                
            except Exception as e:
                logger.error(f"Route handler error: {e}")
                return JSONResponse(
                    {"error": "Internal server error"},
                    status_code=500
                )
        
        return route_handler
    
    def get_route_info(self) -> List[Dict[str, Any]]:
        """
        Get information about loaded routes.
        
        Returns:
            List of route information dictionaries
        """
        route_info = []
        
        for route in self.routes:
            info = {
                "path": route.path,
                "methods": list(route.methods) if route.methods else ["GET"],
                "name": getattr(route, "name", None)
            }
            route_info.append(info)
        
        return route_info
    
    def reload_routes(self) -> None:
        """Reload all routes (useful for development)."""
        self.routes.clear()
        self._router = None
        self.load_routes()
        logger.info("API routes reloaded")


def create_api_router(project_dir: Path) -> APIRouter:
    """
    Create an API router for the project.
    
    Args:
        project_dir: Project root directory
        
    Returns:
        Configured APIRouter instance
    """
    api_dir = project_dir / "api"
    return APIRouter(api_dir)


if __name__ == "__main__":
    # Example usage
    project_dir = Path.cwd()
    api_router = create_api_router(project_dir)
    
    router = api_router.load_routes()
    route_info = api_router.get_route_info()
    
    print(f"Loaded {len(route_info)} API routes:")
    for info in route_info:
        print(f"  {info['path']} - {', '.join(info['methods'])}")

# Unit tests as comments:
# 1. test_file_path_to_route_path() - verify file paths convert to correct URL routes
# 2. test_load_route_file() - test loading and importing route modules
# 3. test_extract_handlers() - verify HTTP method handlers are extracted correctly