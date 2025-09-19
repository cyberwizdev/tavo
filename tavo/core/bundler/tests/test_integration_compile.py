"""
Integration tests for the complete compilation process
"""

import pytest
from pathlib import Path
import tempfile
import shutil
import json

from ..compiler import SWCCompiler
from ..resolver import ImportResolver
from ..layouts import LayoutComposer
from unittest.mock import patch, MagicMock


class TestCompilationIntegration:
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.app_dir = self.temp_dir / "app"
        self.app_dir.mkdir(parents=True)
        
        # Create components directory
        self.components_dir = self.temp_dir / "components"
        self.components_dir.mkdir()
        
        self.compiler = SWCCompiler(self.temp_dir)
        self.resolver = ImportResolver(self.temp_dir)
        self.composer = LayoutComposer()
    
    def teardown_method(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir)
    
    def create_file(self, relative_path: str, content: str):
        """Helper to create test files"""
        file_path = self.temp_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return file_path
    
    @pytest.mark.skipif_no_swc
    def test_simple_page_compilation(self):
        """Test compilation of a simple page"""
        # Create a simple page
        page_content = '''
import React from 'react';

export default function HomePage() {
  return (
    <div>
      <h1>Welcome to Tavo</h1>
      <p>This is the home page.</p>
    </div>
  );
}
        '''
        
        page_file = self.create_file("app/page.tsx", page_content)
        
        # Mock SWC compilation since we can't guarantee SWC is installed
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            expected_js = '''
import React from "react";
export default function HomePage() {
    return React.createElement("div", null,
        React.createElement("h1", null, "Welcome to Tavo"),
        React.createElement("p", null, "This is the home page.")
    );
}
            '''.strip()
            
            mock_compile.return_value = (expected_js, page_content)
            
            # Compile
            result = self.compiler.compile_files([page_file], "hydration")
            
            # Verify result
            assert result.compiled_js
            assert result.source_files == [page_file]
            assert not result.cache_hit  # First compilation
            assert result.compilation_time >= 0
            assert result.output_size > 0
    
    def test_layout_page_composition_and_compilation(self):
        """Test compilation of page with layout"""
        # Create layout
        layout_content = '''
import React from 'react';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        <nav>Navigation</nav>
        {children}
        <footer>Footer</footer>
      </body>
    </html>
  );
}
        '''
        
        # Create page
        page_content = '''
import React from 'react';

export default function HomePage() {
  return (
    <div>
      <h1>Home Page</h1>
    </div>
  );
}
        '''
        
        layout_file = self.create_file("app/layout.tsx", layout_content)
        page_file = self.create_file("app/page.tsx", page_content)
        
        # Test layout composition
        composed = self.composer.compose_layouts([layout_file], page_file)
        
        # Should contain both layout and page content
        assert "RootLayout" in composed or "Layout" in composed
        assert "HomePage" in composed or "Page" in composed
        assert "Navigation" in composed
        assert "Home Page" in composed
        
        # Test compilation with mocked SWC
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.return_value = ("compiled_output", composed)
            
            result = self.compiler.compile_files([layout_file, page_file], "ssr")
            
            assert result.compiled_js == "compiled_output"
            assert len(result.source_files) == 2
    
    def test_nested_layouts_compilation(self):
        """Test compilation with nested layouts"""
        # Root layout
        root_layout = '''
import React from 'react';
export default function RootLayout({ children }) {
  return <html><body>{children}</body></html>;
}
        '''
        
        # Dashboard layout
        dashboard_layout = '''
import React from 'react';
export default function DashboardLayout({ children }) {
  return <div><nav>Dashboard Nav</nav>{children}</div>;
}
        '''
        
        # Dashboard page
        dashboard_page = '''
import React from 'react';
export default function DashboardPage() {
  return <h1>Dashboard</h1>;
}
        '''
        
        root_file = self.create_file("app/layout.tsx", root_layout)
        dashboard_layout_file = self.create_file("app/dashboard/layout.tsx", dashboard_layout)
        dashboard_page_file = self.create_file("app/dashboard/page.tsx", dashboard_page)
        
        # Test composition
        composed = self.composer.compose_layouts(
            [root_file, dashboard_layout_file], 
            dashboard_page_file
        )
        
        # Should have nested structure
        assert "RootLayout" in composed or "Layout" in composed
        assert "DashboardLayout" in composed
        assert "DashboardPage" in composed or "Page" in composed
        
        # Test compilation
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.return_value = ("nested_output", composed)
            
            result = self.compiler.compile_files([root_file, dashboard_layout_file, dashboard_page_file], "ssr")
            
            assert result.compiled_js == "nested_output"
            assert len(result.source_files) == 3
    
    def test_component_imports_resolution(self):
        """Test compilation with component imports"""
        # Create shared component
        button_component = '''
import React from 'react';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
}

export default function Button({ children, onClick }: ButtonProps) {
  return <button onClick={onClick}>{children}</button>;
}
        '''
        
        # Create page that uses component
        page_with_imports = '''
import React from 'react';
import Button from '@/components/Button';

export default function HomePage() {
  return (
    <div>
      <h1>Home</h1>
      <Button onClick={() => alert('clicked')}>
        Click me
      </Button>
    </div>
  );
}
        '''
        
        button_file = self.create_file("components/Button.tsx", button_component)
        page_file = self.create_file("app/page.tsx", page_with_imports)
        
        # Test bundling (resolver should include shared components)
        routes = self.resolver.resolve_routes()
        home_route = next(r for r in routes if r.route_path == "/")
        bundle_files = self.resolver.create_entry_bundle_files_for_route(home_route)
        
        # Should include both page and button component
        file_names = [f.name for f in bundle_files]
        assert "page.tsx" in file_names
        assert any("Button.tsx" in str(f) for f in bundle_files)
        
        # Test compilation with bundled files
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.return_value = ("bundled_output", "bundled_tsx")
            
            result = self.compiler.compile_files(bundle_files, "hydration")
            
            assert result.compiled_js == "bundled_output"
    
    def test_dynamic_route_compilation(self):
        """Test compilation of dynamic routes"""
        # Create dynamic route
        dynamic_page = '''
import React from 'react';

interface BlogPostProps {
  params: { slug: string };
}

export default function BlogPost({ params }: BlogPostProps) {
  return (
    <article>
      <h1>Blog Post: {params.slug}</h1>
      <p>This is a dynamic blog post.</p>
    </article>
  );
}
        '''
        
        dynamic_file = self.create_file("app/blog/[slug]/page.tsx", dynamic_page)
        
        # Test route resolution
        routes = self.resolver.resolve_routes()
        blog_route = next(r for r in routes if "[slug]" in r.route_path)
        
        assert blog_route.route_path == "/blog/[slug]"
        assert blog_route.page_file == dynamic_file
        
        # Test compilation
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.return_value = ("dynamic_output", dynamic_page)
            
            result = self.compiler.compile_files([dynamic_file], "ssr")
            
            assert result.compiled_js == "dynamic_output"
    
    def test_ssr_vs_hydration_compilation(self):
        """Test different compilation modes"""
        page_content = '''
import React, { useEffect, useState } from 'react';

export default function InteractivePage() {
  const [count, setCount] = useState(0);
  
  useEffect(() => {
    console.log('Component mounted');
    document.title = `Count: ${count}`;
  }, [count]);
  
  return (
    <div>
      <h1>Interactive Page</h1>
      <p>Count: {count}</p>
      <button onClick={() => setCount(count + 1)}>
        Increment
      </button>
    </div>
  );
}
        '''
        
        page_file = self.create_file("app/interactive/page.tsx", page_content)
        
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            # SSR compilation should optimize for server
            mock_compile.return_value = ("ssr_optimized", page_content)
            ssr_result = self.compiler.compile_for_ssr([page_file])
            
            # Hydration compilation should optimize for client  
            mock_compile.return_value = ("hydration_optimized", page_content)
            hydration_result = self.compiler.compile_for_hydration([page_file])
            
            # Results should be different due to optimizations
            # (In real implementation, SSR would strip client-only code)
            assert ssr_result.compiled_js != hydration_result.compiled_js
    
    def test_compilation_caching_integration(self):
        """Test end-to-end caching behavior"""
        page_content = '''
import React from 'react';
export default function CachedPage() {
  return <div>Cached content</div>;
}
        '''
        
        page_file = self.create_file("app/cached/page.tsx", page_content)
        
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.return_value = ("cached_output", page_content)
            
            # First compilation - cache miss
            result1 = self.compiler.compile_files([page_file], "ssr")
            assert not result1.cache_hit
            assert mock_compile.call_count == 1
            
            # Second compilation - cache hit
            result2 = self.compiler.compile_files([page_file], "ssr")
            assert result2.cache_hit
            assert mock_compile.call_count == 1  # No additional calls
            assert result2.compiled_js == result1.compiled_js
            
            # Modify file - should invalidate cache
            page_file.write_text(page_content + "\n// modified")
            
            result3 = self.compiler.compile_files([page_file], "ssr")
            assert not result3.cache_hit
            assert mock_compile.call_count == 2  # One more call
    
    def test_build_all_integration(self):
        """Test complete build process"""
        # Create full app structure
        self.create_file("app/layout.tsx", '''
import React from 'react';
export default function RootLayout({ children }) {
  return <html><body>{children}</body></html>;
}
        ''')
        
        self.create_file("app/page.tsx", '''
import React from 'react';
export default function HomePage() {
  return <h1>Home</h1>;
}
        ''')
        
        self.create_file("app/about/page.tsx", '''
import React from 'react';
export default function AboutPage() {
  return <h1>About</h1>;
}
        ''')
        
        self.create_file("app/blog/[slug]/page.tsx", '''
import React from 'react';
export default function BlogPost({ params }) {
  return <h1>Post: {params.slug}</h1>;
}
        ''')
        
        # Mock compilation
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.return_value = ("built_output", "bundled_tsx")
            
            # Build all
            result = self.compiler.build_all()
            
            # Should build all routes
            assert result['routes'] >= 3  # At least home, about, blog post
            assert result['success'] >= 3
            assert result['errors'] == 0
            assert result['total_client_size'] > 0
            assert result['total_server_size'] > 0
            
            # Should create output directories
            dist_dir = self.temp_dir / "dist"
            assert dist_dir.exists()
            assert (dist_dir / "client").exists()
            assert (dist_dir / "server").exists()
    
    def test_error_handling_integration(self):
        """Test error handling in integration scenarios"""
        # Create file with syntax error
        broken_content = '''
import React from 'react';
export default function BrokenPage() {
  return <div>Unclosed div;
}
        '''
        
        broken_file = self.create_file("app/broken/page.tsx", broken_content)
        
        # Mock SWC to simulate compilation error
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.side_effect = RuntimeError("SWC compilation failed: syntax error")
            
            # Should raise error
            with pytest.raises(RuntimeError, match="SWC compilation failed"):
                self.compiler.compile_files([broken_file], "ssr")
    
    def test_large_project_compilation(self):
        """Test compilation with many files"""
        # Create multiple routes and components
        for i in range(10):
            self.create_file(f"app/page{i}/page.tsx", f'''
import React from 'react';
export default function Page{i}() {{
  return <h1>Page {i}</h1>;
}}
            ''')
            
            self.create_file(f"components/Component{i}.tsx", f'''
import React from 'react';
export default function Component{i}() {{
  return <div>Component {i}</div>;
}}
            ''')
        
        # Get all routes
        routes = self.resolver.resolve_routes()
        
        # Should find all pages
        assert len(routes) >= 10
        
        # Test compilation of one route with many dependencies
        route = routes[0]
        bundle_files = self.resolver.create_entry_bundle_files_for_route(route)
        
        # Should include shared components
        assert len(bundle_files) > 1
        
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.return_value = ("large_output", "large_bundled")
            
            result = self.compiler.compile_files(bundle_files, "hydration")
            
            assert result.compiled_js == "large_output"
            assert len(result.source_files) == len(bundle_files)


# Test helper to skip tests if SWC is not available
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "skipif_no_swc: skip test if SWC is not available"
    )

def pytest_collection_modifyitems(config, items):
    """Skip integration tests if SWC is not available"""
    try:
        from ..installer import SWCInstaller
        installer = SWCInstaller()
        swc_available = installer.ensure_swc_available()
    except:
        swc_available = False
    
    if not swc_available:
        skip_swc = pytest.mark.skip(reason="SWC not available - install with 'npm install -g @swc/cli @swc/core'")
        for item in items:
            if "skipif_no_swc" in item.keywords:
                item.add_marker(skip_swc)