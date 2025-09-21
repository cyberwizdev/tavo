# MySSR - Rust SSR + Hydration Compiler

A high-performance Rust-based compiler that transpiles and executes React components using SWC for both Server-Side Rendering (SSR) and client-side hydration.

## Features

- **CLI Interface**: Simple command-line tool for generating SSR HTML and hydration scripts
- **SWC Integration**: Uses SWC for fast TypeScript/JSX parsing, transformation, and minification
- **Pure Rust Runtime**: Uses Boa engine for JavaScript execution without external Node.js dependencies
- **Cross-platform**: Works on Windows, macOS, and Linux

## Installation

```bash
cargo build --release
```

The binary will be available at `target/release/myssr`.

## Usage

### Basic Commands

```bash
# Generate SSR HTML only
myssr --entry src/App.tsx --ssr

# Generate hydration script only
myssr --entry src/App.tsx --hydrate

# Generate both and save to file
myssr --entry src/App.tsx --ssr --hydrate --out dist/index.html

# Save individual outputs
myssr --entry src/App.tsx --ssr --out dist/index.html
myssr --entry src/App.tsx --hydrate --out dist/client.js
```

### Example Project Structure

```
my-react-app/
├── src/
│   ├── App.tsx
│   ├── components/
│   │   ├── Header.tsx
│   │   └── Footer.tsx
│   └── utils/
│       └── helpers.ts
├── dist/
└── package.json
```

### Example App.tsx

```tsx
import React from 'react';
import Header from './components/Header';
import Footer from './components/Footer';

interface AppProps {
  title?: string;
}

export default function App({ title = "My App" }: AppProps) {
  return (
    <div className="app">
      <Header title={title} />
      <main>
        <h1>Welcome to {title}</h1>
        <p>This is server-side rendered content!</p>
      </main>
      <Footer />
    </div>
  );
}
```

## How It Works

### SSR Mode (`--ssr`)

1. **Parse**: Uses SWC to parse TypeScript/JSX files
2. **Transform**: Strips TypeScript types and converts JSX to `React.createElement` calls
3. **Bundle**: Resolves imports and creates a dependency graph
4. **Execute**: Runs the transpiled code in Boa JavaScript engine
5. **Render**: Uses a mock ReactDOMServer to render components to HTML strings

### Hydration Mode (`--hydrate`)

1. **Parse & Transform**: Same as SSR mode
2. **Bundle**: Creates a single JavaScript bundle with all dependencies
3. **Inject Hydration**: Adds hydration code that calls `hydrateRoot`
4. **Minify**: Uses SWC minifier to optimize the output
5. **Output**: Produces a standalone JavaScript file for the browser

### Combined Mode (`--ssr --hydrate`)

Generates a complete HTML page with:
- Server-rendered HTML content
- Inlined hydration script for client-side interactivity
- Proper HTML document structure

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLI Parser    │───▶│    Compiler     │───▶│     Output      │
│   (clap)        │    │     (SWC)       │    │   (HTML/JS)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │     Bundler     │
                    │  (Dependency    │
                    │   Resolution)   │
                    └─────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌─────────────────┐ ┌─────────────────┐
            │  SSR Renderer   │ │   Hydration     │
            │  (Boa Engine)   │ │   Generator     │
            └─────────────────┘ └─────────────────┘
```

## Dependencies

- **SWC**: Fast TypeScript/JavaScript compiler
- **Boa**: Pure Rust JavaScript engine
- **Clap**: Command-line argument parsing
- **Tokio**: Async runtime
- **Anyhow**: Error handling

## Limitations

- Limited React API support (basic createElement and Fragment)
- No support for React hooks in SSR mode
- Simplified module resolution (no full node_modules support)
- Basic CSS handling (className only)

## Development

```bash
# Run tests
cargo test

# Run with debug output
RUST_LOG=debug cargo run -- --entry examples/App.tsx --ssr --hydrate

# Build optimized release
cargo build --release
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.