"""
Bino Create Command

Implementation of `bino create <dir>` — scaffold templates into target dir with token replacement.
"""

import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)


def create_project(target_dir: Path, template: str = "default") -> None:
    """
    Create a new Bino project from template.
    
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
    
    logger.info(f"Created project '{project_name}' in {target_dir}")


def _get_template_dir(template: str) -> Path:
    """Get the template directory path."""
    # TODO: implement template discovery from multiple sources
    current_dir = Path(__file__).parent.parent.parent
    return current_dir / "templates"


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
    template_dir = _get_template_dir("default").parent
    if not template_dir.exists():
        return ["default"]
    
    # TODO: implement template discovery from template directory
    return ["default", "blog", "api-only"]


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