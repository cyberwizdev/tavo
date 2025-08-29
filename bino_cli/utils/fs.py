"""
Bino Filesystem Utilities

Helpers for filesystem operations used by the CLI scaffolder and installer.
"""

import shutil
import logging
from pathlib import Path
from typing import List, Optional, Callable, Iterator
import fnmatch
import stat

logger = logging.getLogger(__name__)


def copy_directory(
    source: Path, 
    destination: Path, 
    exclude_patterns: Optional[List[str]] = None,
    transform_fn: Optional[Callable[[Path, str], str]] = None
) -> None:
    """
    Copy directory with optional exclusions and content transformation.
    
    Args:
        source: Source directory to copy
        destination: Destination directory
        exclude_patterns: Glob patterns to exclude
        transform_fn: Function to transform file content (path, content) -> content
        
    Raises:
        FileNotFoundError: If source directory doesn't exist
        PermissionError: If unable to create destination or copy files
        
    Example:
        >>> copy_directory(Path("template"), Path("project"), ["*.pyc", "__pycache__"])
    """
    if not source.exists():
        raise FileNotFoundError(f"Source directory not found: {source}")
    
    if not source.is_dir():
        raise ValueError(f"Source is not a directory: {source}")
    
    exclude_patterns = exclude_patterns or []
    destination.mkdir(parents=True, exist_ok=True)
    
    for item in source.rglob("*"):
        if _should_exclude(item, source, exclude_patterns):
            continue
        
        relative_path = item.relative_to(source)
        dest_path = destination / relative_path
        
        if item.is_dir():
            dest_path.mkdir(parents=True, exist_ok=True)
        else:
            _copy_file_with_transform(item, dest_path, transform_fn)


def _should_exclude(path: Path, base_path: Path, patterns: List[str]) -> bool:
    """Check if path should be excluded based on patterns."""
    relative_path = path.relative_to(base_path)
    path_str = str(relative_path)
    
    for pattern in patterns:
        if fnmatch.fnmatch(path_str, pattern):
            return True
        if fnmatch.fnmatch(path.name, pattern):
            return True
    
    return False


def _copy_file_with_transform(
    source: Path, 
    destination: Path, 
    transform_fn: Optional[Callable[[Path, str], str]]
) -> None:
    """Copy file with optional content transformation."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    if transform_fn and _is_text_file(source):
        try:
            content = source.read_text(encoding="utf-8")
            transformed_content = transform_fn(source, content)
            destination.write_text(transformed_content, encoding="utf-8")
        except UnicodeDecodeError:
            # Fall back to binary copy for non-text files
            shutil.copy2(source, destination)
    else:
        shutil.copy2(source, destination)
    
    logger.debug(f"Copied {source} -> {destination}")


def _is_text_file(path: Path) -> bool:
    """Check if file is likely a text file based on extension."""
    text_extensions = {
        ".py", ".tsx", ".ts", ".js", ".jsx", ".json", ".md", ".txt",
        ".yaml", ".yml", ".toml", ".cfg", ".ini", ".env", ".html",
        ".css", ".scss", ".sass", ".less", ".xml", ".svg"
    }
    return path.suffix.lower() in text_extensions


def ensure_directory(path: Path, mode: int = 0o755) -> None:
    """
    Ensure directory exists with proper permissions.
    
    Args:
        path: Directory path to create
        mode: Directory permissions (default: 755)
        
    Example:
        >>> ensure_directory(Path("logs"))
    """
    if not path.exists():
        path.mkdir(parents=True, mode=mode)
        logger.debug(f"Created directory: {path}")
    elif not path.is_dir():
        raise FileExistsError(f"Path exists but is not a directory: {path}")


def safe_remove(path: Path, recursive: bool = False) -> bool:
    """
    Safely remove file or directory.
    
    Args:
        path: Path to remove
        recursive: Whether to remove directories recursively
        
    Returns:
        True if removed successfully, False if path didn't exist
        
    Example:
        >>> safe_remove(Path("temp_file.txt"))
        True
    """
    if not path.exists():
        return False
    
    try:
        if path.is_file():
            path.unlink()
        elif path.is_dir() and recursive:
            shutil.rmtree(path)
        elif path.is_dir():
            path.rmdir()  # Only works if empty
        
        logger.debug(f"Removed: {path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to remove {path}: {e}")
        raise


def find_files(
    directory: Path, 
    pattern: str = "*", 
    recursive: bool = True
) -> Iterator[Path]:
    """
    Find files matching pattern in directory.
    
    Args:
        directory: Directory to search
        pattern: Glob pattern to match
        recursive: Whether to search recursively
        
    Yields:
        Matching file paths
        
    Example:
        >>> list(find_files(Path("src"), "*.py"))
        [Path('src/main.py'), Path('src/utils.py')]
    """
    if not directory.exists():
        return
    
    if recursive:
        yield from directory.rglob(pattern)
    else:
        yield from directory.glob(pattern)


def get_file_size(path: Path) -> int:
    """
    Get file size in bytes.
    
    Args:
        path: File path
        
    Returns:
        File size in bytes
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    return path.stat().st_size


def make_executable(path: Path) -> None:
    """
    Make file executable on Unix systems.
    
    Args:
        path: File path to make executable
    """
    if sys.platform != "win32":
        current_mode = path.stat().st_mode
        path.chmod(current_mode | stat.S_IEXEC)
        logger.debug(f"Made executable: {path}")


if __name__ == "__main__":
    # Example usage
    temp_dir = Path("temp_test")
    ensure_directory(temp_dir)
    
    test_file = temp_dir / "test.txt"
    test_file.write_text("Hello, Bino!")
    
    print(f"File size: {get_file_size(test_file)} bytes")
    
    # Cleanup
    safe_remove(temp_dir, recursive=True)

# Unit tests as comments:
# 1. test_copy_directory_with_exclusions() - verify exclusion patterns work correctly
# 2. test_safe_remove_handles_missing_files() - test graceful handling of non-existent files
# 3. test_find_files_pattern_matching() - verify glob pattern matching works as expected