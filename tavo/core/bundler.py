import subprocess
import json
import tempfile
import shutil
import logging
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class AppRouter:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        # The render.js script will be in the `tavo` package, one level above `core`
        self.render_js_path = Path(__file__).resolve().parent.parent / "render.js"
        self.swc_binary = self._find_swc_binary()

    def _find_swc_binary(self) -> Optional[str]:
        """Find SWC binary in common locations or PATH"""
        possible_paths = [
            "swc",  # In PATH
            "./node_modules/.bin/swc",  # Local node_modules
            str(self.project_root / "node_modules" / ".bin" / "swc"),  # Project node_modules
        ]
        
        for path in possible_paths:
            if shutil.which(path):
                return path
        
        # Try to find platform-specific binary names
        platform_binaries = ["swc-linux", "swc-darwin", "swc-win32.exe"]
        for binary in platform_binaries:
            if shutil.which(binary):
                return binary
        
        return None

    def resolve_import(self, content: str) -> str:
        """
        Resolve @/ imports in the file content to relative paths
        """
        # Simple regex replacement for @/ imports
        import re
        
        def replace_import(match):
            import_path = match.group(1)
            if import_path.startswith("@/"):
                # Convert @/components/Button to ../components/Button (adjust based on depth)
                relative_path = import_path.replace("@/", "../")
                return f'"{relative_path}"'
            return f'"{import_path}"'
        
        # Replace both single and double quoted imports
        content = re.sub(r'from\s+["\']([^"\']+)["\']', lambda m: f'from {replace_import(m)}', content)
        content = re.sub(r'import\s+["\']([^"\']+)["\']', lambda m: f'import {replace_import(m)}', content)
        
        return content

    def build_component_tree(self, route: str) -> List[str]:
        """
        Build an ordered list of layout.tsx and page.tsx files for a given route.
        """
        segments = route.strip("/").split("/") if route != "/" else []
        files = []
        current_path = self.project_root / "app"

        # 1. Root layout
        root_layout = current_path / "layout.tsx"
        if root_layout.exists():
            files.append(str(root_layout))

        # 2. Nested layouts
        for segment in segments:
            current_path /= segment
            nested_layout = current_path / "layout.tsx"
            if nested_layout.exists():
                files.append(str(nested_layout))

        # 3. Page file
        page_file = current_path / "page.tsx"
        if page_file.exists():
            files.append(str(page_file))
        else:
            # No page found
            if not any(f.endswith("page.tsx") for f in files):
                return []

        return files

    def compile_with_swc(self, files: List[str]) -> str:
        """
        Compile TSX files using SWC prebuilt binary
        """
        if not self.swc_binary:
            raise RuntimeError("SWC binary not found. Please install SWC binary or add it to PATH")

        compiled_modules = []
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            for i, file_path in enumerate(files):
                file_path_obj = Path(file_path)
                
                # Read and resolve imports
                content = file_path_obj.read_text()
                resolved_content = self.resolve_import(content)
                
                # Write to temp file
                temp_file = temp_path / f"component_{i}.tsx"
                temp_file.write_text(resolved_content)
                
                # Compile with SWC
                output_file = temp_path / f"component_{i}.js"
                
                swc_config = {
                    "jsc": {
                        "parser": {
                            "syntax": "typescript",
                            "tsx": True
                        },
                        "transform": {
                            "react": {
                                "runtime": "automatic"
                            }
                        },
                        "target": "es2022"
                    },
                    "module": {
                        "type": "es6"
                    }
                }
                
                config_file = temp_path / "swc_config.json"
                config_file.write_text(json.dumps(swc_config))
                
                cmd = [
                    self.swc_binary,
                    str(temp_file),
                    "-o", str(output_file),
                    "--config-file", str(config_file)
                ]
                
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        check=True,
                        cwd=self.project_root
                    )
                    
                    # Read compiled output
                    if output_file.exists():
                        compiled_content = output_file.read_text()
                        # Export with unique names
                        export_name = f"Layout{i}" if i < len(files) - 1 else "Page"
                        compiled_modules.append(f"const {export_name} = {compiled_content.replace('export default', '').strip()};")
                    
                except subprocess.CalledProcessError as e:
                    error_message = f"SWC compilation failed for {file_path}.\nStdout:\n{e.stdout}\nStderr:\n{e.stderr}"
                    raise RuntimeError(error_message) from e
        
        return "\n".join(compiled_modules)

    def render_with_node(self, compiled_js: str, num_layouts: int) -> str:
        """
        Use Node.js to render the React components to HTML
        """
        if not self.render_js_path.exists():
            raise FileNotFoundError(f"Render script not found at {self.render_js_path}")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            # Write the compiled components and render logic
            render_script = f"""
import React from 'react';
import {{ renderToString }} from 'react-dom/server';

{compiled_js}

// Generate nested React tree
function generateReactTree() {{
    let tree = React.createElement(Page);
    for (let i = {num_layouts - 1}; i >= 0; i--) {{
        const Layout = eval(`Layout${{i}}`);
        tree = React.createElement(Layout, null, tree);
    }}
    return tree;
}}

const html = renderToString(generateReactTree());
console.log(html);
"""
            f.write(render_script)
            temp_script_path = f.name

        try:
            cmd = ["node", temp_script_path]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=self.project_root
            )
            return result.stdout.strip()
            
        except subprocess.CalledProcessError as e:
            error_message = f"Node rendering failed.\nStdout:\n{e.stdout}\nStderr:\n{e.stderr}"
            raise RuntimeError(error_message) from e
        finally:
            # Clean up temp file
            Path(temp_script_path).unlink(missing_ok=True)

    def generate_hydration_script(self, compiled_js: str, num_layouts: int) -> str:
        """
        Generate the client-side hydration script
        """
        return f"""
import React from "react";
import ReactDOM from "react-dom/client";

{compiled_js}

// Generate nested React tree for hydration
function generateReactTree() {{
    let tree = React.createElement(Page);
    for (let i = {num_layouts - 1}; i >= 0; i--) {{
        const Layout = eval(`Layout${{i}}`);
        tree = React.createElement(Layout, null, tree);
    }}
    return tree;
}}

ReactDOM.hydrateRoot(
    document.getElementById('root'),
    generateReactTree()
);
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
            
        if not component_files[-1].endswith("page.tsx"):
            logger.debug("Last file is not page.tsx, returning 404")
            return "404 Not Found - No page.tsx found for this route", 404

        num_layouts = len(component_files) - 1
        logger.debug(f"Number of layouts: {num_layouts}")
        
        try:
            # Compile components
            logger.debug("Starting compilation...")
            compiled_js = self.compile_with_swc(component_files)
            logger.debug("Compilation successful")
            
            # Server-side render
            logger.debug("Starting server-side render...")
            rendered_html = self.render_with_node(compiled_js, num_layouts)
            logger.debug(f"Server-side render successful: {rendered_html[:100]}...")
            
            # Generate hydration script
            logger.debug("Generating hydration script...")
            hydration_script = self.generate_hydration_script(compiled_js, num_layouts)
            
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
            # In development, you might want to show the error
            # In production, return a 500 error page
            return f"500 Internal Server Error: {str(e)}", 500