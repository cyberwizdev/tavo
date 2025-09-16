"""
App Router

Handles React App Router functionality with SSR and hydration.
"""

import logging
import tempfile
import subprocess
import os
import re
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from .compiler import SWCCompiler

logger = logging.getLogger(__name__)


class ComponentExtractor:
    """Extracts React components from compiled JavaScript"""
    
    @staticmethod
    def extract_component_exports(compiled_js: str) -> List[Dict[str, Any]]:
        """Extract component information from compiled JavaScript"""
        components = []
        
        # Find function components
        function_pattern = r'export\s+default\s+function\s+(\w+)\s*\([^)]*\)\s*{'
        function_matches = re.finditer(function_pattern, compiled_js, re.MULTILINE)
        
        for match in function_matches:
            components.append({
                'type': 'function',
                'name': match.group(1),
                'export_type': 'default'
            })
        
        # Find arrow function components  
        arrow_pattern = r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*{'
        arrow_matches = re.finditer(arrow_pattern, compiled_js, re.MULTILINE)
        
        for match in arrow_matches:
            components.append({
                'type': 'arrow',
                'name': match.group(1), 
                'export_type': 'const'
            })
        
        return components
    
    @staticmethod
    def get_main_component_name(compiled_js: str) -> str:
        """Get the main component name from compiled code"""
        # Look for export default function Name
        default_match = re.search(r'export\s+default\s+function\s+(\w+)', compiled_js)
        if default_match:
            return default_match.group(1)
        
        # Look for export default ComponentName
        export_match = re.search(r'export\s+default\s+(\w+)', compiled_js)
        if export_match:
            return export_match.group(1)
        
        return 'Component'


class SSRRenderer:
    """Handles server-side rendering with Node.js"""
    
    def __init__(self, project_root: Path, cache_dir: Path):
        self.project_root = project_root
        self.cache_dir = cache_dir
        
    def create_render_script(self, compiled_js: str, component_name: Optional[str] = None) -> str:
        """Create Node.js rendering script"""
        if not component_name:
            component_name = ComponentExtractor.get_main_component_name(compiled_js)
        
        return f"""
import React from 'react';
import {{ renderToString }} from 'react-dom/server';

{compiled_js}

function renderApp() {{
    try {{
        const element = React.createElement({component_name}, null);
        return renderToString(element);
    }} catch (error) {{
        console.error('Component render error:', error.message);
        return `<div class="error">Component Error: ${{error.message}}</div>`;
    }}
}}

try {{
    const html = renderApp();
    process.stdout.write(html);
}} catch (error) {{
    console.error('SSR Error:', error.message);
    process.stdout.write(`<div class="error">SSR Error: ${{error.message}}</div>`);
    process.exit(1);
}}
"""
    
    def render(self, compiled_js: str) -> str:
        """Render components to HTML using Node.js"""
        render_script = self.create_render_script(compiled_js)
        
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.mjs', 
            delete=False,
            encoding='utf-8',
            dir=self.cache_dir
        ) as f:
            f.write(render_script)
            script_path = f.name
        
        try:
            result = subprocess.run(
                ['node', script_path],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                encoding='utf-8',
                timeout=15
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or 'Unknown Node.js error'
                logger.error(f"Node.js rendering failed: {error_msg}")
                return f'<div class="ssr-error">Render failed: {error_msg}</div>'
            
            return result.stdout or '<div class="empty-render">No output</div>'
            
        except subprocess.TimeoutExpired:
            logger.error("Node.js rendering timeout")
            return '<div class="ssr-error">Rendering timeout</div>'
        except Exception as e:
            logger.error(f"SSR execution error: {e}")
            return f'<div class="ssr-error">Execution error: {e}</div>'
        finally:
            try:
                os.unlink(script_path)
            except Exception:
                pass


class HydrationManager:
    """Manages client-side hydration"""
    
    @staticmethod
    def create_hydration_script(compiled_js: str, component_name: Optional[str] = None) -> str:
        """Generate client-side hydration script"""
        if not component_name:
            component_name = ComponentExtractor.get_main_component_name(compiled_js)
        
        return f"""
import React from 'react';
import {{ hydrateRoot, createRoot }} from 'react-dom/client';

{compiled_js}

function startHydration() {{
    const container = document.getElementById('root');
    if (!container) {{
        console.error('Root container not found');
        return;
    }}
    
    try {{
        const element = React.createElement({component_name}, null);
        
        if (container.innerHTML.trim()) {{
            // Hydrate existing SSR content
            hydrateRoot(container, element);
            console.log('App hydrated successfully');
        }} else {{
            // No SSR content, render fresh
            const root = createRoot(container);
            root.render(element);
            console.log('App rendered client-side');
        }}
    }} catch (error) {{
        console.error('Hydration error:', error);
        
        // Fallback rendering
        try {{
            const root = createRoot(container);
            root.render(React.createElement('div', {{ className: 'hydration-error' }}, 
                'Hydration failed: ' + error.message));
        }} catch (fallbackError) {{
            container.innerHTML = '<div class="fatal-error">Fatal hydration error</div>';
        }}
    }}
}}

if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', startHydration);
}} else {{
    startHydration();
}}
"""


class AppRouter:
    """Handles React App Router with SSR and client hydration"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.app_dir = project_root / "app"
        self.compiler = SWCCompiler(project_root)
        self.ssr_renderer = SSRRenderer(project_root, self.compiler.tavo_cache_dir)
        
        # Ensure app directory exists
        if not self.app_dir.exists():
            logger.warning(f"App directory does not exist: {self.app_dir}")
    
    def find_layout_files(self, route_segments: List[str]) -> List[str]:
        """Find all layout files for a route"""
        layouts = []
        current_path = self.app_dir
        
        # Root layout
        root_layout = current_path / "layout.tsx"
        if root_layout.exists():
            layouts.append(str(root_layout))
        
        # Nested layouts
        for segment in route_segments:
            current_path = current_path / segment
            layout_file = current_path / "layout.tsx"
            if layout_file.exists():
                layouts.append(str(layout_file))
        
        return layouts
    
    def find_page_file(self, route_segments: List[str]) -> Optional[str]:
        """Find the page file for a route"""
        current_path = self.app_dir
        
        for segment in route_segments:
            current_path = current_path / segment
        
        # Try different extensions
        for ext in ['.tsx', '.jsx']:
            page_file = current_path / f"page{ext}"
            if page_file.exists():
                return str(page_file)
        
        return None
    
    def build_component_tree(self, route: str) -> List[str]:
        """Build complete component tree for a route"""
        route = route.strip("/")
        segments = route.split("/") if route else []
        
        component_files = []
        
        # Add layouts
        layouts = self.find_layout_files(segments)
        component_files.extend(layouts)
        
        # Add page
        page_file = self.find_page_file(segments)
        if page_file:
            component_files.append(page_file)
        
        logger.debug(f"Route '{route}' components: {component_files}")
        return component_files
    
    def create_html_document(self, rendered_content: str, hydration_script: str, 
                           title: str = "Tavo App") -> str:
        """Create complete HTML document"""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        #root {{
            min-height: 100vh;
        }}
        .error, .ssr-error, .hydration-error {{
            background: #fee;
            border: 1px solid #fcc;
            padding: 1rem;
            margin: 1rem;
            border-radius: 4px;
            color: #c33;
        }}
        .loading {{
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 50vh;
            color: #666;
        }}
    </style>
</head>
<body>
    <div id="root">{rendered_content}</div>
    <script type="module">{hydration_script}</script>
</body>
</html>'''
    
    def create_error_page(self, error_message: str, status_code: int, route: str) -> str:
        """Create error page HTML"""
        error_content = f'''
        <div class="error-page">
            <h1>{status_code} Error</h1>
            <p>{error_message}</p>
            <p><strong>Route:</strong> {route}</p>
            <p><a href="/">Return Home</a></p>
        </div>
        '''
        
        error_styles = '''
        .error-page {
            max-width: 600px;
            margin: 2rem auto;
            padding: 2rem;
            text-align: center;
            background: #f9f9f9;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .error-page h1 {
            color: #d32f2f;
            margin-bottom: 1rem;
        }
        .error-page p {
            margin-bottom: 1rem;
        }
        .error-page a {
            color: #1976d2;
            text-decoration: none;
            padding: 0.5rem 1rem;
            background: #e3f2fd;
            border-radius: 4px;
            display: inline-block;
        }
        '''
        
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <title>{status_code} Error - Tavo App</title>
    <style>
        body {{ font-family: system-ui, sans-serif; margin: 0; padding: 0; }}
        {error_styles}
    </style>
</head>
<body>{error_content}</body>
</html>'''
    
    def render_route(self, route: str) -> Tuple[str, int]:
        """Render a route with full SSR and hydration"""
        try:
            logger.debug(f"Rendering route: {route}")
            
            # Build component tree
            component_files = self.build_component_tree(route)
            
            if not component_files:
                logger.debug("No components found for route")
                return self.create_error_page(
                    "Page not found", 404, route
                ), 404
            
            # Check if we have a page component
            has_page = any('page.' in Path(f).name for f in component_files)
            if not has_page:
                logger.debug("No page component found")
                return self.create_error_page(
                    "No page component found", 404, route
                ), 404
            
            # Compile for SSR
            logger.debug("Compiling for SSR...")
            ssr_js = self.compiler.compile_for_ssr(component_files)
            
            # Server-side render
            logger.debug("Server-side rendering...")
            rendered_html = self.ssr_renderer.render(ssr_js)
            
            # Compile for hydration
            logger.debug("Compiling for hydration...")
            hydration_js = self.compiler.compile_for_hydration(component_files)
            
            # Create hydration script
            hydration_script = HydrationManager.create_hydration_script(hydration_js)
            
            # Create complete HTML document
            html = self.create_html_document(rendered_html, hydration_script)
            
            logger.debug("Route rendered successfully")
            return html, 200
            
        except Exception as e:
            logger.error(f"Route rendering failed: {e}", exc_info=True)
            return self.create_error_page(
                f"Internal server error: {str(e)}", 500, route
            ), 500
    
    def get_route_info(self, route: str) -> Dict[str, Any]:
        """Get information about a route"""
        component_files = self.build_component_tree(route)
        
        return {
            'route': route,
            'component_files': component_files,
            'layout_count': len([f for f in component_files if 'layout.' in Path(f).name]),
            'has_page': any('page.' in Path(f).name for f in component_files),
            'exists': len(component_files) > 0
        }
    
    def warm_up_route(self, route: str) -> bool:
        """Pre-compile a route for faster serving"""
        try:
            component_files = self.build_component_tree(route)
            if not component_files:
                return False
            
            # Pre-compile both SSR and hydration versions
            self.compiler.compile_for_ssr(component_files)
            self.compiler.compile_for_hydration(component_files)
            
            logger.debug(f"Route {route} warmed up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to warm up route {route}: {e}")
            return False