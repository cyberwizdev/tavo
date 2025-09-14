"""
New App - Tavo Full-Stack Application

Main entry point for the ASGI application.
This file sets up Starlette with file-based routing for both API and React SSR.
"""

from starlette.applications import Starlette
from starlette.staticfiles import StaticFiles
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, Mount
from starlette.requests import Request
from pathlib import Path
import logging
import os

# Import Tavo core components
from tavo.core.ssr import SSRRenderer
from tavo.core.middleware import TavoMiddleware
from tavo.core.routing import FileBasedRouter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tavo.main")

# Check if we should log routes (set by dev server)
SHOULD_LOG_ROUTES = os.getenv("TAVO_LOG_ROUTES") == "1"

# Initialize paths
project_root = Path(__file__).parent
app_dir = project_root / "app"
api_dir = project_root / "api"
public_dir = project_root / "public"
build_dir = project_root / ".tavo"

# Initialize SSR renderer
ssr_renderer = SSRRenderer()

# Initialize routers (lazy discovery on startup)
api_router = FileBasedRouter(api_dir, prefix="/api")
app_router = FileBasedRouter(app_dir, renderer=ssr_renderer)


def log_routes(app: Starlette, header: str = "📜 Registered routes:"):
    logger.info(header)
    for route in app.routes:
        if isinstance(route, Route):
            logger.info(f" - {route.path} {route.methods}")
        elif isinstance(route, Mount):
            logger.info(f" - Mount {route.path}")
            for sub in route.routes:
                if isinstance(sub, Route):
                    logger.info(f"    ↳ {sub.path} {sub.methods}")
                else:
                    logger.info(f"    ↳ {sub}")
        else:
            logger.info(f" - Other {route}")

# --- Endpoints --- #

async def health_check(request: Request):
    return JSONResponse({
        "status": "healthy",
        "app": "New App",
        "routes": {
            "api": len(api_router.routes),
            "pages": len(app_router.routes),
        },
    })


async def routes_info(request: Request):
    """Return detailed route information for dev server."""
    try:
        api_routes = []
        page_routes = []
        
        # Get API route info
        for route in api_router.routes:
            api_routes.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else ["GET"],
                "type": "api"
            })
        
        # Get page route info
        for route in app_router.routes:
            page_routes.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else ["GET"],
                "type": "page"
            })
        
        return JSONResponse({
            "api": api_routes,
            "pages": page_routes,
            "total": len(api_routes) + len(page_routes)
        })
        
    except Exception as e:
        logger.error(f"Error getting route info: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


async def hmr_endpoint(request: Request):
    return JSONResponse({
        "hmr": "enabled",
        "websocket": "ws://localhost:3001",
        "build_dir": str(build_dir),
    })


async def ssr_handler(request: Request):
    """SSR catch-all handler - only for non-API routes."""
    path = request.url.path
    
    # Double-check we're not handling API routes
    if path.startswith('/api/'):
        logger.warning(f"SSR handler received API request: {path}")
        return JSONResponse({"error": "API route handled by SSR"}, status_code=500)
    
    try:
        route_match = app_router.match_route(path)

        ssr_context = {
            "url": str(request.url),
            "method": request.method,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
            "route_params": route_match.params if route_match else {},
        }

        html_content = await ssr_renderer.render_route(route=path, context=ssr_context)
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"SSR error for path '{path}': {e}")
        fallback_html = await _get_fallback_html(path)
        return HTMLResponse(content=fallback_html)


async def _get_fallback_html(path: str = "/") -> str:
    """Fallback HTML for hydration."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>New App</title>
  <script>
    window.__TAVO_INITIAL_PATH__ = "{path}";
  </script>
</head>
<body>
  <div id="root"><h1>Loading...</h1></div>
  <script src="/static/bundle.js"></script>
</body>
</html>
"""


# --- Application Setup --- #

# Initial routes that need to be defined early
initial_routes = [
    Route("/health", health_check),
    Route("/_hmr", hmr_endpoint),
    Mount("/static", StaticFiles(directory=public_dir), name="static"),
    Mount("/favicon.ico", StaticFiles(directory=public_dir), name="favicon")
]

# Create the application with initial routes
app = Starlette(debug=True, routes=initial_routes)

# Add middleware
app.add_middleware(TavoMiddleware)


# --- Lifecycle Hooks --- #

@app.on_event("startup")
async def startup():
    """Setup routes during startup to ensure correct order."""
    logger.info("🚀 Starting up New App...")
    
    # Discover API routes
    await api_router.discover_routes()
    api_routes = api_router.get_starlette_routes()
    
    logger.info(f"📡 Mounting {len(api_routes.routes)} API routes")
    
    # Add API mount to the router - this is key!
    app.router.routes.insert(0, Mount("/api", api_routes))
    
    # Add catch-all SSR route LAST
    app.router.routes.append(Route("/{path:path}", ssr_handler))
    
    logger.info("✅ Routes configured")
    log_routes(app, "📜 Final route configuration:")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    logger.info("🛑 Shutting down New App...")


# Debug mode entry point (not used in tavo dev)
if __name__ == "__main__":
    import uvicorn
    logger.warning("⚠️ Running via main.py directly. For HMR, use: `tavo dev`")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=3000,
        reload=True,
        log_level="info",
    )