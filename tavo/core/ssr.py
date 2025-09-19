import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess # Added for npm install in example

from tavo.core.bundler import get_bundler, Bundler # Import Bundler class

class SSRError(Exception):
    """Exception raised when SSR rendering fails."""
    pass


class SSRRenderer:
    """
    Server-Side Rendering engine that uses the Tavo bundler's DevServer
    to build and compile React components for hydration and SSR.
    """

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize SSR renderer.

        Args:
            project_root: Path to the project root directory. Defaults to current working directory.
        """
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
        self.bundler: Bundler = get_bundler(project_root=self.project_root)

    async def render_route(
        self,
        route: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render a route and return complete HTML with inline JavaScript bundle.
        This method is async to avoid blocking the event loop, as the underlying
        compilation and SSR execution process can be slow.
        """
        try:
            loop = asyncio.get_running_loop()
            # Run the synchronous `dev_server.render_route` in a thread pool executor
            # The dev_server.render_route is now synchronous in its call to subprocess.run
            html = await loop.run_in_executor(
                None, self.bundler.dev_server.render_route, route, context
            )
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
    project_root: Optional[Path] = None
) -> str:
    """
    Convenience function to render a route with inline bundle.
    """
    renderer = SSRRenderer(project_root)
    return await renderer.render_route(route, context)


def render_route_sync(
    route: str,
    context: Optional[Dict[str, Any]] = None,
    project_root: Optional[Path] = None
) -> str:
    """Synchronous convenience function."""
    renderer = SSRRenderer(project_root)
    return renderer.render_route_sync(route, context)


if __name__ == "__main__":
    # Example usage
    async def main():
        print("Testing SSRRenderer with Tavo Bundler...")
        # Create a dummy project for testing in a temporary directory
        import tempfile
        import shutil

        project_dir = Path(tempfile.gettempdir()) / "tavo_ssr_test"
        if project_dir.exists():
            shutil.rmtree(project_dir)
        
        app_dir = project_dir / "app"
        app_dir.mkdir(parents=True, exist_ok=True)

        (app_dir / "layout.tsx").write_text(
            'import React from "react"; export default function RootLayout({ children }) { return <html><head><title>Test</title></head><body><div id="root">{children}</div></body></html>; }'
        )
        (app_dir / "page.tsx").write_text(
            'import React from "react"; export default function Page() { return <h1>Hello from Tavo SSR!</h1>; }'
        )
        # Ensure react and react-dom are installed for Node.js SSR execution
        (project_dir / "package.json").write_text(
            '{ "dependencies": { "react": "latest", "react-dom": "latest" } }'
        )
        # Run npm install to ensure dependencies are available for Node.js SSR
        print(f"Created dummy project at: {project_dir}")
        print("Running npm install in dummy project...")
        try:
            subprocess.run(["npm", "install"], cwd=project_dir, check=True, capture_output=True)
            print("npm install completed.")
        except subprocess.CalledProcessError as e:
            print(f"npm install failed: {e.stderr.decode()}")
            print("Please ensure Node.js and npm are installed and in your PATH.")
            return
        except FileNotFoundError:
            print("npm command not found. Please ensure Node.js and npm are installed and in your PATH.")
            return

        print("NOTE: This test requires 'node' and 'npm' to be installed and in your PATH.")

        try:
            html = await render_route("/", project_root=project_dir)
            print("\n✅ Successfully rendered route '/'")
            print(f"   HTML length: {len(html)} characters")
            print("-" * 20)
            print(html)
            print("-" * 20)
        except SSRError as e:
            print(f"❌ SSR Error: {e}")
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
        finally:
            if project_dir.exists():
                shutil.rmtree(project_dir)
                print(f"Cleaned up dummy project at: {project_dir}")

    asyncio.run(main())

