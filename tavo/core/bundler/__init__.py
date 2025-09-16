"""
Tavo Bundler Module

This module provides SWC-based compilation and bundling for React components
without requiring Node.js at runtime.
"""

from .compiler import SWCCompiler
from .resolver import ImportResolver
from .deduplicator import ImportDeduplicator
from .installer import SWCInstaller
from .router import AppRouter

__all__ = ['SWCCompiler', 'ImportResolver', 'ImportDeduplicator', 'SWCInstaller', 'AppRouter']