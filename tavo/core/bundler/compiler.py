"""
SWC Compiler integration with caching and optimization

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
import time
from pathlib import Path
from typing import List, Optional, Any, Dict, Tuple
from dataclasses import dataclass

from .installer import SWCInstaller
from .resolver import ImportResolver
from .layouts import LayoutComposer
from .constants import DEFAULT_SWC_TIMEOUT, DIST_DIR, COMPILATION_TYPES
from .utils import read_file, write_file_atomic, safe_mkdir

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


@dataclass
class CompilationResult:
    """Result of a compilation operation"""
    compiled_js: str
    bundled_tsx_path: Optional[Path]
    source_files: List[Path]
    cache_hit: bool
    compilation_time: float
    output_size: int


class SWCCompiler:
    """Compiles React/TypeScript components using SWC"""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.installer = SWCInstaller()
        self.resolver = ImportResolver(project_root)
        self.composer = LayoutComposer()
        
        # Setup cache directories
        self.tavo_cache_dir = project_root / ".tavo"
        self.cache_dir = self.tavo_cache_dir / "swc_cache"
        self.debug_dir = self.tavo_cache_dir / "debug"
        
        safe_mkdir(self.cache_dir)
        safe_mkdir(self.debug_dir)
        
        self.cache_index_file = self.cache_dir / "cache_index.pkl"
        self._swc_available = None
        self._cache_index = self._load_cache_index()
        
        # Stats
        self._compilation_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_compilations": 0,
            "total_time": 0.0
        }

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
                        updated_cache[key] = entry
                    else:
                        # Migrate old format
                        logger.info(f"Migrating old cache entry: {key[:8]}...")
                        new_entry = CacheEntry(
                            compiled_js=entry.compiled_js,
                            bundled_tsx="",
                            file_hashes=entry.file_hashes,
                            config_hash=entry.config_hash,
                            compilation_type=entry.compilation_type,
                            timestamp=entry.timestamp
                        )
                        updated_cache[key] = new_entry
                
                return updated_cache
                
            except Exception as e:
                logger.warning(f"Failed to load cache index: {e}")
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

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate hash of a file's content"""
        try:
            if not file_path.exists():
                return ""
            
            content = read_file(file_path)
            mtime = str(file_path.stat().st_mtime)
            hash_input = content.encode('utf-8') + mtime.encode('utf-8')
            
            return hashlib.sha256(hash_input).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to calculate hash for {file_path}: {e}")
            return ""

    def _calculate_files_hash(self, files: List[Path]) -> Dict[str, str]:
        """Calculate hashes for all input files"""
        return {str(file_path): self._calculate_file_hash(file_path) for file_path in files}

    def _calculate_config_hash(self) -> str:
        """Calculate hash of the SWC configuration"""
        config = self.get_swc_config()
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode('utf-8')).hexdigest()

    def _get_cache_key(self, files: List[Path], compilation_type: str = "default") -> str:
        """Generate cache key for a set of files and compilation type"""
        sorted_files = sorted(str(f) for f in files)
        files_str = "|".join(sorted_files)
        key_input = f"{files_str}|{compilation_type}"
        return hashlib.sha256(key_input.encode('utf-8')).hexdigest()

    def _is_cache_valid(self, cache_key: str, file_hashes: Dict[str, str], 
                       config_hash: str, compilation_type: str) -> bool:
        """Check if cache entry is still valid"""
        if cache_key not in self._cache_index:
            return False
        
        entry = self._cache_index[cache_key]
        
        return (entry.compilation_type == compilation_type and
                entry.config_hash == config_hash and
                entry.file_hashes == file_hashes and
                all(Path(file_path).exists() for file_path in file_hashes))

    def _store_in_cache(self, cache_key: str, compiled_js: str, bundled_tsx: str, 
                       file_hashes: Dict[str, str], config_hash: str, compilation_type: str):
        """Store compilation result in cache"""
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
        
        # Save debug file
        debug_file = self.debug_dir / f"{cache_key[:12]}_bundled.tsx"
        write_file_atomic(debug_file, bundled_tsx)
        logger.info(f"Stored bundled TSX for debugging: {debug_file}")

    def _get_from_cache(self, cache_key: str) -> Optional[Tuple[str, str]]:
        """Retrieve compilation result from cache"""
        if cache_key in self._cache_index:
            entry = self._cache_index[cache_key]
            bundled_tsx = getattr(entry, 'bundled_tsx', "")
            
            # Restore debug file if we have content
            if bundled_tsx:
                debug_file = self.debug_dir / f"{cache_key[:12]}_bundled.tsx"
                write_file_atomic(debug_file, bundled_tsx)
            
            logger.debug(f"Using cached compilation result: {cache_key[:8]}...")
            return entry.compiled_js, bundled_tsx
        return None

    def clear_cache(self, older_than_days: Optional[int] = None):
        """Clear compilation cache"""
        if older_than_days is None:
            self._cache_index.clear()
            # Clean up debug files
            for tsx_file in self.debug_dir.glob("*_bundled.tsx"):
                tsx_file.unlink()
            logger.info("Cleared all compilation cache")
        else:
            cutoff_time = time.time() - (older_than_days * 24 * 60 * 60)
            keys_to_remove = [
                key for key, entry in self._cache_index.items() 
                if entry.timestamp < cutoff_time
            ]
            
            for key in keys_to_remove:
                debug_file = self.debug_dir / f"{key[:12]}_bundled.tsx"
                if debug_file.exists():
                    debug_file.unlink()
                del self._cache_index[key]
            
            logger.info(f"Cleared {len(keys_to_remove)} cache entries older than {older_than_days} days")
        
        self._save_cache_index()

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total_entries = len(self._cache_index)
        total_size = sum(
            len(entry.compiled_js.encode('utf-8')) + 
            len(getattr(entry, 'bundled_tsx', '').encode('utf-8'))
            for entry in self._cache_index.values()
        )
        
        return {
            'total_entries': total_entries,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': str(self.cache_dir),
            **self._compilation_stats
        }

    def ensure_swc_available(self) -> bool:
        """Ensure SWC is available for compilation"""
        if self._swc_available is None:
            self._swc_available = self.installer.ensure_swc_available()
        return self._swc_available

    def get_swc_config(self, compilation_type: str = "default") -> dict:
        """Get SWC configuration for React/TypeScript compilation"""
        base_config = {
            "jsc": {
                "parser": {
                    "syntax": "typescript",
                    "tsx": True,
                    "decorators": True,
                    "dynamicImport": True
                },
                "baseUrl": "../../",
                "paths": {
                "@/*": ["./*"]
                },
                "transform": {
                    "react": {
                        "runtime": "classic",
                        "pragma": "React.createElement",
                        "pragmaFrag": "React.Fragment",
                        "throwIfNamespace": True,
                        "development": compilation_type == "development",
                        "useBuiltins": False,
                        "refresh": compilation_type == "development"
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
                "type": "es6" if compilation_type != "ssr" else "commonjs",
                "strict": False,
                "strictMode": True,
                "lazy": False,
                "noInterop": False
            },
            "minify": compilation_type == "production",
            "isModule": True,
            "sourceMaps": os.getenv("TAVO_SOURCE_MAPS", "false").lower() == "true"
        }
        
        return base_config

    def strip_js_comments(self, code: str) -> str:
        """Remove JavaScript comments from code while preserving strings"""
        pattern = re.compile(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)|(//[^\n]*|/\*[\s\S]*?\*/)')
        
        def replacer(match):
            return match.group(1) if match.group(1) else ''
        
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

    def clean_compiled_output(self, compiled_js: str) -> str:
        """Clean and optimize compiled JavaScript output"""
        lines = compiled_js.split('\n')
        
        # Basic cleanup
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('//'):
                continue
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        
        # Ensure React import
        if ('React.' in result or 'createElement' in result) and 'import React' not in result:
            result = 'const React = require("react");\n\n' + result + '\n' + 'module.exports = exports.default;'
        
        return result

    def _compile_with_swc_dual(self, files: List[Path]) -> Tuple[str, str, str]:
        """
        Compile with SWC for both SSR and Hydration.
        Returns (ssr_js, hydration_js, bundled_content)
        """
        swc_command = self.installer.get_swc_command()
        if not swc_command:
            raise RuntimeError("SWC command not available")

        temp_dir = self.debug_dir / "current_compilation"
        safe_mkdir(temp_dir)

        # Create bundled file
        bundled_file = self.resolver.create_single_file_for_swc(files, temp_dir)
        bundled_content = read_file(bundled_file)
        bundled_content = self.strip_js_comments(bundled_content)
        write_file_atomic(bundled_file, bundled_content)

        # ---- Compile SSR (commonjs) ----
        ssr_config = self.get_swc_config("ssr")
        ssr_config_file = temp_dir / ".swcrc.ssr"
        write_file_atomic(ssr_config_file, json.dumps(ssr_config, indent=2))
        ssr_out_file = temp_dir / "compiled.ssr.js"

        ssr_cmd = [
            swc_command,
            str(bundled_file),
            "-o", str(ssr_out_file),
            "--config-file", str(ssr_config_file)
        ]

        # ---- Compile Hydration (esm + bundle) ----
        hydration_config = self.get_swc_config("hydration")
        hydration_config_file = temp_dir / ".swcrc.hydration"
        write_file_atomic(hydration_config_file, json.dumps(hydration_config, indent=2))
        hydration_out_file = temp_dir / "compiled.hydration.js"

        hydration_cmd = [
            swc_command,
            str(bundled_file),
            "-o", str(hydration_out_file),
            "--config-file", str(hydration_config_file),
            "--bundle"
        ]

        env = os.environ.copy()
        timeout = int(os.getenv('TAVO_SWC_TIMEOUT', DEFAULT_SWC_TIMEOUT))

        try:
            # Run SSR
            subprocess.run(
                ssr_cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=self.project_root,
                env=env,
                timeout=timeout
            )
            if not ssr_out_file.exists():
                raise RuntimeError("SWC SSR compilation failed")

            ssr_js = read_file(ssr_out_file)
            ssr_js = self.clean_compiled_output(ssr_js)
            ssr_js = self._optimize_for_ssr(ssr_js)

            # Run Hydration
            subprocess.run(
                hydration_cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=self.project_root,
                env=env,
                timeout=timeout
            )
            if not hydration_out_file.exists():
                raise RuntimeError("SWC Hydration compilation failed")

            hydration_js = read_file(hydration_out_file)
            hydration_js = self.clean_compiled_output(hydration_js)
            hydration_js = self._optimize_for_client(hydration_js)

            return ssr_js, hydration_js, bundled_content

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"SWC failed (code {e.returncode})\n"
                f"Command: {' '.join(e.cmd)}\n"
                f"Stdout: {e.stdout}\nStderr: {e.stderr}"
            )

    def compile_for_ssr_and_hydration(self, files: List[Path], path: str) -> Dict[str, CompilationResult]:
        """
        Compile files for both SSR and Hydration.
        Returns dict: {"ssr": CompilationResult, "hydration": CompilationResult}
        """
        start_time = time.time()
        ssr_js, hydration_js, bundled_tsx = self._compile_with_swc_dual(files)

        duration = time.time() - start_time
        base_info = dict(
            bundled_tsx_path=None,
            source_files=files,
            cache_hit=False,
            compilation_time=duration,
        )

        return {
            "ssr": CompilationResult(
                compiled_js=ssr_js,
                output_size=len(ssr_js.encode("utf-8")),
                **base_info # type: ignore
            ),
            "hydration": CompilationResult(
                compiled_js=hydration_js,
                output_size=len(hydration_js.encode("utf-8")),
                **base_info # type: ignore
            )
        }

    def _compile_with_swc(self, files: List[Path], compilation_type: str = "default") -> Tuple[str, str]:
        """Perform the actual SWC compilation"""
        swc_command = self.installer.get_swc_command()
        if not swc_command:
            raise RuntimeError("SWC command not available")

        # Create temporary compilation directory
        temp_dir = self.debug_dir / "current_compilation"
        safe_mkdir(temp_dir)

        # Create bundled file
        bundled_file = self.resolver.create_single_file_for_swc(files, temp_dir)
        bundled_content = read_file(bundled_file)
        
        # Clean comments but preserve structure
        bundled_content = self.strip_js_comments(bundled_content)
        write_file_atomic(bundled_file, bundled_content)

        # Create SWC config
        config = self.get_swc_config(compilation_type)
        config_file = temp_dir / ".swcrc"
        write_file_atomic(config_file, json.dumps(config, indent=2))

        output_file = temp_dir / "compiled.js"

        # Build SWC command
        cmd = [
            swc_command,
            str(bundled_file),
            "-o", str(output_file),
            "--config-file", str(config_file)
        ]

        try:
            env = os.environ.copy()
            env['NODE_ENV'] = 'production' if compilation_type == 'production' else 'development'

            timeout = int(os.getenv('TAVO_SWC_TIMEOUT', DEFAULT_SWC_TIMEOUT))
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=self.project_root,
                env=env,
                encoding='utf-8',
                timeout=timeout
            )

            if not output_file.exists():
                raise RuntimeError("SWC compilation did not produce output file")

            compiled_content = read_file(output_file)
            compiled_content = self.clean_compiled_output(compiled_content)
            compiled_content = self.transform_react_hooks(compiled_content)

            return compiled_content, bundled_content

        except subprocess.CalledProcessError as e:
            error_msg = (
                f"SWC compilation failed (code {e.returncode}):\n"
                f"Command: {' '.join(cmd)}\n"
                f"Stdout: {e.stdout or 'No stdout'}\n"
                f"Stderr: {e.stderr or 'No stderr'}"
                f"Bundled content preview:\n{bundled_content[:500]}..."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"SWC compilation timed out after {timeout} seconds")

    def compile_files(self, files: List[Path], path: str, compilation_type: str = "default") -> CompilationResult:
        """Compile a list of React/TypeScript files with caching"""
        if compilation_type not in COMPILATION_TYPES:
            raise ValueError(f"Invalid compilation type: {compilation_type}")
            
        if not self.ensure_swc_available():
            self.installer.check_and_raise_if_unavailable()
        
        start_time = time.time()
        
        # Calculate hashes for cache validation
        file_hashes = self._calculate_files_hash(files)
        config_hash = self._calculate_config_hash()
        cache_key = self._get_cache_key(files, compilation_type)
        
        # Check cache first
        cache_hit = False
        if self._is_cache_valid(cache_key, file_hashes, config_hash, compilation_type):
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                compiled_js, bundled_tsx = cached_result
                cache_hit = True
                self._compilation_stats["cache_hits"] += 1
        
        if not cache_hit:
            # Compile if not in cache or cache is invalid
            logger.info(f"Compiling {len(files)} files (cache miss)")
            compiled_js, bundled_tsx = self._compile_with_swc(files, compilation_type)
            
            # Store result in cache
            self._store_in_cache(cache_key, compiled_js, bundled_tsx, file_hashes, config_hash, compilation_type)
            self._compilation_stats["cache_misses"] += 1
        
        compilation_time = time.time() - start_time
        self._compilation_stats["total_compilations"] += 1
        self._compilation_stats["total_time"] += compilation_time
        
        # Find debug file path
        debug_file = self.debug_dir / f"{cache_key[:12]}_bundled.tsx"
        
        result = CompilationResult(
            compiled_js=compiled_js,
            bundled_tsx_path=debug_file if debug_file.exists() else None,
            source_files=files,
            cache_hit=cache_hit,
            compilation_time=compilation_time,
            output_size=len(compiled_js.encode('utf-8'))
        )
        
        logger.info(f"Compiled {path} in {compilation_time:.2f}s (cache_hit={cache_hit})")
        return result

    def compile_for_ssr(self, files: List[Path], path: str) -> CompilationResult:
        """Compile files specifically for server-side rendering"""
        result = self.compile_files(files, path, compilation_type="ssr")
        
        # Apply SSR-specific optimizations
        ssr_optimized = self._optimize_for_ssr(result.compiled_js)
        result.compiled_js = ssr_optimized
        
        return result

    def compile_for_hydration(self, path: str, files: List[Path]) -> CompilationResult:
        """Compile files for client-side hydration"""
        result = self.compile_files(files, path, compilation_type="hydration")
        
        # Apply client-specific optimizations
        client_optimized = self._optimize_for_client(result.compiled_js)
        result.compiled_js = client_optimized
        
        return result

    def _optimize_for_ssr(self, compiled_js: str) -> str:
        """Apply SSR-specific optimizations"""
        ssr_js = compiled_js
        
        # Remove client-only code patterns
        client_only_patterns = [
            r'window\.[^;]*;?',
            r'document\.[^;]*;?',
            r'navigator\.[^;]*;?',
            r'localStorage\.[^;]*;?',
            r'sessionStorage\.[^;]*;?'
        ]
        
        for pattern in client_only_patterns:
            ssr_js = re.sub(pattern, '/* client-only code removed */', ssr_js, flags=re.MULTILINE)
        
        # Remove console statements
        ssr_js = re.sub(r'console\.(log|debug|info)\([^)]*\);?', '', ssr_js, flags=re.MULTILINE)
        
        return ssr_js

    def _optimize_for_client(self, compiled_js: str) -> str:
        """Apply client-specific optimizations"""
        client_js = compiled_js
        
        # Add browser environment checks for hooks
        if 'useEffect' in client_js:
            client_js = client_js.replace(
                'React.useEffect(() => {',
                'React.useEffect(() => {\n    if (typeof window === "undefined") return;'
            )
        
        return client_js

    def build_all(self) -> Dict[str, Any]:
        """Build all routes for production"""
        logger.info("Starting production build...")
        
        routes = self.resolver.resolve_routes()
        if not routes:
            logger.warning("No routes found to build")
            return {"routes": 0, "success": True}
        
        # Setup output directories
        dist_dir = self.project_root / DIST_DIR
        client_dir = dist_dir / "client"
        server_dir = dist_dir / "server"
        
        safe_mkdir(client_dir)
        safe_mkdir(server_dir)
        
        build_results = []
        
        for route in routes:
            try:
                route_files = list(route.all_files)
                
                # Compile for client (hydration)
                client_result = self.compile_for_hydration(files=route_files, path=route.route_path)
                client_file = client_dir / f"{route.route_path.replace('/', '_') or 'index'}.js"
                write_file_atomic(client_file, client_result.compiled_js)
                
                # Compile for server (SSR)
                server_result = self.compile_for_ssr(route_files, path=route.route_path)
                server_file = server_dir / f"{route.route_path.replace('/', '_') or 'index'}.js"
                write_file_atomic(server_file, server_result.compiled_js)
                
                build_results.append({
                    "route": route.route_path,
                    "client_file": str(client_file),
                    "server_file": str(server_file),
                    "client_size": client_result.output_size,
                    "server_size": server_result.output_size,
                    "cache_hit": client_result.cache_hit and server_result.cache_hit
                })
                
                logger.info(f"Built route: {route.route_path}")
                
            except Exception as e:
                logger.error(f"Failed to build route {route.route_path}: {e}")
                build_results.append({
                    "route": route.route_path,
                    "error": str(e)
                })
        
        total_client_size = sum(r.get("client_size", 0) for r in build_results)
        total_server_size = sum(r.get("server_size", 0) for r in build_results)
        
        result = {
            "routes": len(routes),
            "success": len([r for r in build_results if "error" not in r]),
            "errors": len([r for r in build_results if "error" in r]),
            "total_client_size": total_client_size,
            "total_server_size": total_server_size,
            "build_results": build_results,
            "output_dirs": {
                "client": str(client_dir),
                "server": str(server_dir)
            }
        }
        
        logger.info(f"Build completed: {result['success']}/{result['routes']} routes successful")
        return result

    def watch_and_rebuild(self, route_entries, onchange_callback):
        """Watch for file changes and trigger rebuilds"""
        # This is a placeholder - actual file watching would be handled
        # by the DevServer using watchdog or similar
        logger.info(f"Watching {len(route_entries)} routes for changes...")
        
        def rebuild_callback(changed_files):
            logger.info(f"Files changed: {changed_files}")
            # Invalidate relevant cache entries
            for route in route_entries:
                if any(str(f) in [str(cf) for cf in changed_files] for f in route.all_files):
                    cache_key = self._get_cache_key(list(route.all_files))
                    if cache_key in self._cache_index:
                        del self._cache_index[cache_key]
                        logger.info(f"Invalidated cache for route: {route.route_path}")
            
            # Trigger callback
            if onchange_callback:
                onchange_callback(changed_files)
        
        return rebuild_callback

    def get_compilation_stats(self) -> Dict:
        """Get detailed compilation statistics"""
        return {
            **self.get_cache_stats(),
            "swc_available": self.ensure_swc_available(),
            "swc_version": self.installer.get_version()
        }