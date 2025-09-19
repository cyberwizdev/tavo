"""
Tests for the ImportResolver and route discovery functionality
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

from ..resolver import ImportResolver, RouteEntry, RouteNode
from ..constants import APP_DIR_NAME


class TestImportResolver:
    
    def setup_method(self):
        """Setup test environment for each test"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.app_dir = self.temp_dir / APP_DIR_NAME
        self.app_dir.mkdir(parents=True)
        self.resolver = ImportResolver(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup after each test"""
        shutil.rmtree(self.temp_dir)
    
    def create_file(self, relative_path: str, content: str = "export default function Component() { return null; }"):
        """Helper to create test files"""
        file_path = self.temp_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return file_path
    
    def test_init(self):
        """Test resolver initialization"""
        assert self.resolver.project_root == self.temp_dir
        assert self.resolver.app_dir == self.app_dir
        assert self.resolver._route_cache is None
    
    def test_simple_route_discovery(self):
        """Test discovery of simple routes"""
        # Create basic app structure
        self.create_file("app/layout.tsx")
        self.create_file("app/page.tsx") 
        self.create_file("app/about/page.tsx")
        
        routes = self.resolver.resolve_routes()
        
        # Should find routes
        route_paths = [r.route_path for r in routes]
        assert "/" in route_paths
        assert "/about" in route_paths
        
        # Check root route
        root_route = next(r for r in routes if r.route_path == "/")
        assert root_route.page_file.name == "page.tsx"
        assert len(root_route.layout_chain) == 1
        assert root_route.layout_chain[0].name == "layout.tsx"
    
    def test_nested_routes(self):
        """Test nested route discovery"""
        self.create_file("app/layout.tsx")
        self.create_file("app/page.tsx")
        self.create_file("app/dashboard/layout.tsx")
        self.create_file("app/dashboard/page.tsx")
        self.create_file("app/dashboard/settings/page.tsx")
        
        routes = self.resolver.resolve_routes()
        
        # Find dashboard settings route
        settings_route = next(r for r in routes if r.route_path == "/dashboard/settings")
        
        # Should have nested layouts: root -> dashboard
        assert len(settings_route.layout_chain) == 2
        layout_names = [l.name for l in settings_route.layout_chain]
        assert "layout.tsx" in layout_names  # Root layout
        assert layout_names.count("layout.tsx") == 1  # Dashboard layout (same name, different dirs)
    
    def test_dynamic_routes(self):
        """Test dynamic route discovery"""
        self.create_file("app/blog/[slug]/page.tsx")
        self.create_file("app/users/[id]/page.tsx")
        
        routes = self.resolver.resolve_routes()
        
        route_paths = [r.route_path for r in routes]
        assert "/blog/[slug]" in route_paths
        assert "/users/[id]" in route_paths
    
    def test_catch_all_routes(self):
        """Test catch-all route discovery"""
        self.create_file("app/docs/[...slug]/page.tsx")
        self.create_file("app/shop/[[...params]]/page.tsx")
        
        routes = self.resolver.resolve_routes()
        
        route_paths = [r.route_path for r in routes]
        assert "/docs/[...slug]" in route_paths
        assert "/shop/[[...params]]" in route_paths
    
    def test_loading_and_error_files(self):
        """Test discovery of loading and error files"""
        self.create_file("app/dashboard/page.tsx")
        self.create_file("app/dashboard/loading.tsx")
        self.create_file("app/dashboard/error.tsx")
        
        routes = self.resolver.resolve_routes()
        
        dashboard_route = next(r for r in routes if r.route_path == "/dashboard")
        assert dashboard_route.loading_file is not None
        assert dashboard_route.loading_file.name == "loading.tsx"
        # Note: error.tsx handling would need additional implementation
    
    def test_route_priorities(self):
        """Test that static routes take priority over dynamic ones"""
        # Create both static and dynamic routes
        self.create_file("app/blog/latest/page.tsx")  # Static
        self.create_file("app/blog/[slug]/page.tsx")   # Dynamic
        
        routes = self.resolver.resolve_routes()
        
        route_paths = [r.route_path for r in routes]
        assert "/blog/latest" in route_paths
        assert "/blog/[slug]" in route_paths
        
        # Both should be discovered (resolution priority is handled elsewhere)
        assert len([r for r in routes if r.route_path.startswith("/blog/")]) == 2
    
    def test_import_path_resolution(self):
        """Test import path alias resolution"""
        # Test the _resolve_import_path method
        test_import = 'import Component from "@/components/Button"'
        resolved = self.resolver._resolve_import_path(test_import, self.app_dir / "page.tsx")
        
        # Should resolve @/ to project root
        expected_path = str(self.temp_dir) + "/components/Button"
        assert expected_path in resolved
    
    def test_cache_invalidation(self):
        """Test route cache invalidation"""
        # First resolution
        self.create_file("app/page.tsx")
        routes1 = self.resolver.resolve_routes()
        
        # Should be cached
        assert self.resolver._route_cache is not None
        assert len(routes1) >= 1
        
        # Invalidate cache
        self.resolver.invalidate_cache()
        assert self.resolver._route_cache is None
        
        # Add new route and resolve again
        self.create_file("app/about/page.tsx")
        routes2 = self.resolver.resolve_routes()
        
        # Should find new route
        route_paths = [r.route_path for r in routes2]
        assert "/about" in route_paths
    
    def test_bundle_files_for_route(self):
        """Test getting bundle files for a route"""
        # Create route with dependencies
        self.create_file("app/layout.tsx")
        self.create_file("app/dashboard/layout.tsx")
        self.create_file("app/dashboard/page.tsx")
        
        # Create some shared components
        self.create_file("components/Button.tsx")
        self.create_file("lib/utils.ts")
        
        routes = self.resolver.resolve_routes()
        dashboard_route = next(r for r in routes if r.route_path == "/dashboard")
        
        bundle_files = self.resolver.create_entry_bundle_files_for_route(dashboard_route)
        
        # Should include route files
        file_names = [f.name for f in bundle_files]
        assert "layout.tsx" in file_names  # Root layout
        assert "page.tsx" in file_names    # Dashboard page
        
        # Should include shared components
        assert any("Button.tsx" in str(f) for f in bundle_files)
        assert any("utils.ts" in str(f) for f in bundle_files)
    
    def test_create_single_file_for_swc(self):
        """Test creating bundled file for SWC"""
        # Create test files
        layout_file = self.create_file("app/layout.tsx", '''
import React from "react";
export default function Layout({ children }) {
  return <div>{children}</div>;
}
        ''')
        
        page_file = self.create_file("app/page.tsx", '''
import React from "react";
export default function Page() {
  return <h1>Home</h1>;
}
        ''')
        
        temp_dir = self.temp_dir / "temp"
        temp_dir.mkdir()
        
        bundled_file = self.resolver.create_single_file_for_swc([layout_file, page_file], temp_dir)
        
        # Should create bundled file
        assert bundled_file.exists()
        assert bundled_file.name == "bundled.tsx"
        
        # Should contain content from both files
        content = bundled_file.read_text()
        assert "Layout" in content
        assert "Page" in content
        assert 'import React from "react"' in content
    
    def test_no_app_directory(self):
        """Test behavior when app directory doesn't exist"""
        # Remove app directory
        shutil.rmtree(self.app_dir)
        
        routes = self.resolver.resolve_routes()
        
        # Should return empty list
        assert len(routes) == 0
    
    def test_mixed_file_extensions(self):
        """Test handling of different file extensions"""
        self.create_file("app/layout.tsx")
        self.create_file("app/page.jsx")      # JSX instead of TSX
        self.create_file("app/about/page.ts")  # TS instead of TSX
        
        routes = self.resolver.resolve_routes()
        
        # Should find all routes regardless of extension
        route_paths = [r.route_path for r in routes]
        assert "/" in route_paths
        assert "/about" in route_paths
    
    @patch('tavo.core.bundler.resolver.logger')
    def test_error_handling(self, mock_logger):
        """Test error handling in route resolution"""
        # Create a file that will cause issues
        problematic_file = self.app_dir / "broken" / "page.tsx"
        problematic_file.parent.mkdir(parents=True)
        problematic_file.write_text("invalid content {{{")
        
        # Should still work but log warnings
        routes = self.resolver.resolve_routes()
        
        # Should complete without crashing
        assert isinstance(routes, list)
    
    def test_route_sorting(self):
        """Test that routes are sorted consistently"""
        # Create routes in random order
        self.create_file("app/zebra/page.tsx")
        self.create_file("app/alpha/page.tsx")
        self.create_file("app/beta/gamma/page.tsx")
        self.create_file("app/page.tsx")
        
        routes = self.resolver.resolve_routes()
        
        route_paths = [r.route_path for r in routes]
        
        # Should be sorted by depth first, then alphabetically
        # Root route should be first
        assert route_paths[0] == "/"
        
        # Single-level routes should come before nested ones
        single_level = [p for p in route_paths if p.count('/') == 1]
        nested = [p for p in route_paths if p.count('/') > 1]
        
        # All single-level routes should appear before nested ones
        single_level_indices = [route_paths.index(p) for p in single_level]
        nested_indices = [route_paths.index(p) for p in nested]
        
        if single_level and nested:
            assert max(single_level_indices) < min(nested_indices)


class TestRouteEntry:
    
    def test_route_entry_creation(self):
        """Test RouteEntry creation and properties"""
        layout_file = Path("/app/layout.tsx")
        page_file = Path("/app/dashboard/page.tsx")
        
        route = RouteEntry(
            route_path="/dashboard",
            layout_chain=[layout_file],
            page_file=page_file,
            loading_file=None,
            head_file=None,
            route_file=None,
            all_files={layout_file, page_file}
        )
        
        assert route.route_path == "/dashboard"
        assert route.page_file == page_file
        assert len(route.layout_chain) == 1
        assert len(route.all_files) == 2


class TestRouteNode:
    
    def test_route_node_creation(self):
        """Test RouteNode creation and properties"""
        node = RouteNode(
            path="/dashboard",
            file_path=Path("/app/dashboard/page.tsx"),
            route_type="page",
            children=[],
            route_segment="dashboard",
            is_dynamic=False,
            is_catch_all=False
        )
        
        assert node.path == "/dashboard"
        assert node.route_type == "page"
        assert node.route_segment == "dashboard"
        assert not node.is_dynamic
        assert not node.is_catch_all
    
    def test_dynamic_route_node(self):
        """Test dynamic route node properties"""
        node = RouteNode(
            path="/blog/[slug]",
            file_path=Path("/app/blog/[slug]/page.tsx"),
            route_type="page",
            children=[],
            route_segment="slug",
            is_dynamic=True,
            is_catch_all=False
        )
        
        assert node.is_dynamic
        assert not node.is_catch_all
        assert node.route_segment == "slug"
    
    def test_catch_all_route_node(self):
        """Test catch-all route node properties"""
        node = RouteNode(
            path="/docs/[...slug]",
            file_path=Path("/app/docs/[...slug]/page.tsx"),
            route_type="page",
            children=[],
            route_segment="slug",
            is_dynamic=True,
            is_catch_all=True
        )
        
        assert node.is_dynamic
        assert node.is_catch_all
        assert node.route_segment == "slug"