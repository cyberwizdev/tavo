# Bundler API Reference

## Core Functions

### `get_bundler(project_root)`

Creates and returns a configured Bundler instance.

**Parameters:**
- `project_root` (Path | str): Path to project root directory (default: current directory)

**Returns:** `Bundler` instance

**Example:**
```python
from tavo.core.bundler import get_bundler
from pathlib import Path

bundler = get_bundler(Path("/path/to/project"))
```

### `build(project_root)`

Builds the project for production.

**Parameters:**
- `project_root` (Path | str): Path to project root directory

**Returns:** Dict with build statistics and results

**Example:**
```python
from tavo.core.bundler import build

result = build()
print(f"Built {result['success']} routes")
```

### `dev(project_root, port)`

Starts development server with hot reloading.

**Parameters:**
- `project_root` (Path | str): Path to project root directory
- `port` (int): Development server port (default: 3000)

**Returns:** None (blocks until server is stopped)

**Example:**
```python
from tavo.core.bundler import dev

dev(port=8080)
```

### `clean(project_root, older_than_days)`

Cleans build artifacts and caches.

**Parameters:**
- `project_root` (Path | str): Path to project root directory
- `older_than_days` (Optional[int]): Only clean entries older than specified days (None = clean all)

**Returns:** None

**Example:**
```python
from tavo.core.bundler import clean

# Clean all cache
clean()

# Clean cache older than 7 days
clean(older_than_days=7)
```

## Bundler Class

### `Bundler.__init__(project_root)`

**Parameters:**
- `project_root` (Path): Path to project root directory

### `Bundler.get_stats()`

Get comprehensive bundler statistics.

**Returns:** Dict containing:
- `project_root`: Project root path
- `compiler_stats`: Compiler cache statistics
- `routes`: Number of discovered routes
- `version`: Bundler version

## SWCCompiler Class

### `SWCCompiler.__init__(project_root)`

**Parameters:**
- `project_root` (Path): Path to project root directory

### `SWCCompiler.compile_files(files, compilation_type)`

Compile a list of React/TypeScript files with caching.

**Parameters:**
- `files` (List[Path]): List of source files to compile
- `compilation_type` (str): Compilation type ("ssr", "hydration", "default")

**Returns:** `CompilationResult` object

**Example:**
```python
from pathlib import Path

files = [Path("app/page.tsx"), Path("app/layout.tsx")]
result = compiler.compile_files(files, "ssr")

print(f"Output size: {result.output_size} bytes")
print(f"Cache hit: {result.cache_hit}")
print(f"Compilation time: {result.compilation_time:.2f}s")
```

### `SWCCompiler.compile_for_ssr(files)`

Compile files specifically for server-side rendering.

**Parameters:**
- `files` (List[Path]): List of source files

**Returns:** `CompilationResult` with SSR optimizations applied

### `SWCCompiler.compile_for_hydration(files)`

Compile files for client-side hydration.

**Parameters:**
- `files` (List[Path]): List of source files  

**Returns:** `CompilationResult` with client optimizations applied

### `SWCCompiler.clear_cache(older_than_days)`

Clear compilation cache.

**Parameters:**
- `older_than_days` (Optional[int]): Only clear entries older than specified days

**Returns:** None

### `SWCCompiler.get_cache_stats()`

Get cache statistics.

**Returns:** Dict containing:
- `total_entries`: Number of cache entries
- `total_size_bytes`: Total cache size in bytes
- `total_size_mb`: Total cache size in MB
- `cache_hits`: Number of cache hits
- `cache_misses`: Number of cache misses
- `total_compilations`: Total compilation count

### `SWCCompiler.build_all()`

Build all routes for production.

**Returns:** Dict with build results:
- `routes`: Total number of routes
- `success`: Number of successfully built routes
- `errors`: Number of failed routes
- `total_client_size`: Total client bundle size
- `total_server_size`: Total server bundle size
- `build_results`: Detailed results per route
- `output_dirs`: Output directory paths

## ImportResolver Class

### `ImportResolver.__init__(project_root)`

**Parameters:**
- `project_root` (Path): Path to project root directory

### `ImportResolver.resolve_routes()`

Resolve all routes from the app directory.

**Returns:** List[RouteEntry] representing all discovered routes

