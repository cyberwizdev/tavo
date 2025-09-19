"""
Constants and default values for the Tavo bundler
"""

from pathlib import Path
import os

# Directory names
APP_DIR_NAME = "app"
DIST_DIR = "dist"
TAVO_CACHE_DIR = ".tavo"
PUBLIC_DIR = "public"

# File extensions
SUPPORTED_EXTENSIONS = {".tsx", ".ts", ".jsx", ".js"}
LAYOUT_FILES = {"layout.tsx", "layout.ts", "layout.jsx", "layout.js"}
PAGE_FILES = {"page.tsx", "page.ts", "page.jsx", "page.js"}
LOADING_FILES = {"loading.tsx", "loading.ts", "loading.jsx", "loading.js"}
HEAD_FILES = {"head.tsx", "head.ts", "head.jsx", "head.js"}
ROUTE_FILES = {"route.ts", "route.js"}

# Route patterns
DYNAMIC_ROUTE_PATTERN = r"\[([^\]]+)\]"
CATCH_ALL_ROUTE_PATTERN = r"\[\[\.\.\.([^\]]+)\]\]"

# Environment variable defaults
DEFAULT_SWC_TIMEOUT = int(os.getenv("TAVO_SWC_TIMEOUT", "30"))
DEFAULT_SWC_COMMAND = os.getenv("TAVO_SWC_CMD", "swc")
DEFAULT_CACHE_DIR = os.getenv("TAVO_CACHE_DIR", TAVO_CACHE_DIR)
DEFAULT_DEV_PORT = int(os.getenv("TAVO_DEV_PORT", "3000"))

# Build configuration
BUILD_MODES = {"development", "production"}
COMPILATION_TYPES = {"ssr", "hydration", "default"}

# Cache settings
DEFAULT_CACHE_MAX_ENTRIES = 1000
DEFAULT_CACHE_MAX_AGE_DAYS = 30

# Development server settings
HMR_WEBSOCKET_PATH = "/_tavo_hmr"
DEV_SERVER_HOST = "localhost"


PROD_SERVER = "example.com"
# Template placeholders
SSR_HTML_PLACEHOLDER = "%%SSR_HTML%%"
INITIAL_STATE_PLACEHOLDER = "%%INITIAL_STATE%%"
CLIENT_BUNDLE_PLACEHOLDER = "%%CLIENT_BUNDLE%%"
HMR_SCRIPT_PLACEHOLDER = "%%HMR_SCRIPT%%"

# Logging format
LOG_FORMAT = "[tavo:bundler] %(levelname)s: %(message)s"