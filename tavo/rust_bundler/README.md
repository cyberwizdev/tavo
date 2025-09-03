# SSR Bundler

A Rust-based SSR bundler for TypeScript/JSX applications that compiles TS/TSX & JSX using SWC and outputs JSON for a Python SSR bridge.

## Features

- **File-system based routing** with support for static and dynamic routes
- **TypeScript/JSX compilation** using SWC (ultra-fast Rust compiler)
- **Server-side rendering** with rquickjs JavaScript runtime
- **Client-side hydration** with automatic parameter injection
- **Layout chain support** for nested layouts
- **JSON output** for easy integration with Python SSR bridges

## Building

```bash
cargo build --release
```

## Usage

### Basic Commands

**Hydration mode** (default):
```bash
./target/release/ssr-bundler --route /blog/hello-world --app-dir ./app --compile-type hydration
```

**Server-side rendering**:
```bash
./target/release/ssr-bundler --route /blog/hello-world --app-dir ./app --compile-type ssr
```

### CLI Options

- `--route <string>` - The route to render (e.g., `/`, `/about`, `/blog/hello-world`)
- `--app-dir <path>` - Path to the app directory (default: `./app`)
- `--compile-type <hydration|ssr>` - Compilation type (default: `hydration`)
- `--output <json|stdout>` - Output format (default: `json`)
- `--minify` - Enable code minification
- `--sourcemap` - Generate source maps
- `--timeout-ms <u64>` - Timeout in milliseconds for SSR execution (default: `120000`)
- `--log-level <error|warn|info|debug|trace>` - Log level (default: `warn`)

## Router Assumptions

### Static Routes
- `app/page.tsx` → `/`
- `app/about/page.tsx` → `/about`
- `app/blog/page.tsx` → `/blog`

### Dynamic Routes
- `app/blog/[slug]/page.tsx` → `/blog/hello-world` matches with `{ "slug": "hello-world" }`
- `app/user/[id]/profile/page.tsx` → `/user/123/profile` matches with `{ "id": "123" }`

### Layouts
- Nested layouts are automatically discovered and applied
- Only `page.tsx` files are treated as server-only components
- Layouts and other components remain client-hydrated

## Output Format

The bundler outputs JSON to stdout with the following structure:

```json
{
  "html": "<!DOCTYPE html>...",
  "js": "/* transpiled client bundle */",
  "params": { "slug": "hello-world" }
}
```

### Error Output

On error, JSON is output to stderr and the process exits with code 1:

```json
{
  "error": {
    "kind": "RouteNotFound",
    "message": "No matching page for /blog/foo"
  }
}
```

## Architecture

- **CLI** (`src/cli.rs`) - Command-line interface and argument parsing
- **Router** (`src/fs_router.rs`) - File-system based routing with dynamic parameter extraction
- **SWC Build** (`src/swc_build.rs`) - TypeScript/JSX compilation using SWC
- **Bundler** (`src/bundler.rs`) - Virtual entry generation and module bundling
- **SSR** (`src/ssr.rs`) - Server-side rendering using rquickjs JavaScript runtime
- **Output** (`src/output.rs`) - JSON formatting and output management
- **Utils** (`src/utils.rs`) - Logging and utility functions

## Key Features

### Parameter Injection
- **Hydration mode**: Parameters are injected as `window.__TAVO_PARAMS__`
- **SSR mode**: Parameters are passed as props to the page component
- Custom `useParams()` hook available for accessing parameters in components

### Layout Chain
- Automatically discovers and applies nested layouts
- Layouts wrap page components in the correct hierarchy
- Both layouts and pages receive `params` as props

### Error Handling
- Comprehensive error reporting with structured JSON output
- Timeout protection for SSR execution
- Graceful handling of missing routes and compilation errors

## Examples

### Hydration Example
```bash
ssr-bundler --route /blog/hello-world --compile-type hydration --minify
```

### SSR Example
```bash
ssr-bundler --route /user/123/profile --compile-type ssr --timeout-ms 30000
```

### Debug Mode
```bash
ssr-bundler --route /about --log-level debug --output stdout
```