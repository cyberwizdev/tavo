# Tavo Bundler Documentation

## Overview

The Tavo bundler is a Python-first front-end bundler designed specifically for the Tavo framework. It provides App Router semantics for React applications with server-side rendering (SSR) and client-side hydration capabilities.

## Features

- **App Router Integration**: Automatic route discovery based on file structure
- **SWC Compilation**: Fast TypeScript/JSX compilation using SWC CLI
- **Intelligent Caching**: File-based compilation caching with automatic invalidation
- **Development Server**: Hot reloading and live development features
- **Layout Composition**: Automatic nested layout composition
- **SSR & Hydration**: Separate builds for server and client execution

## Installation & Setup

### Prerequisites

The bundler requires SWC CLI to be installed globally:

```bash
# Using npm
npm install -g @swc/cli @swc/core

# Using yarn  
yarn global add @swc/cli @swc/core

# Using pnpm
pnpm add -g @swc/cli @swc/core
```

### Environment Variables

Configure the bundler using these environment variables:

- `TAVO_SWC_CMD`: Path to SWC binary (default: `swc`)
- `TAVO_SWC_TIMEOUT`: SWC compilation timeout in seconds (default: `30`)
- `TAVO_CACHE_DIR`: Cache directory name (default: `.tavo`)
- `TAVO_DEV_PORT`: Development server port (default: `3000`)
- `TAVO_SOURCE_MAPS`: Enable source maps (default: `false`)

## Usage

### Basic Usage

```python
from tavo.core.bundler import build, dev, clean

# Production build
build()

# Development server
dev()

# Clean cache
clean()
```

### Advanced Usage

```python
from pathlib import Path
from tavo.core.bundler import get_bundler

# Create bundler instance
bundler = get_bundler(Path.cwd())

# Get compilation statistics
stats = bundler.compiler.get_cache_stats()
print(f"Cache entries: {stats['total_entries']}")
print(f"Cache size: {stats['total_size_mb']} MB")

# Manual compilation
routes = bundler.resolver.resolve_routes()
for route in routes:
    files = list(route.all_files)
    result = bundler.compiler.compile_for_ssr(files)
    print(f"Compiled {route.route_path}: {result.output_size} bytes")
```

## Configuration

### Project Structure

The bundler expects this project structure:

```
project-root/
├── app/                    # App Router directory
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Home page
│   ├── about/
│   │   └── page.tsx       # About page
│   └── dashboard/
│       ├── layout.tsx     # Dashboard layout
│       ├── page.tsx       # Dashboard home
│       └── settings/
│           └── page.tsx   # Settings page
├── public/                # Static assets
├── components/            # Shared components
├── lib/                   # Utilities
└── dist/                  # Build output (generated)
    ├── client/            # Client bundles
    └── server/            # Server bundles
```

### Build Configuration

Create a `tavo.config.json` file in your project root:

```json
{
  "bundler": {
    "sourceMaps": false,
    "minify": true,
    "target": "es2020",
    "optimizeForSSR": true
  }
}
```

## Cache Management

The bundler uses intelligent caching to speed up compilation:

### Cache Structure

```
.tavo/
├── cache/                 # General cache
├── swc_cache/            # SWC compilation cache
│   ├── cache_index.pkl   # Cache metadata
│   └── *.tsx             # Debug bundled files
└── debug/                # Debug artifacts
```

### Cache Operations

```python
from tavo.core.bundler import get_bundler

bundler = get_bundler()

# Clear all cache
bundler.compiler.clear_cache()

# Clear cache older than 7 days
bundler.compiler.clear_cache(older_than_days=7)

# Get cache statistics
stats = bundler.compiler.get_cache_stats()
```

### Cache Security

⚠️ **Security Note**: The cache uses Python's pickle format by default for performance. Only use in trusted environments. For production or shared environments, consider enabling JSON caching:

```python
# Use JSON cache (slower but safer)
bundler = get_bundler()
bundler.cache_manager.use_json_cache = True
```

## Development Server

