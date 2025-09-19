"""
Tavo Core Bundler - Python-based front-end bundler for Tavo framework

Provides build and development tools for React App Router applications with SWC compilation.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import logging

from .compiler import SWCCompiler
from .resolver import ImportResolver
from .devserver import DevServer
from .cache import CacheManager
from .installer import SWCInstaller

# Setup logging
logger = logging.getLogger(__name__)

__version__ = "0.1.0"
__all__ = ["get_bundler", "build", "dev", "clean", "Bundler"]


class Bundler:
    """Main bundler class that coordinates all components"""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.resolver = ImportResolver(project_root)
        self.compiler = SWCCompiler(project_root)
        self.dev_server = DevServer(project_root, self.compiler, self.resolver)
        self.cache_manager = CacheManager(project_root)
        self.swc_installer = SWCInstaller()
        
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive bundler statistics"""
        return {
            "project_root": str(self.project_root),
            "compiler_stats": self.compiler.get_cache_stats(),
            "routes": len(self.resolver.resolve_routes()),
            "version": __version__
        }


def get_bundler(project_root: Path | str = ".") -> Bundler:
    """
    Get a configured bundler instance
    
    Args:
        project_root: Path to the project root directory
        
    Returns:
        Configured Bundler instance
    """
    project_root = Path(project_root).resolve()
    return Bundler(project_root)


def build(project_root: str | Path = ".") -> Dict[str, Any]:
    """
    Build the project for production
    
    Args:
        project_root: Path to the project root directory
        
    Returns:
        Build statistics and results
    """
    bundler = get_bundler(project_root)
    return bundler.compiler.build_all()


def dev(project_root: str | Path = ".", port: int = 3000) -> None:
    """
    Start development server with hot reloading
    
    Args:
        project_root: Path to the project root directory  
        port: Development server port
    """
    bundler = get_bundler(project_root)
    bundler.dev_server.start(port=port)


def clean(project_root: str | Path = ".", older_than_days: Optional[int] = None) -> None:
    """
    Clean build artifacts and caches
    
    Args:
        project_root: Path to the project root directory
        older_than_days: Only clean entries older than specified days (None = clean all)
    """
    bundler = get_bundler(project_root)
    bundler.compiler.clear_cache(older_than_days=older_than_days)
    bundler.cache_manager.clear_cache(older_than_days=older_than_days)
    logger.info("Cache cleared successfully")