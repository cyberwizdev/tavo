"""
🚀 Tavo - Modern full-stack framework CLI

Tavo combines:
- ⚡ Python backend (FastAPI/Starlette base)  
- 🦀 Rust + SWC powered SSR for React (with App Router support)  
- 🔥 Client hydration & HMR with no Node.js required  
- 🛠️ CLI scaffolding for apps, routes, components, and APIs  
"""

from .core import bundler as Bundler
from .core.ssr import SSRRenderer
from .core.router.app_router import AppRouter
from .core.router.api_router import APIRouter
from .core.orm.models import BaseModel
from .core.orm.fields import Field, StringField as CharField, IntegerField, DateTimeField

__version__ = "0.1.0"
__author__ = "CyberwizDev"
__description__ = "🚀 Modern full-stack framework CLI with Python backend, Rust+SWC powered SSR for React, and HMR"

__all__ = [
    "Bundler",
    "SSRRenderer", 
    "AppRouter",
    "APIRouter",
    "BaseModel",
    "Field",
    "CharField",
    "IntegerField", 
    "DateTimeField",
]