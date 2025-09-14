
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from tavo.core.bundler import AppRouter


class SSRError(Exception):
    """Exception raised when SSR rendering fails."""
    pass


class SSRRenderer:
    """
    Server-Side Rendering engine that uses the AppRouter to build and compile
    React components for hydration.
    """

    def __init__(self, app_dir: Optional[Path] = None):
        """
        Initialize SSR renderer.

        Args:
            app_dir: Directory containing the React app components (defaults to cwd/app).
        """
        if app_dir:
            # If app_dir is provided, the project root is its parent
            project_root = app_dir.parent
        else:
            # Default to current working directory as project root
            project_root = Path.cwd()
        
        self.router = AppRouter(project_root=project_root)

    async def render_route(
        self,
        route: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a route and return complete HTML with inline JavaScript bundle.
        This method is async to avoid blocking the event loop, as the underlying
        compilation process can be slow.
        """
        try:
            loop = asyncio.get_running_loop()
            # Run the synchronous `render_route` in a thread pool executor
            html, status_code = await loop.run_in_executor(
                None, self.router.render_route, route
            )

            if status_code != 200:
                raise SSRError(f"Router returned status {status_code} for route '{route}': {html}")

            return html
        except Exception as e:
            raise SSRError(f"Failed to render route '{route}': {e}") from e

    def render_route_sync(
        self,
        route: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Synchronous version of render_route.
        """
        return asyncio.run(self.render_route(route, context))


# Convenience functions for the router
async def render_route(
    route: str,
    context: Optional[Dict[str, Any]] = None,
    app_dir: Optional[Path] = None
) -> str:
    """
    Convenience function to render a route with inline bundle.
    """
    renderer = SSRRenderer(app_dir)
    return await renderer.render_route(route, context)


def render_route_sync(
    route: str,
    context: Optional[Dict[str, Any]] = None,
    app_dir: Optional[Path] = None
) -> str:
    """Synchronous convenience function."""
    renderer = SSRRenderer(app_dir)
    return renderer.render_route_sync(route, context)


if __name__ == "__main__":
    # Example usage
    async def main():
        print("Testing SSRRenderer with AppRouter...")
        # Create a dummy project for testing in a temporary directory
        import tempfile
        import shutil

        project_dir = Path(tempfile.gettempdir()) / "tavo_ssr_test"
        if project_dir.exists():
            shutil.rmtree(project_dir)
        
        app_dir = project_dir / "app"
        app_dir.mkdir(parents=True, exist_ok=True)

        (app_dir / "layout.tsx").write_text(
            'export default function RootLayout({ children }) { return <html><head><title>Test</title></head><body><div id="root">{children}</div></body></html>; }'
        )
        (app_dir / "page.tsx").write_text(
            'export default function Page() { return <h1>Hello from Tavo SSR!</h1>; }'
        )
        (project_dir / "package.json").write_text(
            '{ "dependencies": { "react": "latest", "react-dom": "latest" } }'
        )
        print(f"Created dummy project at: {project_dir}")
        print("NOTE: This test runs 'node' and may require 'npm install' in the temp directory if dependencies are missing.")

        try:
            html = await render_route("/", app_dir=project_dir)
            print("\n✅ Successfully rendered route '/'")
            print(f"   HTML length: {len(html)} characters")
            print("-" * 20)
            print(html)
            print("-" * 20)
        except SSRError as e:
            print(f"❌ SSR Error: {e}")
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")

    asyncio.run(main())
