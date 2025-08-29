"""
Tavo Start Command

Run production server (uvicorn or configured ASGI runner) serving prebuilt assets.
"""

import subprocess
import sys
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
import signal

logger = logging.getLogger(__name__)


def start_production_server(
    host: str = "0.0.0.0", 
    port: int = 8000, 
    workers: int = 1,
    build_dir: Optional[Path] = None
) -> None:
    """
    Start production server with prebuilt assets.
    
    Args:
        host: Host to bind to
        port: Port to bind to  
        workers: Number of worker processes
        build_dir: Directory containing build output (defaults to ./dist)
        
    Raises:
        FileNotFoundError: If build directory or manifest not found
        subprocess.CalledProcessError: If server fails to start
    """
    if build_dir is None:
        build_dir = Path.cwd() / "dist"
    
    # Validate build exists
    _validate_build(build_dir)
    
    # Configure environment for production
    _configure_production_env(build_dir)
    
    # Start ASGI server
    _start_asgi_server(host, port, workers)


def _validate_build(build_dir: Path) -> None:
    """
    Validate that build directory contains required files.
    
    Args:
        build_dir: Build directory to validate
        
    Raises:
        FileNotFoundError: If required build files are missing
    """
    if not build_dir.exists():
        raise FileNotFoundError(f"Build directory not found: {build_dir}")
    
    manifest_file = build_dir / "manifest.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"Build manifest not found: {manifest_file}")
    
    # Validate manifest content
    try:
        with manifest_file.open() as f:
            manifest = json.load(f)
        
        required_keys = ["client", "server"]
        for key in required_keys:
            if key not in manifest:
                raise ValueError(f"Invalid manifest: missing '{key}' section")
        
        logger.info("Build validation passed")
        
    except (json.JSONDecodeError, ValueError) as e:
        raise FileNotFoundError(f"Invalid build manifest: {e}")


def _configure_production_env(build_dir: Path) -> None:
    """
    Configure environment variables for production.
    
    Args:
        build_dir: Build directory path
    """
    import os
    
    # Set build directory for the app to find assets
    os.environ["TAVO_BUILD_DIR"] = str(build_dir.absolute())
    os.environ["TAVO_ENV"] = "production"
    
    logger.info("Production environment configured")


def _start_asgi_server(host: str, port: int, workers: int) -> None:
    """
    Start the ASGI server using uvicorn.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        workers: Number of worker processes
    """
    cmd = _build_server_command(host, port, workers)
    
    logger.info(f"Starting production server: {' '.join(cmd)}")
    
    try:
        # Setup signal handling
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start server
        subprocess.run(cmd, check=True)
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Server failed with exit code {e.returncode}")
        raise
    except KeyboardInterrupt:
        logger.info("Server stopped by user")


def _build_server_command(host: str, port: int, workers: int) -> List[str]:
    """
    Build the uvicorn command with appropriate options.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        workers: Number of worker processes
        
    Returns:
        Command list for subprocess
    """
    cmd = [
        sys.executable, "-m", "uvicorn",
        "main:app",
        "--host", host,
        "--port", str(port),
        "--workers", str(workers),
        "--no-reload",
        "--log-level", "info"
    ]
    
    return cmd


def check_production_requirements() -> bool:
    """
    Check if production requirements are met.
    
    Returns:
        True if ready for production deployment
        
    Example:
        >>> if check_production_requirements():
        ...     print("Ready for production")
    """
    project_dir = Path.cwd()
    
    # Check for main.py
    if not (project_dir / "main.py").exists():
        logger.error("main.py not found")
        return False
    
    # Check for build directory
    build_dir = project_dir / "dist"
    if not build_dir.exists():
        logger.error("Build directory not found - run 'tavo build' first")
        return False
    
    # Check for uvicorn
    try:
        subprocess.run([sys.executable, "-m", "uvicorn", "--version"], 
                      capture_output=True, check=True)
    except subprocess.CalledProcessError:
        logger.error("uvicorn not installed - run 'tavo install' first")
        return False
    
    return True


def get_server_status(port: int) -> Dict[str, Any]:
    """
    Get status information about the running server.
    
    Args:
        port: Port to check
        
    Returns:
        Server status information
    """
    # TODO: implement server health check
    return {
        "running": False,
        "port": port,
        "pid": None
    }


if __name__ == "__main__":
    # Example usage
    if check_production_requirements():
        print("Starting production server...")
        start_production_server()
    else:
        print("❌ Production requirements not met")

# Unit tests as comments:
# 1. test_validate_build() - verify build validation catches missing files
# 2. test_production_server_startup() - test server starts with correct configuration
# 3. test_check_production_requirements() - verify all requirements are checked properly