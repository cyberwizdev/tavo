"""
Bino Bundler Integration

Helpers to call the rust SWC bundler (build/watch/ssr) from Python.
"""

import subprocess
import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import os

logger = logging.getLogger(__name__)


class BundlerError(Exception):
    """Exception raised when bundler operations fail."""
    pass


async def build_production(
    project_dir: Path, 
    output_dir: Path, 
    production: bool = True
) -> Dict[str, Any]:
    """
    Build client and server bundles for production.
    
    Args:
        project_dir: Source project directory
        output_dir: Build output directory
        production: Whether to build in production mode
        
    Returns:
        Build manifest with asset mappings
        
    Raises:
        BundlerError: If build process fails
        
    Example:
        >>> manifest = await build_production(Path("."), Path("dist"))
        >>> print(manifest["client"]["entry"])
    """
    logger.info("Starting production build...")
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build command
    cmd = _build_bundler_command("build", project_dir, output_dir, production)
    
    try:
        result = await _run_bundler_command(cmd, project_dir)
        manifest = _parse_build_output(result.stdout)
        
        logger.info("✅ Production build completed")
        return manifest
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Build failed: {e.stderr}")
        raise BundlerError(f"Build process failed: {e}")


async def start_watch_mode(project_dir: Path, hmr_port: int = 3001) -> None:
    """
    Start bundler in watch mode for development.
    
    Args:
        project_dir: Project directory to watch
        hmr_port: Port for HMR WebSocket server
        
    Raises:
        BundlerError: If watch mode fails to start
    """
    logger.info("Starting bundler watch mode...")
    
    cmd = _build_bundler_command("watch", project_dir, hmr_port=hmr_port)
    
    try:
        # Start as background process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=project_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        logger.info("✅ Bundler watch mode started")
        return process
        
    except Exception as e:
        logger.error(f"Failed to start watch mode: {e}")
        raise BundlerError(f"Watch mode failed: {e}")


async def render_ssr(route: str, props: Optional[Dict[str, Any]] = None) -> str:
    """
    Render a route server-side using the bundler.
    
    Args:
        route: Route path to render
        props: Optional props to pass to the component
        
    Returns:
        Rendered HTML string
        
    Raises:
        BundlerError: If SSR fails
    """
    logger.debug(f"Rendering SSR for route: {route}")
    
    # TODO: implement actual SSR call to rust bundler
    # This would invoke the rust_bundler with ssr command
    
    # Mock implementation
    props_json = json.dumps(props or {})
    
    # This would be the actual call:
    # cmd = ["rust_bundler", "ssr", "--route", route, "--props", props_json]
    # result = await _run_bundler_command(cmd, Path.cwd())
    # return result.stdout
    
    return f"<html><body><h1>SSR: {route}</h1><script>window.__PROPS__ = {props_json}</script></body></html>"


def _build_bundler_command(
    command: str, 
    project_dir: Path, 
    output_dir: Optional[Path] = None,
    production: bool = True,
    hmr_port: Optional[int] = None
) -> List[str]:
    """Build command for rust bundler."""
    # TODO: implement actual rust bundler command building
    cmd = ["rust_bundler", command]
    
    if command == "build" and output_dir:
        cmd.extend(["--output", str(output_dir)])
        if production:
            cmd.append("--production")
    
    if command == "watch" and hmr_port:
        cmd.extend(["--hmr-port", str(hmr_port)])
    
    return cmd


async def _run_bundler_command(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run bundler command asynchronously."""
    logger.debug(f"Running bundler: {' '.join(cmd)}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode, cmd, stdout, stderr
            )
        
        return subprocess.CompletedProcess(
            cmd, process.returncode, stdout.decode(), stderr.decode()
        )
        
    except Exception as e:
        logger.error(f"Bundler command failed: {e}")
        raise


def _parse_build_output(output: str) -> Dict[str, Any]:
    """Parse bundler output to extract manifest."""
    try:
        # TODO: implement actual manifest parsing from rust bundler output
        # For now, return a mock manifest
        return {
            "client": {
                "entry": "client.js",
                "assets": ["client.js", "client.css"]
            },
            "server": {
                "entry": "server.js"
            },
            "routes": {}
        }
    except Exception as e:
        logger.error(f"Failed to parse build output: {e}")
        raise BundlerError(f"Invalid build output: {e}")


def check_bundler_available() -> bool:
    """
    Check if rust bundler is available on the system.
    
    Returns:
        True if bundler is available
    """
    try:
        subprocess.run(["rust_bundler", "--version"], 
                      capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_bundler_config(project_dir: Path) -> Dict[str, Any]:
    """
    Load bundler configuration from project.
    
    Args:
        project_dir: Project directory
        
    Returns:
        Bundler configuration
    """
    config_file = project_dir / "bino.config.json"
    if config_file.exists():
        with config_file.open() as f:
            return json.load(f)
    
    # Default configuration
    return {
        "entry": {
            "client": "app/page.tsx",
            "server": "app/layout.tsx"
        },
        "output": "dist",
        "target": "es2020"
    }


if __name__ == "__main__":
    # Example usage
    async def main():
        project_dir = Path.cwd()
        
        if check_bundler_available():
            print("✅ Rust bundler available")
            
            # Example build
            output_dir = Path("dist")
            manifest = await build_production(project_dir, output_dir)
            print(f"Build manifest: {manifest}")
        else:
            print("❌ Rust bundler not found")
    
    asyncio.run(main())

# Unit tests as comments:
# 1. test_build_production() - verify build process creates expected output
# 2. test_start_watch_mode() - test watch mode starts without errors
# 3. test_render_ssr() - verify SSR rendering returns valid HTML