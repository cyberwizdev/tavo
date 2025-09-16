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
import hashlib
import pickle
from pathlib import Path
from typing import List, Optional, Set, Dict
from dataclasses import dataclass

from .installer import SWCInstaller
from .resolver import ImportResolver

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry for compiled files"""
    compiled_js: str
    bundled_tsx: str  # Store the intermediate bundled TSX file
    file_hashes: Dict[str, str]
    config_hash: str
    compilation_type: str
    timestamp: float


class SWCCompiler:
    """Compiles React/TypeScript components using SWC"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.installer = SWCInstaller()
        self.resolver = ImportResolver(project_root)
        self.tavo_cache_dir = project_root / ".tavo"
        self.cache_dir = self.tavo_cache_dir / "swc_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_index_file = self.cache_dir / "cache_index.pkl"
        self._swc_available = None
        self._cache_index = self._load_cache_index()
    
    def _load_cache_index(self) -> Dict[str, CacheEntry]:
        """Load cache index from disk"""
        if self.cache_index_file.exists():
            try:
                with open(self.cache_index_file, 'rb') as f:
                    cache_data = pickle.load(f)
                
                # Handle backward compatibility for old cache entries
                updated_cache = {}
                for key, entry in cache_data.items():
                    if hasattr(entry, 'bundled_tsx'):
                        # New format - use as is
                        updated_cache[key] = entry
                    else:
                        # Old format - add missing bundled_tsx field
                        logger.info(f"Migrating old cache entry: {key[:8]}...")
                        new_entry = CacheEntry(
                            compiled_js=entry.compiled_js,
                            bundled_tsx="",  # Empty for old entries
                            file_hashes=entry.file_hashes,
                            config_hash=entry.config_hash,
                            compilation_type=entry.compilation_type,
                            timestamp=entry.timestamp
                        )
                        updated_cache[key] = new_entry
                
                return updated_cache
            except Exception as e:
                logger.warning(f"Failed to load cache index: {e}")
                # Clear corrupted cache
                try:
                    self.cache_index_file.unlink()
                    logger.info("Cleared corrupted cache index")
                except:
                    pass
        return {}
    
    def _save_cache_index(self):
        """Save cache index to disk"""
        try:
            with open(self.cache_index_file, 'wb') as f:
                pickle.dump(self._cache_index, f)
        except Exception as e:
            logger.warning(f"Failed to save cache index: {e}")
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate hash of a file's content"""
        try:
            path = Path(file_path)
            if not path.exists():
                return ""
            
            with open(path, 'rb') as f:
                content = f.read()
            
            # Include file modification time in hash for extra safety
            mtime = str(path.stat().st_mtime)
            hash_input = content + mtime.encode('utf-8')
            
            return hashlib.sha256(hash_input).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to calculate hash for {file_path}: {e}")
            return ""
    
    def _calculate_files_hash(self, files: List[str]) -> Dict[str, str]:
        """Calculate hashes for all input files"""
        file_hashes = {}
        for file_path in files:
            file_hashes[file_path] = self._calculate_file_hash(file_path)
        return file_hashes
    
    def _calculate_config_hash(self) -> str:
        """Calculate hash of the SWC configuration"""
        config = self.get_swc_config()
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode('utf-8')).hexdigest()
    
    def _get_cache_key(self, files: List[str], compilation_type: str = "default") -> str:
        """Generate cache key for a set of files and compilation type"""
        # Sort files for consistent cache keys
        sorted_files = sorted(files)
        files_str = "|".join(sorted_files)
        key_input = f"{files_str}|{compilation_type}"
        return hashlib.sha256(key_input.encode('utf-8')).hexdigest()
    
    def _is_cache_valid(self, cache_key: str, file_hashes: Dict[str, str], config_hash: str, compilation_type: str) -> bool:
        """Check if cache entry is still valid"""
        if cache_key not in self._cache_index:
            return False
        
        entry = self._cache_index[cache_key]
        
        # Check if compilation type matches
        if entry.compilation_type != compilation_type:
            return False
        
        # Check if config has changed
        if entry.config_hash != config_hash:
            return False
        
        # Check if any file has changed
        if entry.file_hashes != file_hashes:
            return False
        
        # Verify all files still exist
        for file_path in file_hashes:
            if not Path(file_path).exists():
                return False
        
        return True
    
    def _store_in_cache(self, cache_key: str, compiled_js: str, bundled_tsx: str, 
                       file_hashes: Dict[str, str], config_hash: str, compilation_type: str):
        """Store compilation result in cache"""
        import time
        
        entry = CacheEntry(
            compiled_js=compiled_js,
            bundled_tsx=bundled_tsx,
            file_hashes=file_hashes,
            config_hash=config_hash,
            compilation_type=compilation_type,
            timestamp=time.time()
        )
        
        self._cache_index[cache_key] = entry
        self._save_cache_index()
        
        # Also save the bundled TSX file to disk for debugging
        debug_file = self.cache_dir / f"{cache_key[:12]}_bundled.tsx"
        try:
            debug_file.write_text(bundled_tsx, encoding='utf-8')
            logger.info(f"Stored bundled TSX for debugging: {debug_file}")
        except Exception as e:
            logger.warning(f"Failed to save debug TSX file: {e}")
        
        logger.info(f"Stored compilation result in cache: {cache_key[:8]}...")
    
    def _get_from_cache(self, cache_key: str) -> Optional[tuple[str, str]]:
        """Retrieve compilation result from cache"""
        if cache_key in self._cache_index:
            entry = self._cache_index[cache_key]
            
            # Handle backward compatibility - old entries might not have bundled_tsx
            bundled_tsx = getattr(entry, 'bundled_tsx', "")
            
            # Only try to restore debug file if we have bundled_tsx content
            if bundled_tsx:
                debug_file = self.cache_dir / f"{cache_key[:12]}_bundled.tsx"
                try:
                    debug_file.write_text(bundled_tsx, encoding='utf-8')
                    logger.info(f"Bundled TSX available at: {debug_file}")
                except Exception as e:
                    logger.warning(f"Failed to restore debug TSX file: {e}")
            
            logger.info(f"Using cached compilation result: {cache_key[:8]}...")
            return entry.compiled_js, bundled_tsx
        return None
    
    def clear_cache(self, older_than_days: Optional[int] = None):
        """Clear compilation cache"""
        if older_than_days is None:
            # Clear all cache
            self._cache_index.clear()
            
            # Also clean up debug TSX files
            try:
                for tsx_file in self.cache_dir.glob("*_bundled.tsx"):
                    tsx_file.unlink()
                logger.info("Cleared all debug TSX files")
            except Exception as e:
                logger.warning(f"Failed to clean debug TSX files: {e}")
            
            logger.info("Cleared all compilation cache")
        else:
            # Clear entries older than specified days
            import time
            cutoff_time = time.time() - (older_than_days * 24 * 60 * 60)
            
            keys_to_remove = []
            for key, entry in self._cache_index.items():
                if entry.timestamp < cutoff_time:
                    keys_to_remove.append(key)
            
            # Remove old debug TSX files
            for key in keys_to_remove:
                debug_file = self.cache_dir / f"{key[:12]}_bundled.tsx"
                try:
                    if debug_file.exists():
                        debug_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove debug TSX file {debug_file}: {e}")
                
                del self._cache_index[key]
            
            logger.info(f"Cleared {len(keys_to_remove)} cache entries older than {older_than_days} days")
        
        self._save_cache_index()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total_entries = len(self._cache_index)
        total_size = 0
        
        for entry in self._cache_index.values():
            total_size += len(entry.compiled_js.encode('utf-8'))
            # Handle backward compatibility for bundled_tsx
            bundled_tsx = getattr(entry, 'bundled_tsx', "")
            if bundled_tsx:
                total_size += len(bundled_tsx.encode('utf-8'))
        
        return {
            'total_entries': total_entries,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': str(self.cache_dir)
        }

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
                if code.strip().startswith('import React'):
                    return False
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


    def strip_js_comments(code: str) -> str:
        """
        Remove JavaScript comments (single-line // and multi-line /* */) from code.
        Preserves string literals so // inside strings won't be removed.
        """
        # Regex explanation:
        # - (\"(?:\\.|[^\"\\])*\"|\'(?:\\.|[^\'\\])*\'|\`(?:\\.|[^`\\])*\`) → match strings ("...", '...', `...`)
        # - | → OR
        # - (//[^\n]*|/\*[\s\S]*?\*/) → match // comments or /* block comments */
        pattern = re.compile(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)|(//[^\n]*|/\*[\s\S]*?\*/)')
        
        def replacer(match):
            if match.group(1):  # It's a string literal
                return match.group(1)
            else:
                return ''  # It's a comment, strip it
        
        return pattern.sub(replacer, code)

    
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
    
    def _compile_with_swc(self, files: List[str]) -> str:
        """Perform the actual SWC compilation"""
        swc_command = self.installer.get_swc_command()
        if not swc_command:
            raise RuntimeError("SWC command not available")

        # Permanent debug directory inside tavo_cache_dir
        temp_path = Path(self.tavo_cache_dir) / "swc_debug"
        temp_path.mkdir(parents=True, exist_ok=True)

        bundled_file = self.resolver.create_single_file_for_swc(files, temp_path)
        bundled_file = self.strip_js_comments(bundled_file)

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

            return compiled_content, output_file.read_text(encoding='utf-8')

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
   
    def compile_files(self, files: List[str], compilation_type: str = "default") -> str:
        """Compile a list of React/TypeScript files with caching"""
        if not self.ensure_swc_available():
            raise RuntimeError("SWC is not available. Install Node.js and npm.")
        
        # Calculate hashes for cache validation
        file_hashes = self._calculate_files_hash(files)
        config_hash = self._calculate_config_hash()
        cache_key = self._get_cache_key(files, compilation_type)
        
        # Check cache first
        if self._is_cache_valid(cache_key, file_hashes, config_hash, compilation_type):
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                compiled_js, bundled_tsx = cached_result
                return compiled_js
        
        # Compile if not in cache or cache is invalid
        logger.info(f"Compiling {len(files)} files (cache miss)")
        compiled_js, bundled_tsx = self._compile_with_swc(files)
        
        # Store result in cache
        self._store_in_cache(cache_key, compiled_js, bundled_tsx, file_hashes, config_hash, compilation_type)
        
        logger.info(f"Successfully compiled {len(files)} files")
        return compiled_js
    
    def compile_for_ssr(self, files: List[str]) -> str:
        """Compile files specifically for server-side rendering"""
        compiled_js = self.compile_files(files, compilation_type="ssr")
        
        ssr_optimized = self._optimize_for_ssr(compiled_js)
        return ssr_optimized
    
    def compile_for_hydration(self, files: List[str]) -> str:
        """Compile files for client-side hydration"""
        compiled_js = self.compile_files(files, compilation_type="hydration")
        
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
        
        cache_stats = self.get_cache_stats()
        
    def get_bundled_tsx_path(self, files: List[str], compilation_type: str = "default") -> Optional[Path]:
        """Get the path to the cached bundled TSX file for debugging"""
        cache_key = self._get_cache_key(files, compilation_type)
        debug_file = self.cache_dir / f"{cache_key[:12]}_bundled.tsx"
        
        if debug_file.exists():
            return debug_file
        return None
    
    def get_debug_info(self, files: List[str], compilation_type: str = "default") -> Dict:
        """Get debug information about a compilation"""
        cache_key = self._get_cache_key(files, compilation_type)
        debug_file = self.cache_dir / f"{cache_key[:12]}_bundled.tsx"
        compilation_dir = self.cache_dir / "current_compilation"
        
        info = {
            'cache_key': cache_key,
            'bundled_tsx_path': str(debug_file) if debug_file.exists() else None,
            'compilation_dir': str(compilation_dir) if compilation_dir.exists() else None,
            'is_cached': cache_key in self._cache_index,
            'files': files,
            'compilation_type': compilation_type
        }
        
        if cache_key in self._cache_index:
            entry = self._cache_index[cache_key]
            info['cache_timestamp'] = entry.timestamp
            # Handle backward compatibility for bundled_tsx
            bundled_tsx = getattr(entry, 'bundled_tsx', "")
            info['bundled_tsx_size'] = len(bundled_tsx) if bundled_tsx else 0
            info['compiled_js_size'] = len(entry.compiled_js)
        
        return {
            'file_count': file_count,
            'total_source_size': total_size,
            'average_file_size': total_size / file_count if file_count > 0 else 0,
            'cache_stats': cache_stats
        }