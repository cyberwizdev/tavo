"""
Bino SSR Implementation

SSR bridge implementation — Python ↔ rust_bundler. Provide sync/async API to render a route and return HTML.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
import time

logger = logging.getLogger(__name__)


class SSRError(Exception):
    """Exception raised when SSR rendering fails."""
    pass


class SSRRenderer:
    """
    Server-Side Rendering engine that bridges Python and Rust bundler.
    """
    
    def __init__(self, build_dir: Path):
        self.build_dir = build_dir
        self.manifest: Optional[Dict[str, Any]] = None
        self._load_manifest()
    
    def _load_manifest(self) -> None:
        """Load build manifest for asset resolution."""
        manifest_file = self.build_dir / "manifest.json"
        
        if manifest_file.exists():
            try:
                with manifest_file.open() as f:
                    self.manifest = json.load(f)
                logger.debug("Build manifest loaded")
            except Exception as e:
                logger.error(f"Failed to load manifest: {e}")
                self.manifest = None
        else:
            logger.warning("No build manifest found - using development mode")
    
    async def render_route(
        self, 
        route: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a route server-side and return HTML.
        
        Args:
            route: Route path to render (e.g., "/", "/about")
            context: Optional context data for rendering
            
        Returns:
            Rendered HTML string
            
        Raises:
            SSRError: If rendering fails
            
        Example:
            >>> renderer = SSRRenderer(Path("dist"))
            >>> html = await renderer.render_route("/about", {"user": "John"})
        """
        logger.debug(f"Rendering route: {route}")
        
        try:
            # Prepare rendering context
            render_context = self._prepare_context(route, context or {})
            
            # Call rust bundler for SSR
            html_content = await self._call_rust_ssr(route, render_context)
            
            # Inject client-side hydration script
            html_with_hydration = self._inject_hydration_script(html_content, render_context)
            
            return html_with_hydration
            
        except Exception as e:
            logger.error(f"SSR failed for route {route}: {e}")
            raise SSRError(f"Failed to render {route}: {e}")
    
    def render_route_sync(
        self, 
        route: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Synchronous version of render_route.
        
        Args:
            route: Route path to render
            context: Optional context data
            
        Returns:
            Rendered HTML string
        """
        return asyncio.run(self.render_route(route, context))
    
    def _prepare_context(self, route: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare rendering context with route and build information.
        
        Args:
            route: Route being rendered
            context: User-provided context
            
        Returns:
            Complete rendering context
        """
        render_context = {
            "route": route,
            "timestamp": time.time(),
            "build_manifest": self.manifest,
            "assets": self._get_route_assets(route),
            **context
        }
        
        return render_context
    
    def _get_route_assets(self, route: str) -> Dict[str, List[str]]:
        """
        Get CSS and JS assets for a specific route.
        
        Args:
            route: Route path
            
        Returns:
            Dictionary with 'css' and 'js' asset lists
        """
        if not self.manifest:
            return {"css": [], "js": []}
        
        # TODO: implement actual asset resolution from manifest
        # This would look up route-specific assets from the build manifest
        
        return {
            "css": self.manifest.get("client", {}).get("css", []),
            "js": self.manifest.get("client", {}).get("js", [])
        }
    
    async def _call_rust_ssr(self, route: str, context: Dict[str, Any]) -> str:
        """
        Call rust bundler to perform SSR.
        
        Args:
            route: Route to render
            context: Rendering context
            
        Returns:
            Rendered HTML content
        """
        # TODO: implement actual rust bundler SSR call
        # This would invoke the rust_bundler binary with ssr command
        
        context_json = json.dumps(context)
        
        # Mock implementation for now
        logger.debug(f"Calling rust SSR for {route}")
        
        # This would be the actual implementation:
        # cmd = ["rust_bundler", "ssr", "--route", route, "--context", context_json]
        # result = await self._run_ssr_command(cmd)
        # return result.stdout
        
        # Mock HTML response
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Bino App</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
    <div id="root">
        <h1>SSR Route: {route}</h1>
        <p>This content was server-side rendered.</p>
    </div>
</body>
</html>
"""
    
    async def _run_ssr_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run SSR command and return result."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode, cmd, stdout, stderr # type: ignore
                )
            
            return subprocess.CompletedProcess(
                cmd, process.returncode, stdout.decode(), stderr.decode()
            )
            
        except Exception as e:
            logger.error(f"SSR command failed: {e}")
            raise
    
    def _inject_hydration_script(self, html: str, context: Dict[str, Any]) -> str:
        """
        Inject client-side hydration script into HTML.
        
        Args:
            html: Server-rendered HTML
            context: Rendering context
            
        Returns:
            HTML with hydration script injected
        """
        # Create hydration script
        hydration_script = self._create_hydration_script(context)
        
        # Inject before closing body tag
        if "</body>" in html:
            html = html.replace("</body>", f"{hydration_script}</body>")
        else:
            html += hydration_script
        
        return html
    
    def _create_hydration_script(self, context: Dict[str, Any]) -> str:
        """Create client-side hydration script."""
        # Include assets
        assets = context.get("assets", {})
        css_links = ""
        js_scripts = ""
        
        for css_file in assets.get("css", []):
            css_links += f'<link rel="stylesheet" href="/{css_file}">\n'
        
        for js_file in assets.get("js", []):
            js_scripts += f'<script src="/{js_file}"></script>\n'
        
        # Context for client-side hydration
        context_script = f"""
<script>
window.__BINO_CONTEXT__ = {json.dumps(context)};
</script>
"""
        
        return f"""
{css_links}
{context_script}
{js_scripts}
"""
    
    def preload_routes(self, routes: List[str]) -> None:
        """
        Preload routes for faster SSR.
        
        Args:
            routes: List of routes to preload
        """
        # TODO: implement route preloading
        logger.info(f"Preloading {len(routes)} routes")
    
    def get_render_stats(self) -> Dict[str, Any]:
        """
        Get SSR rendering statistics.
        
        Returns:
            Rendering statistics
        """
        # TODO: implement actual stats collection
        return {
            "total_renders": 0,
            "average_time": 0.0,
            "cache_hits": 0,
            "errors": 0
        }


# Convenience functions
async def render_route(
    route: str, 
    context: Optional[Dict[str, Any]] = None,
    build_dir: Optional[Path] = None
) -> str:
    """
    Convenience function to render a route.
    
    Args:
        route: Route path to render
        context: Optional rendering context
        build_dir: Build directory (defaults to ./dist)
        
    Returns:
        Rendered HTML string
        
    Example:
        >>> html = await render_route("/dashboard", {"user_id": 123})
    """
    if build_dir is None:
        build_dir = Path("dist")
    
    renderer = SSRRenderer(build_dir)
    return await renderer.render_route(route, context)


def render_route_sync(
    route: str, 
    context: Optional[Dict[str, Any]] = None,
    build_dir: Optional[Path] = None
) -> str:
    """
    Synchronous convenience function to render a route.
    
    Args:
        route: Route path to render
        context: Optional rendering context
        build_dir: Build directory
        
    Returns:
        Rendered HTML string
    """
    return asyncio.run(render_route(route, context, build_dir))


if __name__ == "__main__":
    # Example usage
    async def main():
        build_dir = Path("dist")
        renderer = SSRRenderer(build_dir)
        
        try:
            html = await renderer.render_route("/", {"title": "Home Page"})
            print("SSR HTML:")
            print(html[:200] + "..." if len(html) > 200 else html)
            
            stats = renderer.get_render_stats()
            print(f"Render stats: {stats}")
            
        except SSRError as e:
            print(f"SSR Error: {e}")
    
    asyncio.run(main())

# Unit tests as comments:
# 1. test_render_route_success() - verify successful route rendering
# 2. test_render_route_error_handling() - test error handling for invalid routes
# 3. test_inject_hydration_script() - verify hydration script injection works correctly