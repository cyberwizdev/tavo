"""
Common utility functions for the bundler
"""

import os
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Union, Optional
import json

# Setup module logger
logger = logging.getLogger(__name__)

def normalize_path(path: Union[str, Path]) -> Path:
    """
    Normalize a file path
    
    Args:
        path: Path to normalize
        
    Returns:
        Normalized Path object
    """
    return Path(path).resolve()


def read_file(file_path: Union[str, Path], encoding: str = 'utf-8') -> str:
    """
    Read file content safely
    
    Args:
        file_path: Path to file
        encoding: File encoding
        
    Returns:
        File content as string
        
    Raises:
        IOError: If file cannot be read
    """
    try:
        path = Path(file_path)
        with open(path, 'r', encoding=encoding) as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        raise IOError(f"Cannot read file {file_path}: {e}") from e


def write_file_atomic(file_path: Union[str, Path], content: str, encoding: str = 'utf-8') -> None:
    """
    Write file content atomically (write to temp, then move)
    
    Args:
        file_path: Target file path
        content: Content to write
        encoding: File encoding
        
    Raises:
        IOError: If file cannot be written
    """
    try:
        path = Path(file_path)
        
        # Ensure parent directory exists
        safe_mkdir(path.parent)
        
        # Write to temporary file first
        with tempfile.NamedTemporaryFile(
            mode='w', 
            encoding=encoding, 
            dir=path.parent, 
            delete=False
        ) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # Atomic move
        shutil.move(tmp_path, path)
        
    except Exception as e:
        # Cleanup temp file if it exists
        try:
            if 'tmp_path' in locals():
                Path(tmp_path).unlink()
        except:
            pass
        
        logger.error(f"Failed to write file {file_path}: {e}")
        raise IOError(f"Cannot write file {file_path}: {e}") from e


def safe_mkdir(directory: Union[str, Path]) -> Path:
    """
    Create directory safely (no error if exists)
    
    Args:
        directory: Directory path to create
        
    Returns:
        Path object of created directory
    """
    path = Path(directory)
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        raise OSError(f"Cannot create directory {directory}: {e}") from e


def safe_rmdir(directory: Union[str, Path], ignore_errors: bool = True) -> bool:
    """
    Remove directory safely
    
    Args:
        directory: Directory to remove
        ignore_errors: Whether to ignore errors
        
    Returns:
        True if removed successfully
    """
    try:
        path = Path(directory)
        if path.exists():
            shutil.rmtree(path)
        return True
    except Exception as e:
        if not ignore_errors:
            logger.error(f"Failed to remove directory {directory}: {e}")
            raise
        return False


def get_file_size(file_path: Union[str, Path]) -> int:
    """
    Get file size in bytes
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in bytes, 0 if file doesn't exist
    """
    try:
        return Path(file_path).stat().st_size
    except (OSError, IOError):
        return 0


def get_relative_path(file_path: Union[str, Path], base_path: Union[str, Path]) -> str:
    """
    Get relative path from base path
    
    Args:
        file_path: Target file path
        base_path: Base path
        
    Returns:
        Relative path as string
    """
    try:
        return str(Path(file_path).relative_to(Path(base_path)))
    except ValueError:
        # If not relative, return absolute path
        return str(Path(file_path).resolve())


def copy_file(src: Union[str, Path], dst: Union[str, Path], preserve_metadata: bool = True) -> None:
    """
    Copy file safely
    
    Args:
        src: Source file path
        dst: Destination file path
        preserve_metadata: Whether to preserve file metadata
        
    Raises:
        IOError: If copy fails
    """
    try:
        src_path = Path(src)
        dst_path = Path(dst)
        
        # Ensure destination directory exists
        safe_mkdir(dst_path.parent)
        
        if preserve_metadata:
            shutil.copy2(src_path, dst_path)
        else:
            shutil.copy(src_path, dst_path)
            
    except Exception as e:
        logger.error(f"Failed to copy {src} to {dst}: {e}")
        raise IOError(f"Cannot copy file: {e}") from e


