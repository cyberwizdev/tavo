.PHONY: build test clean install example

# Build the project
build:
	cargo build --release

# Run tests
test:
	cargo test

# Clean build artifacts
clean:
	cargo clean
	rm -rf examples/dist/

# Install the binary to system PATH
install: build
	cargo install --path .

# Build and run example
example: build
	mkdir -p examples/dist
	./target/release/myssr --entry examples/App.tsx --ssr --hydrate --out examples/dist/index.html
	@echo "Example built! Open examples/dist/index.html in your browser"

# Development build
dev:
	cargo build

# Run example with development build
example-dev: dev
	mkdir -p examples/dist
	./target/debug/myssr --entry examples/App.tsx --ssr --hydrate --out examples/dist/index.html
	@echo "Example built with debug binary! Open examples/dist/index.html in your browser"

# Benchmark the compiler
bench:
	cargo bench

# Check code formatting
fmt:
	cargo fmt --check

# Run clippy lints
lint:
	cargo clippy -- -D warnings

# Full CI check
ci: fmt lint test build

# Help
help:
	@echo "Available targets:"
	@echo "  build      - Build release binary"
	@echo "  test       - Run tests"
	@echo "  clean      - Clean build artifacts"
	@echo "  install    - Install binary to system PATH"
	@echo "  example    - Build and run example"
	@echo "  dev        - Build debug binary"
	@echo "  example-dev- Run example with debug binary"
	@echo "  bench      - Run benchmarks"
	@echo "  fmt        - Check code formatting"
	@echo "  lint       - Run clippy lints"
	@echo "  ci         - Run full CI checks"
	@echo "  help       - Show this help"