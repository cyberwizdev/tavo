"""
Tavo Install Command

Implementation of `tavo install` — run pip install then npm install; handle virtualenv and cross-platform concerns.
"""

import subprocess
import sys
import logging
from pathlib import Path
from typing import Optional, List
import venv
import os

logger = logging.getLogger(__name__)


def install_dependencies(project_dir: Optional[Path] = None) -> None:
    """
    Install both Python and Node.js dependencies for a Tavo project.
    
    Args:
        project_dir: Project directory (defaults to current directory)
        
    Raises:
        subprocess.CalledProcessError: If installation commands fail
        FileNotFoundError: If required files are missing
    """
    if project_dir is None:
        project_dir = Path.cwd()
    
    logger.info(f"Installing dependencies in {project_dir}")
    
    # Install Python dependencies
    _install_python_deps(project_dir)
    
    # Install Node.js dependencies
    _install_node_deps(project_dir)
    
    logger.info("All dependencies installed successfully")


def _install_python_deps(project_dir: Path) -> None:
    """
    Install Python dependencies using pip.
    
    Args:
        project_dir: Project directory containing requirements or pyproject.toml
    """
    # Check for virtual environment
    venv_path = project_dir / ".venv"
    if not venv_path.exists():
        logger.info("Creating virtual environment...")
        _create_virtual_env(venv_path)
    
    # Determine Python executable
    python_exe = _get_python_executable(venv_path)
    
    # Install dependencies
    requirements_file = project_dir / "requirements.txt"
    pyproject_file = project_dir / "pyproject.toml"
    
    if pyproject_file.exists():
        logger.info("Installing from pyproject.toml...")
        _run_command([python_exe, "-m", "pip", "install", "-e", "."], project_dir)
    elif requirements_file.exists():
        logger.info("Installing from requirements.txt...")
        _run_command([python_exe, "-m", "pip", "install", "-r", "requirements.txt"], project_dir)
    else:
        logger.warning("No Python dependencies file found (requirements.txt or pyproject.toml)")


def _install_node_deps(project_dir: Path) -> None:
    """
    Install Node.js dependencies using npm/pnpm/yarn.
    
    Args:
        project_dir: Project directory containing package.json
    """
    package_json = project_dir / "package.json"
    if not package_json.exists():
        logger.warning("No package.json found, skipping Node.js dependencies")
        return
    
    # Detect package manager
    package_manager = _detect_package_manager(project_dir)
    logger.info(f"Installing Node.js dependencies with {package_manager}...")
    
    install_cmd = _get_install_command(package_manager)
    _run_command(install_cmd, project_dir)


def _create_virtual_env(venv_path: Path) -> None:
    """Create a Python virtual environment."""
    try:
        venv.create(venv_path, with_pip=True)
        logger.info(f"Created virtual environment at {venv_path}")
    except Exception as e:
        logger.error(f"Failed to create virtual environment: {e}")
        raise


def _get_python_executable(venv_path: Path) -> str:
    """Get the Python executable path for the virtual environment."""
    if sys.platform == "win32":
        return str(venv_path / "Scripts" / "python.exe")
    else:
        return str(venv_path / "bin" / "python")


def _detect_package_manager(project_dir: Path) -> str:
    """
    Detect which package manager to use based on lockfiles.
    
    Args:
        project_dir: Project directory to check
        
    Returns:
        Package manager name ("pnpm", "yarn", or "npm")
    """
    if (project_dir / "pnpm-lock.yaml").exists():
        return "pnpm"
    elif (project_dir / "yarn.lock").exists():
        return "yarn"
    else:
        return "npm"


def _get_install_command(package_manager: str) -> List[str]:
    """Get the install command for the specified package manager."""
    commands = {
        "npm": ["npm", "install"],
        "yarn": ["yarn", "install"],
        "pnpm": ["pnpm", "install"]
    }
    return commands.get(package_manager, ["npm", "install"])


def _run_command(cmd: List[str], cwd: Path) -> None:
    """
    Run a shell command with proper error handling.
    
    Args:
        cmd: Command and arguments to run
        cwd: Working directory for the command
        
    Raises:
        subprocess.CalledProcessError: If command fails
    """
    try:
        logger.debug(f"Running: {' '.join(cmd)} in {cwd}")
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            shell=True
        )
        if result.stdout:
            logger.debug(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(cmd)}")
        logger.error(f"Exit code: {e.returncode}")
        if e.stderr:
            logger.error(f"Error output: {e.stderr}")
        raise


def check_system_requirements() -> bool:
    """
    Check if system has required tools installed.
    
    Returns:
        True if all requirements are met
        
    Example:
        >>> if check_system_requirements():
        ...     print("System ready for Tavo development")
    """
    required_tools = ["python", "node", "npm"]
    missing_tools = []
    
    for tool in required_tools:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing_tools.append(tool)
    
    if missing_tools:
        logger.error(f"Missing required tools: {', '.join(missing_tools)}")
        return False
    
    return True


if __name__ == "__main__":
    # Example usage
    if check_system_requirements():
        print("✅ System requirements met")
        # install_dependencies()
    else:
        print("❌ Missing system requirements")

# Unit tests as comments:
# 1. test_install_python_deps() - verify pip install works with virtual environment
# 2. test_detect_package_manager() - test detection of npm/yarn/pnpm lockfiles
# 3. test_check_system_requirements() - verify system tool detection works correctly