def find_files(directory: Union[str, Path], pattern: str = "*", recursive: bool = True) -> list[Path]:
    """
    Find files matching pattern in directory
    
    Args:
        directory: Directory to search
        pattern: File pattern (glob style)
        recursive: Whether to search recursively
        
    Returns:
        List of matching file paths
    """
    try:
        path = Path(directory)
        if not path.exists():
            return []
        
        if recursive:
            return list(path.rglob(pattern))
        else:
            return list(path.glob(pattern))
            
    except Exception as e:
        logger.warning(f"Failed to find files in {directory}: {e}")
        return []


def load_json_file(file_path: Union[str, Path], default: Optional[dict] = None) -> dict:
    """
    Load JSON file safely
    
    Args:
        file_path: Path to JSON file
        default: Default value if file doesn't exist or is invalid
        
    Returns:
        Parsed JSON data or default value
    """
    path = Path(file_path)
    
    if not path.exists():
        return default or {}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load JSON file {file_path}: {e}")
        return default or {}


def save_json_file(file_path: Union[str, Path], data: dict, indent: int = 2) -> bool:
    """
    Save data to JSON file safely
    
    Args:
        file_path: Target JSON file path
        data: Data to save
        indent: JSON indentation
        
    Returns:
        True if saved successfully
    """
    try:
        content = json.dumps(data, indent=indent, ensure_ascii=False)
        write_file_atomic(file_path, content)
        return True
    except Exception as e:
        logger.error(f"Failed to save JSON file {file_path}: {e}")
        return False


def setup_logging(level: int = logging.INFO, format_str: Optional[str] = None) -> None:
    """
    Setup logging for the bundler
    
    Args:
        level: Logging level
        format_str: Custom format string
    """
    if format_str is None:
        format_str = "[tavo:bundler] %(levelname)s: %(message)s"
    
    # Configure the bundler logger
    bundler_logger = logging.getLogger('tavo.core.bundler')
    
    if not bundler_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(format_str)
        handler.setFormatter(formatter)
        bundler_logger.addHandler(handler)
        bundler_logger.setLevel(level)
        bundler_logger.propagate = False


def is_text_file(file_path: Union[str, Path]) -> bool:
    """
    Check if file is a text file
    
    Args:
        file_path: Path to check
        
    Returns:
        True if file appears to be text
    """
    try:
        path = Path(file_path)
        
        # Check by extension first
        text_extensions = {
            '.txt', '.md', '.json', '.yaml', '.yml', '.toml',
            '.js', '.jsx', '.ts', '.tsx', '.css', '.scss', '.sass',
            '.html', '.htm', '.xml', '.svg',
            '.py', '.rb', '.php', '.java', '.c', '.cpp', '.h',
            '.sh', '.bash', '.zsh', '.fish',
            '.config', '.conf', '.ini', '.env'
        }
        
        if path.suffix.lower() in text_extensions:
            return True
        
        # Try reading first few bytes
        with open(path, 'rb') as f:
            sample = f.read(1024)
            
        # Check for null bytes (binary indicator)
        if b'\x00' in sample:
            return False
        
        # Try to decode as text
        try:
            sample.decode('utf-8')
            return True
        except UnicodeDecodeError:
            try:
                sample.decode('latin-1')
                return True
            except UnicodeDecodeError:
                return False
                
    except Exception:
        return False


def get_file_hash(file_path: Union[str, Path], algorithm: str = 'sha256') -> str:
    """
    Calculate hash of file content
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, md5, etc.)
        
    Returns:
        Hex digest of file hash
    """
    import hashlib
    
    try:
        hasher = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        
        return hasher.hexdigest()
        
    except Exception as e:
        logger.warning(f"Failed to calculate hash for {file_path}: {e}")
        return ""


def format_bytes(size_bytes: int) -> str:
    """
    Format byte size as human readable string
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.2 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    
    return f"{size:.1f} {units[unit_index]}"


def measure_time(func):
    """
    Decorator to measure function execution time
    
    Args:
        func: Function to measure
        
    Returns:
        Decorated function that logs execution time
    """
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        logger.debug(f"{func.__name__} executed in {execution_time:.3f}s")
        
        return result
    
    return wrapper