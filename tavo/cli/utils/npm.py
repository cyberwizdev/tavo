"""
Bino NPM Utilities

Wrapper helpers that call npm/pnpm/yarn ensuring lockfile and cross-platform behavior.
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
import shutil

logger = logging.getLogger(__name__)


class PackageManager:
    """Package manager abstraction for npm/yarn/pnpm."""
    
    def __init__(self, name: str, install_cmd: List[str], add_cmd: List[str]):
        self.name = name
        self.install_cmd = install_cmd
        self.add_cmd = add_cmd
    
    def is_available(self) -> bool:
        """Check if package manager is available on system."""
        try:
            subprocess.run([self.name, "--version"], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


# Package manager configurations
PACKAGE_MANAGERS = {
    "npm": PackageManager("npm", ["npm", "install"], ["npm", "add"]),
    "yarn": PackageManager("yarn", ["yarn", "install"], ["yarn", "add"]),
    "pnpm": PackageManager("pnpm", ["pnpm", "install"], ["pnpm", "add"])
}


def detect_package_manager(project_dir: Path) -> str:
    """
    Detect package manager based on lockfiles and availability.
    
    Args:
        project_dir: Project directory to check
        
    Returns:
        Package manager name ("npm", "yarn", or "pnpm")
        
    Example:
        >>> pm = detect_package_manager(Path("."))
        >>> print(f"Using {pm}")
    """
    # Check for lockfiles first
    if (project_dir / "pnpm-lock.yaml").exists():
        if PACKAGE_MANAGERS["pnpm"].is_available():
            return "pnpm"
    
    if (project_dir / "yarn.lock").exists():
        if PACKAGE_MANAGERS["yarn"].is_available():
            return "yarn"
    
    # Default to npm
    return "npm"


def install_dependencies(project_dir: Path, package_manager: Optional[str] = None) -> None:
    """
    Install Node.js dependencies using detected or specified package manager.
    
    Args:
        project_dir: Project directory containing package.json
        package_manager: Specific package manager to use (auto-detect if None)
        
    Raises:
        FileNotFoundError: If package.json not found
        subprocess.CalledProcessError: If installation fails
    """
    package_json = project_dir / "package.json"
    if not package_json.exists():
        raise FileNotFoundError(f"package.json not found in {project_dir}")
    
    if package_manager is None:
        package_manager = detect_package_manager(project_dir)
    
    pm = PACKAGE_MANAGERS.get(package_manager)
    if not pm:
        raise ValueError(f"Unknown package manager: {package_manager}")
    
    if not pm.is_available():
        raise FileNotFoundError(f"{package_manager} not found on system")
    
    logger.info(f"Installing dependencies with {package_manager}...")
    
    try:
        subprocess.run(
            pm.install_cmd,
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True
        )
        logger.info("✅ Node.js dependencies installed")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Installation failed: {e.stderr}")
        raise


def add_package(
    project_dir: Path, 
    packages: List[str], 
    dev: bool = False,
    package_manager: Optional[str] = None
) -> None:
    """
    Add new packages to the project.
    
    Args:
        project_dir: Project directory
        packages: List of package names to add
        dev: Whether to add as dev dependencies
        package_manager: Package manager to use (auto-detect if None)
    """
    if package_manager is None:
        package_manager = detect_package_manager(project_dir)
    
    pm = PACKAGE_MANAGERS.get(package_manager)
    if not pm:
        raise ValueError(f"Unknown package manager: {package_manager}")
    
    cmd = pm.add_cmd + packages
    if dev:
        if package_manager == "npm":
            cmd.append("--save-dev")
        elif package_manager in ["yarn", "pnpm"]:
            cmd.append("--dev")
    
    logger.info(f"Adding packages: {', '.join(packages)}")
    
    try:
        subprocess.run(cmd, cwd=project_dir, check=True)
        logger.info("✅ Packages added successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to add packages: {e}")
        raise


def ensure_node_modules(project_dir: Path) -> bool:
    """
    Ensure node_modules directory exists and is populated.
    
    Args:
        project_dir: Project directory to check
        
    Returns:
        True if node_modules exists and appears populated
        
    Example:
        >>> if not ensure_node_modules(Path(".")):
        ...     print("Run npm install first")
    """
    node_modules = project_dir / "node_modules"
    
    if not node_modules.exists():
        return False
    
    # Check if it has any content (basic heuristic)
    try:
        next(node_modules.iterdir())
        return True
    except StopIteration:
        return False


def get_package_info(project_dir: Path) -> Dict[str, Any]:
    """
    Read package.json and return parsed content.
    
    Args:
        project_dir: Project directory containing package.json
        
    Returns:
        Parsed package.json content
        
    Raises:
        FileNotFoundError: If package.json not found
        json.JSONDecodeError: If package.json is invalid
    """
    package_json = project_dir / "package.json"
    if not package_json.exists():
        raise FileNotFoundError(f"package.json not found in {project_dir}")
    
    with package_json.open() as f:
        return json.load(f)


def run_npm_script(project_dir: Path, script_name: str, package_manager: Optional[str] = None) -> None:
    """
    Run an npm script defined in package.json.
    
    Args:
        project_dir: Project directory
        script_name: Name of script to run
        package_manager: Package manager to use (auto-detect if None)
        
    Raises:
        subprocess.CalledProcessError: If script execution fails
    """
    if package_manager is None:
        package_manager = detect_package_manager(project_dir)
    
    # Build command based on package manager
    if package_manager == "npm":
        cmd = ["npm", "run", script_name]
    elif package_manager == "yarn":
        cmd = ["yarn", script_name]
    elif package_manager == "pnpm":
        cmd = ["pnpm", "run", script_name]
    else:
        raise ValueError(f"Unknown package manager: {package_manager}")
    
    logger.info(f"Running script '{script_name}' with {package_manager}")
    
    try:
        subprocess.run(cmd, cwd=project_dir, check=True)
        logger.info(f"✅ Script '{script_name}' completed")
    except subprocess.CalledProcessError as e:
        logger.error(f"Script '{script_name}' failed with exit code {e.returncode}")
        raise


def clean_node_modules(project_dir: Path) -> None:
    """
    Remove node_modules directory to force clean install.
    
    Args:
        project_dir: Project directory containing node_modules
    """
    node_modules = project_dir / "node_modules"
    if node_modules.exists():
        logger.info("Cleaning node_modules...")
        shutil.rmtree(node_modules)
        logger.info("✅ node_modules cleaned")


if __name__ == "__main__":
    # Example usage
    project_dir = Path.cwd()
    
    try:
        pm = detect_package_manager(project_dir)
        print(f"Detected package manager: {pm}")
        
        if ensure_node_modules(project_dir):
            print("✅ node_modules is ready")
        else:
            print("❌ node_modules missing or empty")
            
    except Exception as e:
        print(f"Error: {e}")

# Unit tests as comments:
# 1. test_detect_package_manager() - verify lockfile detection works correctly
# 2. test_ensure_node_modules() - test node_modules validation logic
# 3. test_run_npm_script() - verify script execution with different package managers