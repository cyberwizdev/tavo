import subprocess
import json
import tempfile
import shutil
import logging
import os
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
            "npx @swc/cli",  # Using npx
            "./node_modules/.bin/swc",  # Local node_modules
            str(self.project_root / "node_modules" / ".bin" / "swc"),  # Project node_modules
            str(self.project_root / "node_modules" / ".bin" / "swc.cmd"),  # Windows cmd
        ]
        
        for path in possible_paths:
            if path.startswith("npx"):
                # Test npx availability
                try:
                    result = subprocess.run(
                        ["npx", "--version"], 
                        capture_output=True, 
                        text=True, 
                        shell=True,
                        cwd=self.project_root
                    )
                    if result.returncode == 0:
                        return path
                except:
                    continue
            elif shutil.which(path):
                return path
        
        # Try to find platform-specific binary names
        platform_binaries = ["swc-linux", "swc-darwin", "swc-win32.exe", "swc.exe"]
        for binary in platform_binaries:
            if shutil.which(binary):
                return binary
        
        return None

    def resolve_import(self, content: str, current_file_path: str) -> str:
        """
        Resolve relative imports in the file content
        """
        import re
        
        def replace_import(match):
            import_path = match.group(1)
            
            # Handle relative imports like './components/Hello'
            if import_path.startswith('./'):
                # Calculate relative path from current file
                current_dir = Path(current_file_path).parent
                target_path = current_dir / import_path[2:]  # Remove './'
                
                # Convert to relative path from project root
                try:
                    relative_to_root = target_path.relative_to(self.project_root)
                    return f'"./{relative_to_root}"'
                except ValueError:
                    # If can't make relative, keep original
                    return f'"{import_path}"'
            
            # Handle @/ imports (alias for project root)
            elif import_path.startswith("@/"):
                relative_path = import_path.replace("@/", "./")
                return f'"{relative_path}"'
            
            # Keep other imports as-is
            return f'"{import_path}"'
        
        # Replace both single and double quoted imports in from statements
        content = re.sub(r'from\s+["\']([^"\']+)["\']', lambda m: f'from {replace_import(m)}', content)
        # Replace import statements
        def replace_import_statement(match):
            import_part = match.group(1)
            import_path = match.group(2)
            mock_match = type("", (), {"group": lambda _, i: import_path if i == 1 else None})()
            return f'import {import_part} from {replace_import(mock_match)}'
        
        content = re.sub(r'import\s+([^"\']*?)\s+from\s+["\']([^"\']+)["\']', replace_import_statement, content)
        
        return content

    def build_component_tree(self, route: str) -> List[str]:
        """
        Build an ordered list of layout.tsx and page.tsx files for a given route.
        """
        segments = route.strip("/").split("/") if route != "/" else []
        files = []
        current_path = self.project_root / "app"

        logger.debug(f"Building component tree for route: {route}")
        logger.debug(f"Project root: {self.project_root}")
        logger.debug(f"App directory: {current_path}")
        logger.debug(f"App directory exists: {current_path.exists()}")

        if not current_path.exists():
            logger.debug("App directory does not exist")
            return []

        # List contents of app directory for debugging
        if current_path.exists():
            app_contents = list(current_path.iterdir())
            logger.debug(f"App directory contents: {[f.name for f in app_contents]}")

        # 1. Root layout
        root_layout = current_path / "layout.tsx"
        logger.debug(f"Checking root layout: {root_layout}")
        logger.debug(f"Root layout exists: {root_layout.exists()}")
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
        logger.debug(f"Page file exists: {page_file.exists()}")
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

    def compile_with_swc(self, files: List[str]) -> str:
        """
        Compile TSX files using SWC via Node.js or fallback methods
        """
        # Try to use the existing compile.js script first
        compile_js_path = Path(__file__).resolve().parent.parent / "compile.js"
        
        if compile_js_path.exists():
            return self._compile_with_node_script(files, compile_js_path)
        
        # Fallback to direct SWC binary if available
        if self.swc_binary:
            return self._compile_with_swc_binary(files)
        
        # Final fallback: simple TypeScript to JavaScript transformation
        logger.warning("SWC not available, using basic TypeScript transformation")
        return self._compile_with_basic_transform(files)

    def _compile_with_node_script(self, files: List[str], compile_script: Path) -> str:
        """Use the existing Node.js compile script"""
        try:
            # Prepare files list as JSON with proper path normalization
            normalized_files = [str(Path(f).as_posix()) for f in files]
            files_json = json.dumps(normalized_files)
            
            cmd = ["node", str(compile_script), files_json]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                shell=True,
                cwd=self.project_root,
                encoding='utf-8',
                errors='replace'
            )
            if result.stdout:
                return result.stdout.strip()
            else:
                logger.error("Node.js compilation returned empty output")
                return ""
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Node.js compilation failed: {e.stderr}")
            raise RuntimeError(f"Node.js compilation failed: {e.stderr}") from e
        except FileNotFoundError:
            logger.error("Node.js not found")
            raise RuntimeError("Node.js not found. Please install Node.js to compile React components.")

    def _compile_with_swc_binary(self, files: List[str]) -> str:
        """Compile using SWC binary"""
        compiled_modules = []
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            for i, file_path in enumerate(files):
                file_path_obj = Path(file_path)
                
                # Read and resolve imports
                content = file_path_obj.read_text()
                resolved_content = self.resolve_import(content, file_path)
                
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
                
                if self.swc_binary.startswith("npx"):
                    cmd = [
                        "npx", "@swc/cli",
                        str(temp_file),
                        "-o", str(output_file),
                        "--config-file", str(config_file)
                    ]
                else:
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
                        shell=True,
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

    def _compile_with_basic_transform(self, files: List[str]) -> str:
        """Basic TypeScript to JavaScript transformation as fallback"""
        compiled_modules = []
        
        for i, file_path in enumerate(files):
            file_path_obj = Path(file_path)
            content = file_path_obj.read_text()
            
            # Basic transformations
            # Remove TypeScript types and interfaces
            import re
            
            # Remove interface declarations
            content = re.sub(r'interface\s+\w+\s*{[^}]*}', '', content, flags=re.DOTALL)
            
            # Remove type annotations
            content = re.sub(r':\s*\w+(\[\])?(\s*\|\s*\w+)*', '', content)
            content = re.sub(r'<[^>]+>', '', content)  # Remove generic types
            
            # Replace JSX with React.createElement calls (basic)
            # This is a very basic transformation - in production you'd want proper JSX parsing
            
            export_name = f"Layout{i}" if i < len(files) - 1 else "Page"
            
            # Simple export default replacement
            content = content.replace('export default', f'const {export_name} =')
            
            compiled_modules.append(content)
        
        return "\n".join(compiled_modules)

    def render_with_node(self, compiled_js: str, num_layouts: int) -> str:
        """
        Use Node.js to render the React components to HTML
        """
        if not self.render_js_path.exists():
            raise FileNotFoundError(f"Render script not found at {self.render_js_path}")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            # Write the compiled components and render logic
            render_script = f"""
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
            # Use absolute path to the temporary script but run from project root
            # so Node.js can find the node_modules
            cmd = ["node", os.path.abspath(temp_script_path)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                shell=True,
                cwd=str(self.project_root.parent),  # Run from the framework root where node_modules is
                encoding='utf-8',
                errors='replace'
            )
            if result.stdout:
                return result.stdout.strip()
            else:
                logger.error("Node.js script returned empty output")
                return ""
            
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