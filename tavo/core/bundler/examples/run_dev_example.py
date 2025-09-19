#!/usr/bin/env python3
"""
Example script showing how to use the Tavo bundler programmatically

This demonstrates the integration between the bundler and a CLI command.
Run this script to start a development server for the sample app.
"""

import sys
import logging
from pathlib import Path

# Add the parent directories to Python path for imports
current_dir = Path(__file__).parent
bundler_dir = current_dir.parent
core_dir = bundler_dir.parent
tavo_dir = core_dir.parent
sys.path.insert(0, str(tavo_dir))

from tavo.core.bundler import get_bundler
from tavo.core.bundler.utils import setup_logging


def main():
    """Main function to run the development server"""
    # Setup logging
    setup_logging(level=logging.INFO)
    
    print("Tavo Bundler Development Example")
    print("=" * 40)
    
    # Use the sample app directory as project root
    project_root = current_dir / "sample_app"
    
    if not project_root.exists():
        print(f"Error: Sample app directory not found at {project_root}")
        print("Make sure you're running this script from the examples directory.")
        sys.exit(1)
    
    print(f"Project root: {project_root}")
    
    # Get bundler instance
    try:
        bundler = get_bundler(project_root)
        print("✓ Bundler initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize bundler: {e}")
        sys.exit(1)
    
    # Display project statistics
    try:
        routes = bundler.resolver.resolve_routes()
        print(f"✓ Discovered {len(routes)} routes:")
        for route in routes:
            print(f"  - {route.route_path}")
            if route.layout_chain:
                layouts = " → ".join(l.name for l in route.layout_chain)
                print(f"    Layouts: {layouts}")
    except Exception as e:
        print(f"✗ Failed to resolve routes: {e}")
        sys.exit(1)
    
    # Check SWC availability
    if bundler.compiler.ensure_swc_available():
        print("✓ SWC is available for compilation")
    else:
        print("⚠ SWC is not available - install with: npm install -g @swc/cli @swc/core")
        print("  The development server will still run but compilation may fail")
    
    # Setup development server callbacks
    @bundler.dev_server.on_change
    def handle_file_changes(changed_files):
        """Handle file change events"""
        print(f"📝 Files changed: {[str(f) for f in changed_files]}")
        print("🔄 Rebuilding affected routes...")
    
    # Display cache statistics
    cache_stats = bundler.compiler.get_cache_stats()
    print(f"📊 Cache: {cache_stats['total_entries']} entries, {cache_stats['total_size_mb']} MB")
    
    print("\n🚀 Starting development server...")
    print("   Available routes:")
    for route in routes:
        print(f"   http://localhost:3000{route.route_path}")
    
    print("\n📍 Server will start on http://localhost:3000")
    print("   Press Ctrl+C to stop the server")
    print()
    
    # Start development server
    try:
        bundler.dev_server.start(port=3000, host="localhost")
    except KeyboardInterrupt:
        print("\n👋 Development server stopped")
    except Exception as e:
        print(f"✗ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()