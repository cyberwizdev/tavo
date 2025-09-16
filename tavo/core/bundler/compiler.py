"""
SWC Compiler

Handles compilation of React/TypeScript components using SWC via subprocess.
"""

import subprocess
import json
import tempfile
import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Set, Dict

from .installer import SWCInstaller
from .resolver import ImportResolver

logger = logging.getLogger(__name__)


class SWCCompiler:
    """Compiles React/TypeScript components using SWC"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.installer = SWCInstaller()
        self.resolver = ImportResolver(project_root)
        self.tavo_cache_dir = project_root / ".tavo"
        self.tavo_cache_dir.mkdir(exist_ok=True)
        self._swc_available = None
    
    def ensure_swc_available(self) -> bool:
        """Ensure SWC is available for compilation"""
        if self._swc_available is None:
            self._swc_available = self.installer.ensure_swc_available()
        return self._swc_available
    
    def get_swc_config(self) -> dict:
        """Get SWC configuration for React/TypeScript compilation"""
        return {
            "jsc": {
                "parser": {
                    "syntax": "typescript",
                    "tsx": True,
                    "decorators": True,
                    "dynamicImport": True
                },
                "transform": {
                    "react": {
                        "runtime": "classic",
                        "pragma": "React.createElement",
                        "pragmaFrag": "React.Fragment",
                        "throwIfNamespace": True,
                        "development": False,
                        "useBuiltins": False,
                        "refresh": False
                    },
                    "decoratorMetadata": False,
                    "legacyDecorator": True
                },
                "target": "es2020",
                "loose": False,
                "externalHelpers": False,
                "keepClassNames": True,
                "preserveAllComments": False
            },
            "module": {
                "type": "es6",
                "strict": False,
                "strictMode": True,
                "lazy": False,
                "noInterop": False
            },
            "minify": False,
            "isModule": True,
            "sourceMaps": False
        }
    
    def clean_compiled_output(self, compiled_js: str) -> str:
        """Clean and optimize compiled JavaScript output"""
        lines = compiled_js.split('\n')
        cleaned_lines = []
        
        react_import_found = False
        react_imports = set()
        other_imports = []
        export_statements = []
        regular_code = []
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped or stripped.startswith('//'):
                cleaned_lines.append(line)
                continue
            
            if self._is_react_import(stripped):
                self._collect_react_import(stripped, react_imports)
                react_import_found = True
                continue
            
            if stripped.startswith('import '):
                other_imports.append(line)
                continue
            
            if stripped.startswith('export '):
                export_statements.append(line)
                continue
            
            regular_code.append(line)
        
        result_lines = []
        
        if react_import_found or self._needs_react_import(compiled_js):
            result_lines.append('import React from "react";')
        
        result_lines.extend(other_imports)
        
        if result_lines and (other_imports or react_import_found):
            result_lines.append('')
        
        result_lines.extend(regular_code)
        
        unique_exports = self._deduplicate_exports(export_statements)
        if unique_exports:
            result_lines.append('')
            result_lines.extend(unique_exports)
        
        return '\n'.join(result_lines)
    
    def _is_react_import(self, line: str) -> bool:
        """Check if line is a React import"""
        return 'import' in line and 'react' in line.lower() and ('from' in line or line.endswith('"') or line.endswith("'"))
    
    def _collect_react_import(self, line: str, imports_set: Set[str]) -> None:
        """Collect React imports for deduplication"""
        named_match = re.search(r'import\s*\{\s*([^}]+)\s*\}\s*from\s*["\']react["\']', line)
        if named_match:
            named_imports = [imp.strip() for imp in named_match.group(1).split(',')]
            imports_set.update(named_imports)
    
    def _needs_react_import(self, code: str) -> bool:
        """Check if code needs React import"""
        react_usage_patterns = [
            r'React\.',
            r'<[A-Z][a-zA-Z0-9]*',
            r'createElement',
            r'Fragment'
        ]
        
        for pattern in react_usage_patterns:
            if re.search(pattern, code):
                return True
        
        return False
    
    def _deduplicate_exports(self, exports: List[str]) -> List[str]:
        """Remove duplicate exports and handle default exports"""
        default_exports = []
        named_exports = []
        seen_named = set()
        
        for export_line in exports:
            stripped = export_line.strip()
            
            if stripped.startswith('export default'):
                default_exports.append(export_line)
            elif stripped not in seen_named:
                seen_named.add(stripped)
                named_exports.append(export_line)
        
        result = named_exports[:]
        
        if default_exports:
            result.append(default_exports[-1])
        
        return result
    
    def transform_react_hooks(self, code: str) -> str:
        """Transform standalone React hooks to React.hook format"""
        hooks_and_functions = {
            'useState': 'React.useState',
            'useEffect': 'React.useEffect', 
            'useContext': 'React.useContext',
            'useReducer': 'React.useReducer',
            'useCallback': 'React.useCallback',
            'useMemo': 'React.useMemo',
            'useRef': 'React.useRef',
            'useLayoutEffect': 'React.useLayoutEffect',
            'useImperativeHandle': 'React.useImperativeHandle',
            'useDebugValue': 'React.useDebugValue',
            'createContext': 'React.createContext',
            'forwardRef': 'React.forwardRef',
            'memo': 'React.memo',
            'lazy': 'React.lazy',
            'Suspense': 'React.Suspense',
            'Fragment': 'React.Fragment',
            'Component': 'React.Component',
            'PureComponent': 'React.PureComponent'
        }
        
        transformed = code
        
        for hook, replacement in hooks_and_functions.items():
            pattern = rf'\b(?<!React\.){hook}\b(?=\s*[\(\<\.])'
            transformed = re.sub(pattern, replacement, transformed)
        
        return transformed
    
    def compile_files(self, files: List[str]) -> str:
        """Compile a list of React/TypeScript files"""
        if not self.ensure_swc_available():
            raise RuntimeError("SWC is not available. Install Node.js and npm.")
        
        swc_command = self.installer.get_swc_command()
        if not swc_command:
            raise RuntimeError("SWC command not available")
        
        with tempfile.TemporaryDirectory(dir=self.tavo_cache_dir) as temp_dir:
            temp_path = Path(temp_dir)
            
            bundled_file = self.resolver.create_single_file_for_swc(files, temp_path)
            
            config = self.get_swc_config()
            config_file = temp_path / ".swcrc"
            config_file.write_text(json.dumps(config, indent=2))
            
            output_file = temp_path / "compiled.js"
            
            cmd = [
                swc_command,
                str(bundled_file),
                "-o", str(output_file),
                "--config-file", str(config_file)
            ]
            
            try:
                env = os.environ.copy()
                env['NODE_ENV'] = 'production'
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    shell=True,
                    cwd=self.project_root,
                    env=env,
                    encoding='utf-8',
                    timeout=30
                )
                
                if not output_file.exists():
                    raise RuntimeError("SWC compilation did not produce output file")
                    
                compiled_content = output_file.read_text(encoding='utf-8')
                compiled_content = self.clean_compiled_output(compiled_content)
                compiled_content = self.transform_react_hooks(compiled_content)
                
                logger.info(f"Successfully compiled {len(files)} files")
                return compiled_content
                    
            except subprocess.CalledProcessError as e:
                error_details = {
                    'command': ' '.join(cmd),
                    'stdout': e.stdout or 'No stdout',
                    'stderr': e.stderr or 'No stderr',
                    'return_code': e.returncode
                }
                
                error_msg = (
                    f"SWC compilation failed (code {error_details['return_code']}):\n"
                    f"Command: {error_details['command']}\n"
                    f"Stdout: {error_details['stdout']}\n"
                    f"Stderr: {error_details['stderr']}"
                )
                
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
                
            except subprocess.TimeoutExpired:
                raise RuntimeError("SWC compilation timed out after 30 seconds")
            except Exception as e:
                logger.error(f"Unexpected error during compilation: {e}")
                raise RuntimeError(f"Compilation failed: {e}") from e
    
    def compile_for_ssr(self, files: List[str]) -> str:
        """Compile files specifically for server-side rendering"""
        compiled_js = self.compile_files(files)
        
        ssr_optimized = self._optimize_for_ssr(compiled_js)
        return ssr_optimized
    
    def compile_for_hydration(self, files: List[str]) -> str:
        """Compile files for client-side hydration"""
        compiled_js = self.compile_files(files)
        
        client_optimized = self._optimize_for_client(compiled_js)
        return client_optimized
    
    def _optimize_for_ssr(self, compiled_js: str) -> str:
        """Apply SSR-specific optimizations"""
        ssr_js = compiled_js
        
        if 'React.createElement' in ssr_js and not ssr_js.strip().startswith('import React'):
            ssr_js = 'import React from "react";\n\n' + ssr_js
        
        ssr_js = re.sub(r'console\.(log|debug|info)\([^)]*\);?', '', ssr_js, flags=re.MULTILINE)
        
        client_only_patterns = [
            r'window\.',
            r'document\.',
            r'navigator\.',
            r'localStorage\.',
            r'sessionStorage\.'
        ]
        
        for pattern in client_only_patterns:
            ssr_js = re.sub(
                pattern + r'[^;]*;?',
                '/* client-only code removed */',
                ssr_js,
                flags=re.MULTILINE
            )
        
        return ssr_js
    
    def _optimize_for_client(self, compiled_js: str) -> str:
        """Apply client-specific optimizations"""
        client_js = compiled_js
        
        if 'useEffect' in client_js:
            client_js = client_js.replace(
                'React.useEffect(() => {',
                'React.useEffect(() => {\n    if (typeof window === "undefined") return;'
            )
        
        return client_js
    
    def get_compilation_stats(self, files: List[str]) -> Dict:
        """Get compilation statistics"""
        total_size = 0
        file_count = len(files)
        
        for file_path in files:
            try:
                total_size += Path(file_path).stat().st_size
            except Exception:
                continue
        
        return {
            'file_count': file_count,
            'total_source_size': total_size,
            'average_file_size': total_size / file_count if file_count > 0 else 0
        }