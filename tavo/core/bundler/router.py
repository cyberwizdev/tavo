"""
App Router

Handles React App Router functionality with SSR and hydration.
"""

import logging
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional

from .compiler import SWCCompiler

logger = logging.getLogger(__name__)


class AppRouter:
    """Handles React App Router with SSR and client hydration"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.app_dir = project_root / "app"
        self.compiler = SWCCompiler(project_root)
    
    def build_component_tree(self, route: str) -> List[str]:
        """
        Build an ordered list of layout.tsx and page.tsx files for a given route.
        """
        segments = route.strip("/").split("/") if route != "/" else []
        files = []
        current_path = self.app_dir

        logger.debug(f"Building component tree for route: {route}")
        logger.debug(f"App directory: {current_path}")
        logger.debug(f"App directory exists: {current_path.exists()}")

        if not current_path.exists():
            logger.debug("App directory does not exist")
            return []

        # 1. Root layout
        root_layout = current_path / "layout.tsx"
        logger.debug(f"Checking root layout: {root_layout}")
        if root_layout.exists():
            files.append(str(root_layout))

        # 2. Nested layouts
        for segment in segments:
            current_path /= segment
            nested_layout = current_path / "layout.tsx"
            logger.debug(f"Checking nested layout: {nested_layout}")
            if nested_layout.exists():
                files.append(str(nested_layout))

        # 3. Page file
        page_file = current_path / "page.tsx"
        logger.debug(f"Checking page file: {page_file}")
        if page_file.exists():
            files.append(str(page_file))
        else:
            # Also try page.jsx
            page_file_jsx = current_path / "page.jsx"
            logger.debug(f"Checking page.jsx file: {page_file_jsx}")
            if page_file_jsx.exists():
                files.append(str(page_file_jsx))
            else:
                # No page found
                if not any(f.endswith(("page.tsx", "page.jsx")) for f in files):
                    logger.debug("No page files found")
                    return []

        logger.debug(f"Found component files: {files}")
        return files
    
    def render_with_node(self, compiled_js: str, num_layouts: int) -> str:
        """
        Use Node.js to render the React components to HTML
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mjs', delete=False, encoding='utf-8', dir=self.compiler.tavo_cache_dir) as f:
            # Write the compiled components and render logic
            render_script = f"""
import React from 'react';
import {{ renderToString }} from 'react-dom/server';

{compiled_js}

// Extract component exports (assuming they follow export default pattern)
const components = [];
const moduleExports = {{}};

// This is a simplified approach - in production you'd want proper module parsing
// For now, we'll assume the compiled JS has the components available

// Generate nested React tree
function generateReactTree() {{
    // This is a placeholder - you'll need to adapt based on your compiled output structure
    // The compiled JS should expose the components in a predictable way
    return React.createElement('div', null, 'Rendered content');
}}

try {{
    const html = renderToString(generateReactTree());
    console.log(html);
}} catch (error) {{
    console.error('Rendering error:', error);
    process.exit(1);
}}
"""
            f.write(render_script)
            temp_script_path = f.name

        try:
            import subprocess
            import os
            
            # Use absolute path to the temporary script but run from project root
            cmd = ["node", os.path.abspath(temp_script_path)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                shell=True,
                cwd=str(self.project_root),
                encoding='utf-8',
                errors='replace',
                timeout=10
            )
            
            if result.stdout:
                return result.stdout.strip()
            else:
                logger.error("Node.js script returned empty output")
                return "<div>Error: Empty render output</div>"
                
        except subprocess.CalledProcessError as e:
            error_message = f"Node rendering failed.\nStdout:\n{e.stdout}\nStderr:\n{e.stderr}"
            logger.error(error_message)
            return f"<div>Render Error: {e.stderr}</div>"
        except subprocess.TimeoutExpired:
            logger.error("Node.js rendering timed out")
            return "<div>Error: Rendering timeout</div>"
        finally:
            # Clean up temp file
            Path(temp_script_path).unlink(missing_ok=True)
    
    def generate_hydration_script(self, compiled_js: str, num_layouts: int) -> str:
        """
        Generate the client-side hydration script
        """
        return f"""
// Hydration script
import React from "react";
import {{ hydrateRoot }} from "react-dom/client";

{compiled_js}

// Generate nested React tree for hydration
function generateReactTree() {{
    // This should match the SSR structure
    return React.createElement('div', null, 'Hydrated content');
}}

// Hydrate the application
const container = document.getElementById('root');
if (container) {{
    hydrateRoot(container, generateReactTree());
}}
"""
    
    def render_route(self, route: str) -> Tuple[str, int]:
        """
        Complete rendering pipeline: find files, compile, render, and return HTML
        """
        logger.debug(f"Starting render_route for: {route}")
        component_files = self.build_component_tree(route)
        logger.debug(f"Component files found: {component_files}")

        if not component_files:
            logger.debug("No component files found, returning 404")
            return "404 Not Found - No page.tsx found for this route", 404
            
        if not component_files[-1].endswith(("page.tsx", "page.jsx")):
            logger.debug("Last file is not a page file, returning 404")
            return "404 Not Found - No page.tsx found for this route", 404

        num_layouts = len(component_files) - 1
        logger.debug(f"Number of layouts: {num_layouts}")
        
        try:
            # Compile components
            logger.debug("Starting compilation...")
            compiled_js = self.compiler.compile_for_ssr(component_files)
            logger.debug("Compilation successful")
            
            # Server-side render
            logger.debug("Starting server-side render...")
            rendered_html = self.render_with_node(compiled_js, num_layouts)
            logger.debug(f"Server-side render successful")
            
            # Generate hydration script
            logger.debug("Generating hydration script...")
            hydration_js = self.compiler.compile_for_hydration(component_files)
            hydration_script = self.generate_hydration_script(hydration_js, num_layouts)
            
            # Combine into final HTML
            html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>Tavo App</title>
</head>
<body>
    <div id="root">{rendered_html}</div>
    <script type="module">
        {hydration_script}
    </script>
</body>
</html>'''
            
            logger.debug("Route rendering completed successfully")
            return html, 200
            
        except Exception as e:
            logger.error(f"Error rendering route '{route}': {str(e)}", exc_info=True)
            return f"500 Internal Server Error: {str(e)}", 500
