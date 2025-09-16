import re
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass, field
from pathlib import Path

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
            import_info = self.import_registry[module_path]
            statement_parts = []
            
            # Handle side-effect only imports
            if import_info.side_effect_only and not import_info.default_import and not import_info.named_imports and not import_info.namespace_import:
                import_statements.append(f'import "{module_path}";')
                continue
            
            # Build import statement components
            imports = []
            
            # Add default import
            if import_info.default_import:
                imports.append(import_info.default_import)
            
            # Add namespace import
            if import_info.namespace_import:
                if imports:
                    imports.append(f"* as {import_info.namespace_import}")
                else:
                    imports.append(f"* as {import_info.namespace_import}")
            
            # Add named imports
            if import_info.named_imports:
                named_list = sorted(list(import_info.named_imports))
                named_str = "{ " + ", ".join(named_list) + " }"
                imports.append(named_str)
            
            # Construct final import statement
            if imports:
                import_part = ", ".join(imports)
                import_statements.append(f'import {import_part} from "{module_path}";')
        
        return import_statements
    
    def process_files(self, files: List[str]) -> Tuple[List[str], List[str]]:
        """Process multiple files and return deduplicated imports and clean content"""
        clean_contents = []
        
        for file_path in files:
            current_file = Path(file_path)
            try:
                content = current_file.read_text(encoding='utf-8')
            except Exception:
                continue
            
            # Extract imports
            self.add_imports_from_content(content, current_file)
            
            # Remove import statements from content
            clean_content = self.remove_imports_from_content(content)
            if clean_content.strip():
                clean_contents.append(f"// File: {current_file.name}")
                clean_contents.append(clean_content)
                clean_contents.append("")
        
        # Generate deduplicated imports
        deduplicated_imports = self.generate_deduplicated_imports()
        
        return deduplicated_imports, clean_contents
    
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
    
    def create_bundled_content(self, files: List[str]) -> str:
        """Create final bundled content with deduplicated imports"""
        deduplicated_imports, clean_contents = self.process_files(files)
        
        # Combine everything
        final_content = []
        
        # Add deduplicated imports
        if deduplicated_imports:
            final_content.extend(deduplicated_imports)
            final_content.append("")  # Empty line after imports
        
        # Add clean content
        final_content.extend(clean_contents)
        
        return '\n'.join(final_content)
    
    def reset(self):
        """Reset the import registry for processing new files"""
        self.import_registry.clear()

# Usage example function to integrate with existing ImportResolver
def integrate_with_import_resolver(resolver_instance):
    """Integration function to use with existing ImportResolver"""
    
    def enhanced_bundle_files(self, files: List[str]) -> str:
        """Enhanced bundle_files method with import deduplication"""
        deduplicator = ImportDeduplicator(self.project_root)
        
        # Separate layouts from pages (keep existing logic)
        layouts = []
        page_file = None
        other_files = []
        
        for file_path in files:
            file_info = self.parse_file(Path(file_path))
            if file_info['component_info']['is_layout']:
                layouts.append(file_path)
            elif file_info['component_info']['is_page']:
                page_file = file_path
            else:
                other_files.append(file_path)
        
        # Sort layouts by depth
        layouts.sort(key=lambda x: len(Path(x).relative_to(self.app_dir).parts))
        
        # Process all files for import deduplication
        all_files = other_files + layouts + ([page_file] if page_file else [])
        bundled_content = deduplicator.create_bundled_content(all_files)
        
        # Apply existing layout composition logic if needed
        if layouts or page_file:
            # Extract just the clean content without imports
            _, clean_contents = deduplicator.process_files(all_files)
            composition = self._create_layout_composition(layouts, page_file)
            
            if composition:
                # Get the deduplicated imports
                deduplicated_imports = deduplicator.generate_deduplicated_imports()
                
                # Combine imports + composition
                final_parts = deduplicated_imports + [""] + [composition]
                bundled_content = '\n'.join(final_parts)
        
        return bundled_content
    
    # Replace the original method
    resolver_instance.bundle_files = enhanced_bundle_files.__get__(resolver_instance, type(resolver_instance))
    return resolver_instance