**Example:**
```python
routes = resolver.resolve_routes()

for route in routes:
    print(f"Route: {route.route_path}")
    print(f"  Page file: {route.page_file}")
    print(f"  Layouts: {[str(l) for l in route.layout_chain]}")
    print(f"  All files: {len(route.all_files)}")
```

### `ImportResolver.create_entry_bundle_files_for_route(route_entry)`

Get list of source files needed to build a route bundle.

**Parameters:**
- `route_entry` (RouteEntry): Route entry to get files for

**Returns:** List[Path] of required source files

### `ImportResolver.create_single_file_for_swc(files, temp_dir)`

Create a single bundled TSX file from multiple source files.

**Parameters:**
- `files` (List[Path]): Source files to bundle
- `temp_dir` (Path): Temporary directory for bundled file

**Returns:** Path to the bundled file

### `ImportResolver.invalidate_cache()`

Invalidate the internal route resolution cache.

**Returns:** None

## RouteEntry Class

Represents a complete route with all associated files.

### Properties:
- `route_path` (str): URL path for the route (e.g., "/dashboard/settings")
- `layout_chain` (List[Path]): Layout files from outermost to innermost
- `page_file` (Optional[Path]): Main page component file
- `loading_file` (Optional[Path]): Loading component file
- `head_file` (Optional[Path]): Head component file  
- `route_file` (Optional[Path]): API route handler file
- `all_files` (Set[Path]): All files associated with this route

## CompilationResult Class

Result of a compilation operation.

### Properties:
- `compiled_js` (str): Compiled JavaScript output
- `bundled_tsx_path` (Optional[Path]): Path to debug bundled TSX file
- `source_files` (List[Path]): Source files that were compiled
- `cache_hit` (bool): Whether result came from cache
- `compilation_time` (float): Time taken for compilation in seconds
- `output_size` (int): Size of compiled output in bytes

## DevServer Class

### `DevServer.__init__(project_root, compiler, resolver)`

**Parameters:**
- `project_root` (Path): Project root directory
- `compiler` (SWCCompiler): Compiler instance
- `resolver` (ImportResolver): Import resolver instance

### `DevServer.start(port, host)`

Start the development server.

**Parameters:**
- `port` (int): Server port (default: 3000)
- `host` (str): Server host (default: "localhost")

**Returns:** None (blocks until server is stopped)

### `DevServer.stop()`

Stop the development server.

**Returns:** None

### `DevServer.add_change_callback(callback)`

Add callback for file change events.

**Parameters:**
- `callback` (Callable): Function to call when files change

**Returns:** None

### `DevServer.on_change(callback)`

Decorator for change callbacks.

**Parameters:**
- `callback` (Callable): Callback function

**Returns:** The callback function (for use as decorator)

**Example:**
```python
@dev_server.on_change
def handle_file_change(changed_files):
    print(f"Files changed: {changed_files}")
```

### `DevServer.handle_file_change(changed_files)`

Handle file change events (called automatically by file watcher).

**Parameters:**
- `changed_files` (List[Path]): List of changed files

**Returns:** None

### `DevServer.get_stats()`

Get development server statistics.

**Returns:** Dict with server status and statistics

## LayoutComposer Class

### `LayoutComposer.compose_layouts(layout_files, page_file)`

Compose layout files and page into a single TSX component.

**Parameters:**
- `layout_files` (List[Path]): Layout file paths (outermost to innermost)
- `page_file` (Path): Page component file path

**Returns:** Composed TSX content as string

### `LayoutComposer.compose_layouts_clean(layout_contents, page_content)`

Compose layout contents and page content into single TSX.

**Parameters:**
- `layout_contents` (List[str]): Layout file contents (outermost to innermost)
- `page_content` (str): Page component content

**Returns:** Composed TSX content as string

## TemplateManager Class

### `TemplateManager.__init__(project_root)`

**Parameters:**
- `project_root` (Path): Project root directory

### `TemplateManager.render_html(ssr_html, state, client_script_path)`

Render complete HTML page.

**Parameters:**
- `ssr_html` (str): Server-side rendered HTML content
- `state` (Dict[str, Any]): Initial application state
- `client_script_path` (str): Path to client bundle

**Returns:** Complete HTML document as string

### `TemplateManager.render_error_page(error_message)`

Render error page.

**Parameters:**
- `error_message` (str): Error message to display

**Returns:** Error HTML page as string

### `TemplateManager.inject_hmr_script(html)`

Inject HMR client script into HTML.

