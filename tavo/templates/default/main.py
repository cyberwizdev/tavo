"""
{{PROJECT_NAME}} - Tavo Full-Stack Application

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

# Import Tavo core components
from tavo.core.ssr import SSRRenderer
from tavo.core.middleware import TavoMiddleware
from tavo.core.routing import FileBasedRouter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize paths
project_root = Path(__file__).parent
app_dir = project_root / "app"
api_dir = project_root / "api"
public_dir = project_root / "public"

# Initialize SSR renderer
ssr_renderer = SSRRenderer(
    app_dir=app_dir,
    public_dir=public_dir
)

# Initialize file-based routers
api_router = FileBasedRouter(api_dir, prefix="/api")
app_router = FileBasedRouter(app_dir, renderer=ssr_renderer)


async def startup():
    """Initialize application on startup."""
    logger.info("🚀 Starting {{PROJECT_NAME}}...")
    
    # Initialize SSR renderer
    await ssr_renderer.initialize()
    
    # Discover and setup file-based routes
    await api_router.discover_routes()
    await app_router.discover_routes()
    
    logger.info("✅ {{PROJECT_NAME}} initialized successfully")


async def shutdown():
    """Cleanup on application shutdown."""
    logger.info("🛑 Shutting down {{PROJECT_NAME}}...")
    await ssr_renderer.cleanup()


async def health_check(request: Request):
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy", 
        "app": "{{PROJECT_NAME}}",
        "routes": {
            "api": len(api_router.routes),
            "pages": len(app_router.routes)
        }
    })


async def hmr_endpoint(request: Request):
    """HMR endpoint for development."""
    return JSONResponse({
        "hmr": "enabled", 
        "websocket": "ws://localhost:3001",
        "timestamp": ssr_renderer.last_build_time
    })


async def ssr_handler(request: Request):
    """
    Handle all remaining routes through SSR.
    
    This catches routes not handled by the API and serves them
    through Tavo's React SSR system with file-based routing.
    """
    path = request.url.path
    
    try:
        # Check if this path matches a discovered app route
        route_match = app_router.match_route(path)
        
        if route_match:
            # Render the matched page component
            html_content = await ssr_renderer.render_page(
                component_path=route_match.component_path,
                props=route_match.props,
                request=request
            )
        else:
            # Render 404 page or fallback to app/not-found.tsx
            html_content = await ssr_renderer.render_not_found(request)
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"SSR error for path '{path}': {e}")
        
        # Fallback to basic HTML with client-side hydration
        fallback_html = await _get_fallback_html(path)
        return HTMLResponse(content=fallback_html)


async def _get_fallback_html(path: str = "/") -> str:
    """Generate fallback HTML for client-side hydration."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{PROJECT_NAME}}</title>
    <meta name="description" content="A Tavo full-stack application">
    <link rel="icon" href="/static/favicon.ico" />
    <script>
        window.__TAVO_HMR__ = true;
        window.__TAVO_INITIAL_PATH__ = "{path}";
    </script>
</head>
<body>
    <div id="root">
        <div style="padding: 2rem; text-align: center; font-family: system-ui, sans-serif;">
            <h1>Loading {{PROJECT_NAME}}...</h1>
            <p style="color: #666;">Initializing React application...</p>
            <div style="margin-top: 1rem;">
                <div style="width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto;"></div>
            </div>
        </div>
    </div>
    
    <!-- Tavo client bundle -->
    <script src="/static/bundle.js"></script>
    
    <!-- HMR WebSocket connection for development -->
    <script>
        if (window.__TAVO_HMR__ && location.hostname === 'localhost') {{
            const ws = new WebSocket('ws://localhost:3001');
            ws.onmessage = (event) => {{
                const data = JSON.parse(event.data);
                if (data.type === 'reload') {{
                    window.location.reload();
                }} else if (data.type === 'hmr-update') {{
                    // Handle hot module replacement
                    window.__tavo_hmr_update && window.__tavo_hmr_update(data.modules);
                }}
            }};
            ws.onopen = () => console.log('🔥 HMR connected');
            ws.onerror = (err) => console.warn('HMR connection error:', err);
        }}
    </script>
    
    <style>
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</body>
</html>
"""


# Define routes
routes = [
    # Health and development endpoints
    Route("/health", health_check),
    Route("/_hmr", hmr_endpoint),
    
    # Static file serving
    Mount("/static", StaticFiles(directory=public_dir), name="static"),
    
    # API routes (file-based from api/ directory)
    Mount("/api", api_router.get_starlette_routes()),
    
    # Catch-all SSR handler for app routes
    Route("/{path:path}", ssr_handler),
]

# Create Starlette application
app = Starlette(
    debug=True,  # Will be False in production
    routes=routes,
    on_startup=[startup],
    on_shutdown=[shutdown]
)

# Add Tavo middleware for HMR and development features
app.add_middleware(TavoMiddleware)


# Export app for ASGI servers
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=3000,
        reload=True,
        log_level="info"
    )