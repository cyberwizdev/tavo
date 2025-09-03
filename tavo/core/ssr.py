"""
Tavo SSR Implementation - Fixed JSON Serialization

SSR bridge implementation — Python ↔ rust_bundler. Returns complete HTML with inline JavaScript bundle.
Fixed to handle non-serializable context data.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import time

from tavo.core.utils.bundler import get_bundler_path

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
            # Clean context to only include serializable data
            clean_context = self._sanitize_context(context or {})
            
            # Get bundler output (HTML + JS bundle)
            bundler_output = await self._get_bundler_output(route, clean_context)
            
            # Combine HTML and JS into single response
            complete_html = self._create_complete_html(
                bundler_output.get("html", ""),
                bundler_output.get("js", ""),
                route,
                clean_context
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
    
    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean context data to only include JSON-serializable values.
        
        Args:
            context: Raw context that may contain non-serializable objects
            
        Returns:
            Clean context with only serializable data
        """
        def is_serializable(value: Any) -> bool:
            """Check if a value is JSON serializable."""
            try:
                json.dumps(value)
                return True
            except (TypeError, ValueError):
                return False
        
        def serialize_value(value: Any) -> Any:
            """Convert value to serializable form or skip it."""
            if value is None or isinstance(value, (str, int, float, bool)):
                return value
            elif isinstance(value, (list, tuple)):
                return [serialize_value(item) for item in value if is_serializable(serialize_value(item))]
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items() if is_serializable(serialize_value(v))}
            elif hasattr(value, '__dict__'):
                # Try to serialize object attributes
                try:
                    return {k: serialize_value(v) for k, v in value.__dict__.items() if is_serializable(serialize_value(v))}
                except:
                    return str(value)  # Fallback to string representation
            else:
                # For other types, try string conversion or skip
                try:
                    str_value = str(value)
                    return str_value if len(str_value) < 500 else f"{str_value[:100]}..."
                except:
                    return None
        
        clean_context = {}
        
        for key, value in context.items():
            try:
                serialized_value = serialize_value(value)
                if serialized_value is not None:
                    clean_context[key] = serialized_value
            except Exception as e:
                logger.debug(f"Skipping context key '{key}': {e}")
                # Skip non-serializable values
                continue
        
        # Add safe metadata
        clean_context["_tavo"] = {
            "route": context.get("url", "unknown"),
            "timestamp": int(time.time()),
            "development": context.get("development", True)
        }
        
        return clean_context
    
    async def _get_bundler_output(self, route: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get bundler output with HTML and JavaScript bundle.
        """
        # Check cache first (for development efficiency)
        cache_key = f"{route}:{hash(str(sorted(context.items())))}"
        if cache_key in self._bundler_cache:
            logger.debug(f"Using cached bundler output for {route}")
            return self._bundler_cache[cache_key]
        
        try:
            bundler_path = get_bundler_path()
            
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
            logger.debug(f"Bundler output: {output_data}")
            
            # Cache result for development
            self._bundler_cache[cache_key] = output_data
            
            logger.debug(f"Bundler output cached for {route}")
            return output_data
            
        except Exception as e:
            logger.error(f"Bundler execution failed: {e}")
            # Return minimal fallback
            return {
                "html": self._get_fallback_html(route),
                "js": "console.log('Bundler failed, using fallback');"
            }
     
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
                logger.error(f"Bundler stderr: {error_msg}")
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
        
        # Safely serialize context to JSON
        try:
            context_json = json.dumps(context, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to serialize context: {e}")
            context_json = json.dumps({"error": "Context serialization failed"}, indent=2)
        
        # Create inline script with the complete bundle
        inline_script = f"""
<script type="module">
// Tavo hydration bundle for route: {route}
window.__TAVO_CONTEXT__ = {context_json};

// Initialize Tavo runtime
if (!window.__TAVO_RUNTIME__) {{
    window.__TAVO_RUNTIME__ = {{
        route: "{route}",
        hydrated: false,
        context: window.__TAVO_CONTEXT__
    }};
}}

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
    <title>Tavo App{' - ' + route if route != '/' else ''}</title>
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
            padding: 2rem;
        }}
        .route-info {{
            background: #f5f5f5;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            font-family: monospace;
            margin-top: 1rem;
        }}
    </style>
</head>
<body>
    <div id="root">
        <div class="loading">
            <h2>Tavo App</h2>
            <div class="route-info">Route: {route}</div>
            <p>Initializing...</p>
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
        routes = []
        for key in self._bundler_cache.keys():
            route_part = key.split(":")[0]
            if route_part not in routes:
                routes.append(route_part)
        return routes


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
        
        # Test with potentially problematic context
        test_context = {
            "url": "/test",
            "method": "GET",
            "headers": {"content-type": "application/json"},
            "development": True,
            "function_obj": lambda x: x,  # This would cause the original error
            "nested": {
                "data": "value",
                "number": 42
            }
        }
        
        try:
            html = await renderer.render_route("/", test_context)
            print("✅ Successfully rendered with complex context")
            print(f"HTML length: {len(html)} characters")
            print(f"Cached routes: {renderer.get_cached_routes()}")
            
        except SSRError as e:
            print(f"❌ SSR Error: {e}")
    
    asyncio.run(main())