**Parameters:**
- `html` (str): HTML content to inject script into

**Returns:** HTML with HMR script injected

## SWCInstaller Class

### `SWCInstaller.ensure_swc_available()`

Check if SWC is available and working.

**Returns:** bool - True if SWC is available

### `SWCInstaller.get_swc_command()`

Get the SWC command to use.

**Returns:** str - SWC command path or name

### `SWCInstaller.get_version()`

Get SWC version if available.

**Returns:** Optional[str] - Version string or None

### `SWCInstaller.get_installation_instructions()`

Get instructions for installing SWC.

**Returns:** str - Installation instructions

### `SWCInstaller.check_and_raise_if_unavailable()`

Check SWC availability and raise error with instructions if not available.

**Raises:** RuntimeError if SWC is not available

## CacheManager Class

### `CacheManager.__init__(project_root, use_json_cache)`

**Parameters:**
- `project_root` (Path): Project root directory
- `use_json_cache` (bool): Use JSON instead of pickle for cache (default: False)

### `CacheManager.store(key, data, category)`

Store data in cache.

**Parameters:**
- `key` (str): Cache key
- `data` (Any): Data to store
- `category` (str): Cache category (default: "default")

**Returns:** bool - True if stored successfully

### `CacheManager.retrieve(key, category)`

Retrieve data from cache.

**Parameters:**
- `key` (str): Cache key
- `category` (str): Cache category (default: "default")

**Returns:** Optional[Any] - Cached data or None if not found

### `CacheManager.clear_cache(category, older_than_days)`

Clear cache entries.

**Parameters:**
- `category` (Optional[str]): Only clear specific category (None = all)
- `older_than_days` (Optional[int]): Only clear entries older than specified days

**Returns:** None

### `CacheManager.get_stats(category)`

Get cache statistics.

**Parameters:**
- `category` (Optional[str]): Get stats for specific category (None = all)

**Returns:** Dict with cache statistics

## Error Handling

The bundler provides specific exceptions for different error scenarios:

### Common Exceptions

- `RuntimeError`: SWC not available or compilation failed
- `IOError`: File read/write errors
- `ValueError`: Invalid configuration or parameters
- `OSError`: Directory creation or filesystem errors

### Error Recovery

Most operations include automatic error recovery:

```python
try:
    result = compiler.compile_files(files)
except RuntimeError as e:
    if "SWC is not available" in str(e):
        print("Please install SWC: npm install -g @swc/cli @swc/core")
    else:
        print(f"Compilation failed: {e}")
```

## Environment Variables

Configure the bundler behavior using these environment variables:

- `TAVO_SWC_CMD`: SWC command path (default: "swc")
- `TAVO_SWC_TIMEOUT`: Compilation timeout in seconds (default: 30)
- `TAVO_CACHE_DIR`: Cache directory name (default: ".tavo")
- `TAVO_DEV_PORT`: Default development server port (default: 3000)
- `TAVO_SOURCE_MAPS`: Enable source maps (default: "false")
- `NODE_ENV`: Node.js environment ("development" or "production")
- `NODE_OPTIONS`: Node.js options (e.g., "--max-old-space-size=4096")

## Integration Examples

### CLI Integration

```python
# tavo/cli/commands/dev.py
from pathlib import Path
from tavo.core.bundler import get_bundler

def dev_command(port: int = 3000):
    """Start development server"""
    root = Path.cwd()
    bundler = get_bundler(root)
    
    print(f"Starting Tavo development server on port {port}")
    bundler.dev_server.start(port=port)
```

### Custom Build Pipeline

```python
from tavo.core.bundler import get_bundler
from pathlib import Path

def custom_build_pipeline():
    bundler = get_bundler(Path.cwd())
    
    # Get all routes
    routes = bundler.resolver.resolve_routes()
    
    # Build each route with custom logic
    for route in routes:
        print(f"Building {route.route_path}...")
        
        files = list(route.all_files)
        
        # Compile for client and server
        client_result = bundler.compiler.compile_for_hydration(files)
        server_result = bundler.compiler.compile_for_ssr(files)
        
        # Custom post-processing
        if client_result.output_size > 100000:  # 100KB
            print(f"Warning: Large client bundle for {route.route_path}")
        
        # Save results
        # ... custom save logic
```

This API provides comprehensive control over the bundling process while maintaining simplicity for common use cases.