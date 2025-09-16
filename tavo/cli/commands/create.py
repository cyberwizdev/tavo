"""
Tavo Create Command

Implementation of `tavo create <dir>` — scaffold templates into target dir with token replacement.
"""

import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import json
import importlib.resources as resources

from tavo.core.bundler import SWCInstaller

logger = logging.getLogger(__name__)


def create_project(target_dir: Path, template: str = "default") -> None:
    """
    Create a new Tavo project from template.
    
    Args:
        target_dir: Directory where the project will be created
        template: Template name to use (default: "default")
        
    Raises:
        FileExistsError: If target directory already exists and is not empty
        OSError: If unable to create directory or copy files
        
    Example:
        >>> create_project(Path("my-app"), "blog")
    """
    if target_dir.exists() and any(target_dir.iterdir()):
        raise FileExistsError(f"Directory {target_dir} already exists and is not empty")
    
    # Get template directory
    template_dir = _get_template_dir(template)
    if not template_dir.exists():
        raise FileNotFoundError(f"Template '{template}' not found")
    
    # Create target directory
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy template files with token replacement
    _copy_template_files(template_dir, target_dir)
    
    # Replace tokens in files
    project_name = target_dir.name
    _replace_tokens(target_dir, {"PROJECT_NAME": project_name})
    
    # Install SWC globally for the project
    _install_swc_dependencies()
    
    logger.info(f"Created project '{project_name}' in {target_dir}")


def _get_template_dir(template_name: str = "default") -> Path:
    """
    Get the specific template directory path.
    
    Args:
        template_name: Name of the template to use
        
    Returns:
        Path to the template directory
    """
    # Get the templates directory from the package
    templates_root = resources.files("tavo") / "templates"
    
    # Use as_file to get a real filesystem path
    with resources.as_file(templates_root) as templates_path:
        template_dir = templates_path / template_name
        return template_dir


def _copy_template_files(source_dir: Path, target_dir: Path) -> None:
    """
    Recursively copy template files to target directory.
    
    Args:
        source_dir: Source template directory
        target_dir: Target project directory
    """
    for item in source_dir.rglob("*"):
        if item.is_file() and not _should_skip_file(item):
            relative_path = item.relative_to(source_dir)
            target_file = target_dir / relative_path
            
            # Create parent directories
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(item, target_file)
            logger.debug(f"Copied {relative_path}")


def _should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped during template copying."""
    skip_patterns = {".git", "__pycache__", "node_modules", ".DS_Store"}
    return any(pattern in str(file_path) for pattern in skip_patterns)


def _replace_tokens(target_dir: Path, tokens: Dict[str, str]) -> None:
    """
    Replace template tokens in copied files.
    
    Args:
        target_dir: Directory containing files to process
        tokens: Dictionary of token replacements
    """
    text_extensions = {".py", ".tsx", ".ts", ".js", ".json", ".md", ".toml", ".yaml", ".yml"}
    
    for file_path in target_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix in text_extensions:
            try:
                content = file_path.read_text(encoding="utf-8")
                
                # Replace tokens
                for token, value in tokens.items():
                    content = content.replace(f"{{{{{token}}}}}", value)
                
                file_path.write_text(content, encoding="utf-8")
                logger.debug(f"Processed tokens in {file_path.relative_to(target_dir)}")
                
            except UnicodeDecodeError:
                logger.warning(f"Skipping binary file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")


def _install_swc_dependencies() -> None:
    """
    Install SWC CLI and Core globally for the framework.
    """
    installer = SWCInstaller()
    
    logger.info("Checking SWC installation...")
    if installer.is_swc_installed():
        logger.info("SWC is already installed")
        return
    
    logger.info("Installing SWC CLI and Core globally...")
    if installer.install_swc_globally():
        logger.info("SWC installed successfully")
    else:
        logger.warning("Failed to install SWC. You may need to install it manually: npm install -g @swc/cli @swc/core")


def get_available_templates() -> list[str]:
    """
    Get list of available project templates.
    
    Returns:
        List of template names
        
    Example:
        >>> templates = get_available_templates()
        >>> "default" in templates
        True
    """
    try:
        templates_root = resources.files("tavo") / "templates"
        with resources.as_file(templates_root) as templates_path:
            if not templates_path.exists():
                return ["default"]
            
            # Get all subdirectories in templates/
            templates = []
            for item in templates_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    templates.append(item.name)
            
            # Ensure 'default' is always available
            if "default" not in templates:
                templates.append("default")
            
            return sorted(templates)
    except Exception as e:
        logger.error(f"Failed to get available templates: {e}")
        return ["default"]


if __name__ == "__main__":
    # Example usage
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir) / "test-project"
        create_project(test_dir, "default")
        print(f"Created test project in {test_dir}")

# Unit tests as comments:
# 1. test_create_project_success() - verify project creation with valid template
# 2. test_create_project_existing_dir() - test error handling for existing directories
# 3. test_token_replacement() - verify template tokens are replaced correctly
# 4. test_get_available_templates() - test template discovery