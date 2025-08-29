"""
Tavo CLI Package

A command-line interface for the Tavo full-stack framework that combines
Python backends with Rust/SWC-powered React SSR.
"""

__version__ = "0.1.0"
__author__ = "Tavo Framework Team"

from .main import app

__all__ = ["app"]