"""
Tavo Bundler Integration

Helpers to call the rust SWC bundler (build/watch/ssr) from Python.
"""

import subprocess
import asyncio
import logging
import json
import platform
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class BundlerError(Exception):
    """Exception raised when bundler operations fail."""
    pass


class BundlerNotFound(BundlerError):
    """Raised when the Rust bundler binary cannot be found."""
    pass


def get_bundler_path() -> Path:
    """
    Return the path to the Rust bundler binary for the current platform.

    Raises:
        BundlerNotFound: if the binary does not exist
    """
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
        raise BundlerNotFound(f"Unsupported platform: {system}")

    bin_path = (
        Path(__file__).parent.parent.parent  # up from tavo/core → project root
        / "rust_bundler"
        / "target"
        / target
        / "release"
        / bin_name
    )

    if not bin_path.exists():
        raise BundlerNotFound(f"Rust bundler not found at {bin_path}")

    return bin_path


async def build_production(
    project_dir: Path,
    output_dir: Path,
    production: bool = True
) -> Dict[str, Any]:
    """
    Build client and server bundles for production.
    """
    logger.info("Starting production build...")

    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = _build_bundler_command("build", project_dir, output_dir, production)

    try:
        result = await _run_bundler_command(cmd, project_dir)
        manifest = _parse_build_output(result.stdout)

        logger.info("✅ Production build completed")
        return manifest

    except subprocess.CalledProcessError as e:
        logger.error(f"Build failed: {e.stderr}")
        raise BundlerError(f"Build process failed: {e}")


async def start_watch_mode(project_dir: Path, hmr_port: int = 3001) -> Any:
    """
    Start bundler in watch mode for development.
    """
    logger.info("Starting bundler watch mode...")
    cmd = _build_bundler_command("watch", project_dir, hmr_port=hmr_port)

    try:
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
    """
    logger.debug(f"Rendering SSR for route: {route}")
    props_json = json.dumps(props or {})

    try:
        bundler = str(get_bundler_path())
    except BundlerNotFound:
        # Fallback mock implementation if bundler missing
        return f"<html><body><h1>SSR: {route}</h1><script>window.__PROPS__ = {props_json}</script></body></html>"

    cmd = [bundler, "ssr", "--route", route, "--props", props_json]
    result = await _run_bundler_command(cmd, Path.cwd())
    return result.stdout


def _build_bundler_command(
    command: str,
    project_dir: Path,
    output_dir: Optional[Path] = None,
    production: bool = True,
    hmr_port: Optional[int] = None
) -> List[str]:
    """Build command for rust bundler."""
    bundler = str(get_bundler_path())
    cmd = [bundler, command]

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

    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode, cmd, stdout, stderr  # type: ignore
        )

    return subprocess.CompletedProcess(
        cmd, process.returncode, stdout.decode(), stderr.decode()
    )


def _parse_build_output(output: str) -> Dict[str, Any]:
    """Parse bundler output to extract manifest."""
    try:
        # TODO: parse actual manifest from bundler stdout
        return {
            "client": {"entry": "client.js", "assets": ["client.js", "client.css"]},
            "server": {"entry": "server.js"},
            "routes": {},
        }
    except Exception as e:
        logger.error(f"Failed to parse build output: {e}")
        raise BundlerError(f"Invalid build output: {e}")


def check_bundler_available() -> bool:
    """Check if rust bundler binary exists for this platform."""
    try:
        _ = get_bundler_path()
        return True
    except BundlerNotFound:
        return False


def get_bundler_config(project_dir: Path) -> Dict[str, Any]:
    """Load bundler configuration from project."""
    config_file = project_dir / "tavo.config.json"
    if config_file.exists():
        with config_file.open() as f:
            return json.load(f)

    return {
        "entry": {"client": "app/page.tsx", "server": "app/layout.tsx"},
        "output": "dist",
        "target": "es2020",
    }


if __name__ == "__main__":
    async def main():
        project_dir = Path.cwd()
        if check_bundler_available():
            print("✅ Rust bundler available")
            output_dir = Path("dist")
            manifest = await build_production(project_dir, output_dir)
            print(f"Build manifest: {manifest}")
        else:
            print("❌ Rust bundler not found")

    asyncio.run(main())
