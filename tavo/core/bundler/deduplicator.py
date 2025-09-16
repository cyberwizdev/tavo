import re
from typing import Dict, Set, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import logging


logger = logging.getLogger(__name__)

@dataclass
class ImportInfo:
    """Represents a parsed import statement"""
    module_path: str
    default_import: Optional[str] = None
    named_imports: Set[str] = field(default_factory=set)
    namespace_import: Optional[str] = None
    side_effect_only: bool = False
    original_statement: str = ""

class ImportDeduplicator:
    """Advanced import deduplication system for bundling"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.import_registry: Dict[str, ImportInfo] = {}
        
        # Comprehensive regex patterns for different import types
        self.import_patterns = {
            # import defaultExport from "module"
            'default_only': re.compile(
                r'^\s*import\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s+from\s+["\']([^"\']+)["\']\s*;?\s*$',
                re.MULTILINE
            ),
            
            # import { named1, named2 } from "module"
            'named_only': re.compile(
                r'^\s*import\s+\{\s*([^}]+)\s*\}\s+from\s+["\']([^"\']+)["\']\s*;?\s*$',
                re.MULTILINE
            ),
            
            # import defaultExport, { named1, named2 } from "module"
            'default_and_named': re.compile(
                r'^\s*import\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*,\s*\{\s*([^}]+)\s*\}\s+from\s+["\']([^"\']+)["\']\s*;?\s*$',
                re.MULTILINE
            ),
            
            # import * as namespace from "module"
            'namespace': re.compile(
                r'^\s*import\s+\*\s+as\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s+from\s+["\']([^"\']+)["\']\s*;?\s*$',
                re.MULTILINE
            ),
            
            # import "module" (side effects only)
            'side_effect': re.compile(
                r'^\s*import\s+["\']([^"\']+)["\']\s*;?\s*$',
                re.MULTILINE
            ),
            
            # import defaultExport, * as namespace from "module"
            'default_and_namespace': re.compile(
                r'^\s*import\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*,\s*\*\s+as\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s+from\s+["\']([^"\']+)["\']\s*;?\s*$',
                re.MULTILINE
            ),
        }
    
    def normalize_module_path(self, module_path: str, current_file: Path) -> str:
        """Normalize module paths to handle aliases and relative imports"""
        # Handle @ aliases
        if module_path.startswith('@/'):
            return str(self.project_root / module_path[2:])
        
        # Handle relative imports
        if module_path.startswith('./') or module_path.startswith('../'):
            resolved = (current_file.parent / module_path).resolve()
            return str(resolved)
        
        # Handle absolute project paths
        if module_path.startswith('app/') or module_path.startswith('components/'):
            return str(self.project_root / module_path)
        
        # Return as-is for node_modules and other external imports
        return module_path
    
    def parse_named_imports(self, named_string: str) -> Set[str]:
        """Parse named imports string and handle aliases"""
        named_imports = set()
        
        # Split by comma and clean up
        parts = [part.strip() for part in named_string.split(',')]
        
        for part in parts:
            if not part:
                continue
                
            # Handle import aliases: import { originalName as aliasName }
            if ' as ' in part:
                original, alias = part.split(' as ', 1)
                # We store the original name for deduplication purposes
                named_imports.add(original.strip())
            else:
                named_imports.add(part.strip())
        
        return named_imports
    
    def parse_import_statement(self, statement: str, current_file: Path) -> Optional[ImportInfo]:
        """Parse a single import statement into ImportInfo"""
        statement = statement.strip()
        
        if not statement or not statement.startswith('import'):
            return None
        
        # Try each pattern in order of specificity
        
        # Pattern 1: default and named - import default, { named } from "module"
        match = self.import_patterns['default_and_named'].match(statement)
        if match:
            default_import = match.group(1)
            named_string = match.group(2)
            module_path = self.normalize_module_path(match.group(3), current_file)
            
            return ImportInfo(
                module_path=module_path,
                default_import=default_import,
                named_imports=self.parse_named_imports(named_string),
                original_statement=statement
            )
        
        # Pattern 2: default and namespace - import default, * as namespace from "module"
        match = self.import_patterns['default_and_namespace'].match(statement)
        if match:
            default_import = match.group(1)
            namespace = match.group(2)
            module_path = self.normalize_module_path(match.group(3), current_file)
            
            return ImportInfo(
                module_path=module_path,
                default_import=default_import,
                namespace_import=namespace,
                original_statement=statement
            )
        
        # Pattern 3: named only - import { named1, named2 } from "module"
        match = self.import_patterns['named_only'].match(statement)
        if match:
            named_string = match.group(1)
            module_path = self.normalize_module_path(match.group(2), current_file)
            
            return ImportInfo(
                module_path=module_path,
                named_imports=self.parse_named_imports(named_string),
                original_statement=statement
            )
        
        # Pattern 4: default only - import default from "module"
        match = self.import_patterns['default_only'].match(statement)
        if match:
            default_import = match.group(1)
            module_path = self.normalize_module_path(match.group(2), current_file)
            
            return ImportInfo(
                module_path=module_path,
                default_import=default_import,
                original_statement=statement
            )
        
        # Pattern 5: namespace - import * as namespace from "module"
        match = self.import_patterns['namespace'].match(statement)
        if match:
            namespace = match.group(1)
            module_path = self.normalize_module_path(match.group(2), current_file)
            
            return ImportInfo(
                module_path=module_path,
                namespace_import=namespace,
                original_statement=statement
            )
        
        # Pattern 6: side effect - import "module"
        match = self.import_patterns['side_effect'].match(statement)
        if match:
            module_path = self.normalize_module_path(match.group(1), current_file)
            
            return ImportInfo(
                module_path=module_path,
                side_effect_only=True,
                original_statement=statement
            )
        
        return None
    
    def merge_import_info(self, existing: ImportInfo, new: ImportInfo) -> ImportInfo:
        """Merge two ImportInfo objects for the same module"""
        # Keep the first default import encountered
        default_import = existing.default_import or new.default_import
        
        # Keep the first namespace import encountered
        namespace_import = existing.namespace_import or new.namespace_import
        
        # Merge named imports (union of both sets)
        named_imports = existing.named_imports.union(new.named_imports)
        
        # Side effect imports are additive
        side_effect_only = existing.side_effect_only or new.side_effect_only
        
        return ImportInfo(
            module_path=existing.module_path,
            default_import=default_import,
            named_imports=named_imports,
            namespace_import=namespace_import,
            side_effect_only=side_effect_only,
            original_statement=existing.original_statement  # Keep the first one
        )
    
    def add_imports_from_content(self, content: str, current_file: Path):
        """Extract and deduplicate imports from file content"""
        lines = content.split('\n')
        
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith('import'):
                continue
            
            import_info = self.parse_import_statement(stripped, current_file)
            if not import_info:
                continue
            
            module_path = import_info.module_path
            
            if module_path in self.import_registry:
                # Merge with existing import
                self.import_registry[module_path] = self.merge_import_info(
                    self.import_registry[module_path], 
                    import_info
                )
            else:
                # Add new import
                self.import_registry[module_path] = import_info
    
    def generate_deduplicated_imports(self) -> List[str]:
        """Generate the final deduplicated import statements"""
        import_statements = []
        
        # Sort by module path for consistent output
        for module_path in sorted(self.import_registry.keys()):
            # 🚫 Skip react imports completely
            if module_path == "react" or module_path.endswith("/react"):
                continue

            import_info = self.import_registry[module_path]
            statement_parts = []
            
            # Handle side-effect only imports
            if (import_info.side_effect_only 
                and not import_info.default_import 
                and not import_info.named_imports 
                and not import_info.namespace_import):
                import_statements.append(f'import "{module_path}";')
                continue
            
            # Build import statement components
            imports = []
            
            if import_info.default_import:
                imports.append(import_info.default_import)
            
            if import_info.namespace_import:
                if imports:
                    imports.append(f"* as {import_info.namespace_import}")
                else:
                    imports.append(f"* as {import_info.namespace_import}")
            
            if import_info.named_imports:
                named_list = sorted(list(import_info.named_imports))
                named_str = "{ " + ", ".join(named_list) + " }"
                imports.append(named_str)
            
            if imports:
                import_part = ", ".join(imports)
                import_statements.append(f'import {import_part} from "{module_path}";')
        
        return import_statements

    
    def remove_imports_from_content(self, content: str) -> str:
        """Remove all import statements from content"""
        lines = content.split('\n')
        clean_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Skip import statements
            if stripped.startswith('import '):
                continue
            
            clean_lines.append(line)
        
        return '\n'.join(clean_lines)
    
    def reset(self):
        """Reset the import registry for processing new files"""
        self.import_registry.clear()
