"""
Import Resolver

Handles resolution of relative imports, @/ aliases, and bundling multiple files
into a single compilation unit for SWC.
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional

logger = logging.getLogger(__name__)


class ImportResolver:
    """Resolves and bundles imports for SWC compilation"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.app_dir = project_root / "app"
        self.resolved_files: Dict[str, str] = {}
        self.processed_files: Set[str] = set()
    
    def resolve_file_path(self, import_path: str, current_file: Path) -> Optional[Path]:
        """Resolve import path to actual file path"""
        # Handle relative imports
        if import_path.startswith('./') or import_path.startswith('../'):
            resolved = (current_file.parent / import_path).resolve()
        # Handle @/ alias (project root)
        elif import_path.startswith('@/'):
            resolved = self.project_root / import_path[2:]
        # Handle app/ directory imports
        elif import_path.startswith('app/'):
            resolved = self.project_root / import_path
        else:
            # External imports (node_modules) - let SWC handle these
            return None
        
        # Try different extensions
        extensions = ['.tsx', '.ts', '.jsx', '.js']
        
        # If path already has extension, try it first
        if resolved.suffix in extensions and resolved.exists():
            return resolved
        
        # Try adding extensions
        for ext in extensions:
            candidate = resolved.with_suffix(ext)
            if candidate.exists():
                return candidate
        
        # Try index files
        if resolved.is_dir():
            for ext in extensions:
                index_file = resolved / f"index{ext}"
                if index_file.exists():
                    return index_file
        
        return None
    
    def extract_imports(self, content: str) -> List[str]:
        """Extract all import statements from file content"""
        imports = []
        
        # Match import statements
        import_patterns = [
            r'import\s+[^"\']*?from\s+["\']([^"\']+)["\']',  # import ... from "path"
            r'import\s+["\']([^"\']+)["\']',  # import "path"
            r'from\s+["\']([^"\']+)["\']',  # from "path"
        ]
        
        for pattern in import_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            imports.extend(matches)
        
        return imports
    
    def process_file(self, file_path: Path, visited: Optional[Set[str]] = None) -> str:
        """Process a file and resolve all its local imports recursively"""
        if visited is None:
            visited = set()
        
        file_str = str(file_path)
        if file_str in visited:
            # Circular import detected, return empty to avoid infinite loop
            logger.warning(f"Circular import detected for {file_path}")
            return ""
        
        if file_str in self.resolved_files:
            return self.resolved_files[file_str]
        
        visited.add(file_str)
        
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return ""
        
        # Extract imports
        imports = self.extract_imports(content)
        resolved_content = content
        
        # Process each import
        for import_path in imports:
            resolved_path = self.resolve_file_path(import_path, file_path)
            
            if resolved_path and resolved_path.exists():
                # This is a local file, process it recursively
                imported_content = self.process_file(resolved_path, visited.copy())
                
                # Replace the import statement with the actual content
                # This is a simplified approach - in production you'd want more sophisticated bundling
                import_statement_patterns = [
                    rf'import\s+[^"\']*?from\s+["\']({re.escape(import_path)})["\'];?',
                    rf'import\s+["\']({re.escape(import_path)})["\'];?',
                ]
                
                for pattern in import_statement_patterns:
                    resolved_content = re.sub(
                        pattern,
                        f"// Bundled content from {import_path}\n{imported_content}",
                        resolved_content,
                        flags=re.MULTILINE
                    )
        
        self.resolved_files[file_str] = resolved_content
        return resolved_content
    
    def bundle_files(self, files: List[str]) -> str:
        """Bundle multiple files into a single compilation unit"""
        bundled_content = []
        
        for file_path in files:
            path_obj = Path(file_path)
            if not path_obj.exists():
                logger.warning(f"File not found: {file_path}")
                continue
            
            # Process file and resolve imports
            content = self.process_file(path_obj)
            
            # Add file marker comment
            relative_path = path_obj.relative_to(self.project_root)
            bundled_content.append(f"// === File: {relative_path} ===")
            bundled_content.append(content)
            bundled_content.append("")  # Empty line separator
        
        return "\n".join(bundled_content)
    
    def create_single_file_for_swc(self, files: List[str], temp_dir: Path) -> Path:
        """Create a single bundled file for SWC compilation"""
        bundled_content = self.bundle_files(files)
        
        # Create temporary file
        temp_file = temp_dir / "bundled_components.tsx"
        temp_file.write_text(bundled_content, encoding='utf-8')
        
        return temp_file
