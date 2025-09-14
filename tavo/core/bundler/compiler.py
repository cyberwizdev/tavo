"""
SWC Compiler

Handles compilation of React/TypeScript components using SWC via subprocess.
"""

import subprocess
import json
import tempfile
import logging
import os
from pathlib import Path
from typing import List, Optional

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
    
    def ensure_swc_available(self) -> bool:
        """Ensure SWC is available for compilation"""
        return self.installer.ensure_swc_available()
    
    def get_swc_config(self) -> dict:
        """Get SWC configuration for React/TypeScript compilation"""
        return {
            "jsc": {
                "parser": {
                    "syntax": "typescript",
                    "tsx": True,
                    "decorators": False,
                    "dynamicImport": True
                },
                "transform": {
                    "react": {
                        "runtime": "automatic",
                        "pragma": "React.createElement",
                        "pragmaFrag": "React.Fragment",
                        "throwIfNamespace": True,
                        "development": False,
                        "useBuiltins": False
                    }
                },
                "target": "es2022",
                "loose": False,
                "externalHelpers": False,
                "keepClassNames": False,
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
            "isModule": True
        }
    
    def compile_files(self, files: List[str]) -> str:
        """Compile a list of React/TypeScript files"""
        if not self.ensure_swc_available():
            raise RuntimeError("SWC is not available. Please install Node.js and npm first.")
        
        swc_command = self.installer.get_swc_command()
        if not swc_command:
            raise RuntimeError("SWC command not available")
        
        with tempfile.TemporaryDirectory(dir=self.tavo_cache_dir) as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create bundled file with resolved imports
            bundled_file = self.resolver.create_single_file_for_swc(files, temp_path)
            
            # Create SWC config file
            config = self.get_swc_config()
            config_file = temp_path / ".swcrc"
            config_file.write_text(json.dumps(config, indent=2))
            
            # Output file
            output_file = temp_path / "compiled.js"
            
            # Prepare SWC command
            cmd = [
                "npx", "@swc/cli",
                str(bundled_file),
                "-o", str(output_file),
                "--config-file", str(config_file)
            ]
            
            try:
                # Run SWC compilation from project directory to access node_modules
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    shell=True,
                    cwd=self.project_root,
                    encoding='utf-8',
                    timeout=30
                )
                
                # Read compiled output
                if output_file.exists():
                    compiled_content = output_file.read_text(encoding='utf-8')
                    logger.info("SWC compilation successful")
                    return compiled_content
                else:
                    raise RuntimeError("SWC compilation did not produce output file")
                    
            except subprocess.CalledProcessError as e:
                error_msg = f"SWC compilation failed.\nCommand: {' '.join(cmd)}\nStdout: {e.stdout}\nStderr: {e.stderr}"
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
            except subprocess.TimeoutExpired:
                raise RuntimeError("SWC compilation timed out")
    
    def compile_for_ssr(self, files: List[str]) -> str:
        """Compile files specifically for server-side rendering"""
        # For SSR, we need to ensure React imports are available
        compiled_js = self.compile_files(files)
        
        # Add React import if not present (SWC automatic runtime might not include it for SSR)
        if "import React from" not in compiled_js and "React.createElement" in compiled_js:
            compiled_js = "import React from 'react';\n" + compiled_js
        
        return compiled_js
    
    def compile_for_hydration(self, files: List[str]) -> str:
        """Compile files for client-side hydration"""
        return self.compile_files(files)