The development server provides hot reloading and live development features:

```python
from tavo.core.bundler import dev

# Start with default settings
dev()

# Custom port
dev(port=8080)

# Advanced usage
from tavo.core.bundler import get_bundler

bundler = get_bundler()

# Add change callback
@bundler.dev_server.on_change
def handle_change(changed_files):
    print(f"Files changed: {changed_files}")

bundler.dev_server.start(port=3000)
```

### Hot Module Replacement (HMR)

The bundler includes a simple HMR client that automatically reloads pages when files change. The HMR client connects via WebSocket and listens for update events.

## Troubleshooting

### Common Issues

#### SWC Not Found

```
RuntimeError: SWC is required but not available.
```

**Solution**: Install SWC CLI globally:
```bash
npm install -g @swc/cli @swc/core
```

Or set custom SWC path:
```bash
export TAVO_SWC_CMD=/path/to/swc
```

#### SWC Compilation Errors

**TypeScript errors**:
```
SWC compilation failed (code 1):
stderr: error TS2304: Cannot find name 'React'.
```

**Solutions**:
- Ensure React is imported: `import React from 'react'`
- Check TypeScript configuration in your components
- Verify all dependencies are properly imported

**Syntax errors**:
```
SWC compilation failed (code 1):
stderr: Unexpected token
```

**Solutions**:
- Check JSX/TSX syntax in your components
- Ensure proper file extensions (.tsx for JSX, .ts for TypeScript)
- Validate component exports (must have default export)

#### Cache Issues

**Stale cache**:
```python
# Force cache clear
from tavo.core.bundler import clean
clean()
```

**Cache corruption**:
```
Failed to load cache index: pickle data corrupted
```

**Solution**: Clear the cache directory:
```bash
rm -rf .tavo/swc_cache
```

#### Memory Issues

For large projects, you may encounter memory issues:

**Solutions**:
- Increase Node.js memory limit: `export NODE_OPTIONS="--max-old-space-size=4096"`
- Clear cache regularly: `clean(older_than_days=7)`
- Split large components into smaller files

### Debugging

#### Enable Debug Mode

```python
import logging
from tavo.core.bundler.utils import setup_logging

# Enable debug logging
setup_logging(level=logging.DEBUG)
```

#### Debug Artifacts

The bundler saves intermediate files for debugging:

- `.tavo/debug/current_compilation/`: Latest compilation artifacts
- `.tavo/debug/*_bundled.tsx`: Bundled TSX files for each compilation
- `.tavo/swc_cache/`: Cached compilation results

#### Compilation Statistics

```python
bundler = get_bundler()
stats = bundler.compiler.get_compilation_stats()

print(f"Total compilations: {stats['total_compilations']}")
print(f"Cache hits: {stats['cache_hits']}")
print(f"Cache misses: {stats['cache_misses']}")
print(f"Average compile time: {stats['total_time'] / stats['total_compilations']:.2f}s")
```

## Performance Tips

1. **Use caching**: Don't clear cache unnecessarily
2. **Organize components**: Keep components small and focused
3. **Import optimization**: Use specific imports instead of barrel exports
4. **File watching**: Let the dev server handle rebuilds automatically

## Integration Examples

### With Tavo CLI

```python
# tavo/cli/commands/dev.py
from pathlib import Path
from tavo.core.bundler import get_bundler

def dev_command(port=3000):
    """Start development server"""
    root = Path.cwd()
    bundler = get_bundler(root)
    
    print(f"Starting Tavo development server on port {port}")
    bundler.dev_server.start(port=port)

# tavo/cli/commands/build.py  
from pathlib import Path
from tavo.core.bundler import build

def build_command():
    """Build for production"""
    print("Building Tavo application...")
    result = build(Path.cwd())
    
    print(f"✓ Built {result['success']}/{result['routes']} routes")
    print(f"✓ Client bundle: {result['total_client_size']} bytes")
    print(f"✓ Server bundle: {result['total_server_size']} bytes")
```

## API Reference

See [api.md](api.md) for complete API documentation.