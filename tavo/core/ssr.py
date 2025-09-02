"""
Tavo SSR Implementation - Updated for Inline Bundling

SSR bridge implementation — Python ↔ rust_bundler. Returns complete HTML with inline JavaScript bundle.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
import time
import platform

logger = logging.getLogger(__name__)


class SSRError(Exception):
    """Exception raised when SSR rendering fails."""
    pass


class SSRRenderer:
    """
    Server-Side Rendering engine that bridges Python and Rust bundler.
    Returns complete HTML with inline JavaScript for development.
    """
    
    def __init__(self, app_dir: Optional[Path] = None):
        """
        Initialize SSR renderer.
        
        Args:
            app_dir: Directory containing React components (defaults to ./app)
        """
        self.app_dir = app_dir or Path.cwd() / "app"
        self._bundler_cache: Dict[str, Dict[str, Any]] = {}
        
        if not self.app_dir.exists():
            logger.warning(f"App directory not found: {self.app_dir}")
    
    async def render_route(
        self, 
        route: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a route and return complete HTML with inline JavaScript bundle.
        
        Args:
            route: Route path to render (e.g., "/", "/about")
            context: Optional context data for rendering
            
        Returns:
            Complete HTML string with inline JavaScript bundle
            
        Raises:
            SSRError: If rendering fails
        """
        logger.debug(f"Rendering route: {route}")
        
        try:
            # Get bundler output (HTML + JS bundle)
            bundler_output = await self._get_bundler_output(route, context or {})
            
            # Combine HTML and JS into single response
            complete_html = self._create_complete_html(
                bundler_output.get("html", ""),
                bundler_output.get("js", ""),
                route,
                context or {}
            )
            
            return complete_html
            
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
        """
        return asyncio.run(self.render_route(route, context))
    
    async def _get_bundler_output(self, route: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get bundler output with HTML and JavaScript bundle.
        """
        # Check cache first (for development efficiency)
        cache_key = f"{route}:{hash(str(context))}"
        if cache_key in self._bundler_cache:
            return self._bundler_cache[cache_key]
        
        try:
            bundler_path = self._get_bundler_path()
            
            # Prepare context for bundler
            bundler_context = {
                "route": route,
                "timestamp": time.time(),
                **context
            }
            
            cmd = [
                str(bundler_path),
                "--route", route,
                "--app-dir", str(self.app_dir),
                "--compile-type", "hydration",
                "--output", "json"
            ]
            
            result = await self._run_bundler_command(cmd)
            
            # Parse JSON output
            output_data = json.loads(result.stdout)
            
            # Cache result for development
            self._bundler_cache[cache_key] = output_data
            
            return output_data
            
        except Exception as e:
            logger.error(f"Bundler execution failed: {e}")
            # Return minimal fallback
            return {
                "html": self._get_fallback_html(route),
                "js": "console.log('Bundler failed, using fallback');"
            }
    
    def _get_bundler_path(self) -> Path:
        """Get path to the Rust bundler binary."""
        system = platform.system().lower()
        if system == "windows":
            bin_name = "ssr-bundler.exe"
            target = "x86_64-pc-windows-msvc"
        elif system == "darwin":
            bin_name = "ssr-bundler"
            target = "x86_64-apple-darwin"
        elif system == "linux":
            bin_name = "ssr-bundler"
            target = "x86_64-unknown-linux-gnu"
        else:
            raise SSRError(f"Unsupported platform: {system}")

        # Look for bundler in project root
        project_root = Path.cwd()
        bundler_path = (
            project_root / "rust_bundler" / "target" / target / "release" / bin_name
        )

        if not bundler_path.exists():
            raise SSRError(f"SSR binary not found: {bundler_path}")

        return bundler_path
    
    async def _run_bundler_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run bundler command and return result."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=30.0
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise subprocess.CalledProcessError(
                    process.returncode, cmd, stdout, stderr # type: ignore
                )
            
            return subprocess.CompletedProcess(
                cmd, process.returncode, stdout.decode(), stderr.decode()
            )
            
        except asyncio.TimeoutError:
            logger.error("Bundler command timed out")
            raise SSRError("Bundler execution timed out")
        except Exception as e:
            logger.error(f"Bundler command failed: {e}")
            raise
    
    def _create_complete_html(
        self, 
        base_html: str, 
        js_bundle: str, 
        route: str, 
        context: Dict[str, Any]
    ) -> str:
        """
        Create complete HTML document with inline JavaScript bundle.
        """
        # If base_html is minimal, enhance it
        if not base_html or "<html" not in base_html.lower():
            base_html = self._get_fallback_html(route)
        
        # Create inline script with the complete bundle
        inline_script = f"""
<script type="module">
// Tavo hydration bundle for route: {route}
window.__TAVO_CONTEXT__ = {json.dumps(context, indent=2)};

{js_bundle}
</script>"""
        
        # Inject script before closing body tag
        if "</body>" in base_html:
            complete_html = base_html.replace("</body>", f"{inline_script}\n</body>")
        else:
            # Fallback: add script at the end
            complete_html = base_html + inline_script
        
        return complete_html
    
    def _get_fallback_html(self, route: str) -> str:
        """
        Generate fallback HTML structure when bundler fails or returns minimal HTML.
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tavo App - {route}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #fff;
        }}
        #root {{ 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .loading {{ 
            text-align: center;
            color: #666;
        }}
    </style>
</head>
<body>
    <div id="root">
        <div class="loading">
            <h2>Loading Tavo App...</h2>
            <p>Route: {route}</p>
        </div>
    </div>
</body>
</html>"""
    
    def clear_cache(self) -> None:
        """Clear the bundler output cache."""
        self._bundler_cache.clear()
        logger.debug("SSR cache cleared")
    
    def get_cached_routes(self) -> List[str]:
        """Get list of cached routes."""
        return [key.split(":")[0] for key in self._bundler_cache.keys()]


# Convenience functions for the router
async def render_route(
    route: str, 
    context: Optional[Dict[str, Any]] = None,
    app_dir: Optional[Path] = None
) -> str:
    """
    Convenience function to render a route with inline bundle.
    
    Args:
        route: Route path to render
        context: Optional rendering context
        app_dir: App directory (defaults to ./app)
        
    Returns:
        Complete HTML string with inline JavaScript
    """
    renderer = SSRRenderer(app_dir)
    return await renderer.render_route(route, context)


def render_route_sync(
    route: str, 
    context: Optional[Dict[str, Any]] = None,
    app_dir: Optional[Path] = None
) -> str:
    """Synchronous convenience function."""
    return asyncio.run(render_route(route, context, app_dir))


if __name__ == "__main__":
    # Example usage
    async def main():
        renderer = SSRRenderer()
        
        try:
            html = await renderer.render_route("/", {"title": "Home Page"})
            print("Complete HTML with inline bundle:")
            print(html[:500] + "..." if len(html) > 500 else html)
            
            print(f"Cached routes: {renderer.get_cached_routes()}")
            
        except SSRError as e:
            print(f"SSR Error: {e}")
    
    asyncio.run(main())