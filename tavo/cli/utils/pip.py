"""
Tavo Pip Utilities

Wrapper helpers for pip/venv/pyproject installation routines.
"""

import subprocess
import sys
import logging
import venv
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

logger = logging.getLogger(__name__)


def create_virtual_environment(venv_path: Path, python_executable: Optional[str] = None) -> None:
    """
    Create a Python virtual environment.
    
    Args:
        venv_path: Path where virtual environment will be created
        python_executable: Specific Python executable to use
        
    Raises:
        subprocess.CalledProcessError: If venv creation fails
        
    Example:
        >>> create_virtual_environment(Path(".venv"))
    """
    if venv_path.exists():
        logger.warning(f"Virtual environment already exists: {venv_path}")
        return
    
    logger.info(f"Creating virtual environment at {venv_path}")
    
    try:
        if python_executable:
            # Use specific Python executable
            subprocess.run([
                python_executable, "-m", "venv", str(venv_path)
            ], check=True)
        else:
            # Use built-in venv module
            venv.create(venv_path, with_pip=True)
        
        logger.info("✅ Virtual environment created")
        
    except Exception as e:
        logger.error(f"Failed to create virtual environment: {e}")
        raise


def get_venv_python(venv_path: Path) -> Path:
    """
    Get Python executable path for virtual environment.
    
    Args:
        venv_path: Virtual environment directory
        
    Returns:
        Path to Python executable
        
    Raises:
        FileNotFoundError: If virtual environment or Python executable not found
    """
    if not venv_path.exists():
        raise FileNotFoundError(f"Virtual environment not found: {venv_path}")
    
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"
    
    if not python_exe.exists():
        raise FileNotFoundError(f"Python executable not found: {python_exe}")
    
    return python_exe


def install_requirements(
    project_dir: Path, 
    venv_path: Optional[Path] = None,
    upgrade: bool = False
) -> None:
    """
    Install Python requirements from requirements.txt or pyproject.toml.
    
    Args:
        project_dir: Project directory
        venv_path: Virtual environment path (defaults to .venv)
        upgrade: Whether to upgrade packages
        
    Raises:
        FileNotFoundError: If no requirements file found
        subprocess.CalledProcessError: If installation fails
    """
    if venv_path is None:
        venv_path = project_dir / ".venv"
    
    python_exe = get_venv_python(venv_path)
    
    # Check for pyproject.toml first
    pyproject_file = project_dir / "pyproject.toml"
    requirements_file = project_dir / "requirements.txt"
    
    if pyproject_file.exists():
        _install_from_pyproject(python_exe, project_dir, upgrade)
    elif requirements_file.exists():
        _install_from_requirements(python_exe, requirements_file, upgrade)
    else:
        raise FileNotFoundError("No requirements.txt or pyproject.toml found")


def _install_from_pyproject(python_exe: Path, project_dir: Path, upgrade: bool) -> None:
    """Install from pyproject.toml using pip."""
    cmd = [str(python_exe), "-m", "pip", "install"]
    
    if upgrade:
        cmd.append("--upgrade")
    
    cmd.extend(["-e", "."])
    
    logger.info("Installing from pyproject.toml...")
    _run_pip_command(cmd, project_dir)


def _install_from_requirements(python_exe: Path, requirements_file: Path, upgrade: bool) -> None:
    """Install from requirements.txt using pip."""
    cmd = [str(python_exe), "-m", "pip", "install"]
    
    if upgrade:
        cmd.append("--upgrade")
    
    cmd.extend(["-r", str(requirements_file)])
    
    logger.info("Installing from requirements.txt...")
    _run_pip_command(cmd, requirements_file.parent)


def _run_pip_command(cmd: List[str], cwd: Path) -> None:
    """Run pip command with proper error handling."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            logger.debug(result.stdout)
        
        logger.info("✅ Python dependencies installed")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Pip command failed: {' '.join(cmd)}")
        if e.stderr:
            logger.error(f"Error: {e.stderr}")
        raise


def install_package(
    package_name: str, 
    venv_path: Path,
    dev: bool = False,
    version: Optional[str] = None
) -> None:
    """
    Install a specific Python package.
    
    Args:
        package_name: Name of package to install
        venv_path: Virtual environment path
        dev: Whether this is a development dependency
        version: Specific version to install
        
    Example:
        >>> install_package("requests", Path(".venv"), version="2.28.0")
    """
    python_exe = get_venv_python(venv_path)
    
    package_spec = package_name
    if version:
        package_spec = f"{package_name}=={version}"
    
    cmd = [str(python_exe), "-m", "pip", "install", package_spec]
    
    logger.info(f"Installing package: {package_spec}")
    _run_pip_command(cmd, Path.cwd())


def get_installed_packages(venv_path: Path) -> Dict[str, str]:
    """
    Get list of installed packages and their versions.
    
    Args:
        venv_path: Virtual environment path
        
    Returns:
        Dictionary mapping package names to versions
        
    Example:
        >>> packages = get_installed_packages(Path(".venv"))
        >>> print(packages.get("requests", "Not installed"))
    """
    python_exe = get_venv_python(venv_path)
    
    try:
        result = subprocess.run([
            str(python_exe), "-m", "pip", "list", "--format=json"
        ], capture_output=True, check=True, text=True)
        
        packages_list = json.loads(result.stdout)
        return {pkg["name"]: pkg["version"] for pkg in packages_list}
        
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.error(f"Failed to get package list: {e}")
        return {}


def check_pip_tools() -> bool:
    """
    Check if pip and related tools are available.
    
    Returns:
        True if pip tools are available
    """
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def upgrade_pip(venv_path: Path) -> None:
    """
    Upgrade pip to latest version in virtual environment.
    
    Args:
        venv_path: Virtual environment path
    """
    python_exe = get_venv_python(venv_path)
    
    cmd = [str(python_exe), "-m", "pip", "install", "--upgrade", "pip"]
    
    logger.info("Upgrading pip...")
    _run_pip_command(cmd, Path.cwd())


if __name__ == "__main__":
    # Example usage
    project_dir = Path.cwd()
    venv_path = project_dir / ".venv"
    
    if not venv_path.exists():
        print("Creating virtual environment...")
        create_virtual_environment(venv_path)
    
    if check_pip_tools():
        print("✅ Pip tools available")
        
        # Example: install requirements if they exist
        if (project_dir / "requirements.txt").exists():
            install_requirements(project_dir, venv_path)

# Unit tests as comments:
# 1. test_create_virtual_environment() - verify venv creation works correctly
# 2. test_install_requirements_missing_file() - test error handling for missing requirements
# 3. test_get_installed_packages() - verify package listing works with valid venv