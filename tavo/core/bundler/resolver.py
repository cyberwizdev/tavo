"""
Import Resolver

Handles resolution of relative imports, @/ aliases, and bundling multiple files
into a single compilation unit for SWC with proper layout composition and
advanced import deduplication.
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field

try:
    import esprima
    HAS_ESPRIMA = True
except ImportError:
    HAS_ESPRIMA = False

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


class ImportResolver:
    """Resolves and bundles imports for SWC compilation"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.app_dir = project_root / "app"
        self.components_dir = project_root / "components"
        self.resolved_cache: Dict[str, Dict] = {}
        self.dependency_graph: Dict[str, List[str]] = {}
        self.deduplicator = ImportDeduplicator(project_root)
    
    def resolve_file_path(self, import_path: str, current_file: Path) -> Optional[Path]:
        """Resolve import path to actual file path"""
        if import_path.startswith('./') or import_path.startswith('../'):
            resolved = (current_file.parent / import_path).resolve()
        elif import_path.startswith('@/'):
            resolved = self.project_root / import_path[2:]
        elif import_path.startswith('app/'):
            resolved = self.project_root / import_path
        elif import_path.startswith('components/'):
            resolved = self.project_root / import_path
        else:
            return None
        
        extensions = ['.tsx', '.ts', '.jsx', '.js']
        
        if resolved.suffix in extensions and resolved.exists():
            return resolved
        
        for ext in extensions:
            candidate = resolved.with_suffix(ext)
            if candidate.exists():
                return candidate
        
        if resolved.is_dir():
            for ext in extensions:
                index_file = resolved / f"index{ext}"
                if index_file.exists():
                    return index_file
        
        return None
    
    def parse_file(self, file_path: Path) -> Dict:
        """Parse a single file and extract its components"""
        file_str = str(file_path)
        
        if file_str in self.resolved_cache:
            return self.resolved_cache[file_str]
        
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return {'imports': [], 'exports': [], 'content': '', 'local_deps': [], 'component_info': {}}
        
        imports, exports, main_content = self._extract_statements(content)
        local_deps = self._find_local_dependencies(imports, file_path)
        component_info = self._analyze_component(main_content, file_path)
        
        result = {
            'imports': imports,
            'exports': exports, 
            'content': main_content,
            'local_deps': local_deps,
            'file_path': file_str,
            'component_info': component_info
        }
        
        self.resolved_cache[file_str] = result
        self.dependency_graph[file_str] = local_deps
        
        return result
    
    def _analyze_component(self, content: str, file_path: Path) -> Dict:
        """Analyze component type and properties"""
        file_name = file_path.name
        component_info = {
            'is_layout': 'layout.' in file_name,
            'is_page': 'page.' in file_name,
            'component_name': self._extract_component_name(content),
            'has_children_prop': 'children' in content and ('ReactNode' in content or 'React.ReactNode' in content)
        }
        return component_info
    
    def _extract_component_name(self, content: str) -> Optional[str]:
        """Extract the main component name from file content"""
        # Try to find export default function Name
        match = re.search(r'export\s+default\s+function\s+(\w+)', content)
        if match:
            return match.group(1)
        
        # Try to find const Name = () => or const Name: FC
        match = re.search(r'const\s+(\w+)(?:\s*:\s*\w+)?\s*=\s*\(', content)
        if match:
            return match.group(1)
        
        # Try to find export default Name
        match = re.search(r'export\s+default\s+(\w+)', content)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_statements(self, content: str) -> Tuple[List[str], List[str], str]:
        """Extract import/export statements from content using AST parsing"""
        if HAS_ESPRIMA:
            return self._extract_statements_ast(content)
        else:
            return self._extract_statements_fallback(content)
    
    def _extract_statements_ast(self, content: str) -> Tuple[List[str], List[str], str]:
        """Extract statements using esprima AST parsing with JSX support"""
        try:
            # Try parsing with JSX support first
            ast = esprima.parseModule(content, options={
                'loc': True, 
                'range': True,
                'jsx': True,
                'tolerant': True
            })
            
            imports = []
            exports = []
            
            lines = content.split('\n')
            processed_ranges = set()
            
            for node in ast.body:
                start_line = node.loc.start.line - 1  # esprima uses 1-based line numbers
                end_line = node.loc.end.line - 1
                
                # Extract the original source for this node
                if node.type == 'ImportDeclaration':
                    import_lines = lines[start_line:end_line + 1]
                    imports.append('\n'.join(import_lines).strip())
                    processed_ranges.update(range(start_line, end_line + 1))
                elif node.type == 'ExportNamedDeclaration' or node.type == 'ExportDefaultDeclaration':
                    export_lines = lines[start_line:end_line + 1]
                    exports.append('\n'.join(export_lines).strip())
                    processed_ranges.update(range(start_line, end_line + 1))
            
            # Collect remaining lines that weren't imports or exports
            remaining_lines = []
            for i, line in enumerate(lines):
                if i not in processed_ranges:
                    remaining_lines.append(line)
            
            return imports, exports, '\n'.join(remaining_lines)
            
        except Exception as e:
            logger.warning(f"AST parsing failed, falling back to regex: {e}")
            return self._extract_statements_fallback(content)
    
    def _extract_statements_fallback(self, content: str) -> Tuple[List[str], List[str], str]:
        """Fallback method using improved pattern matching for TypeScript/JSX"""
        lines = content.split('\n')
        imports = []
        exports = []
        main_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Handle imports
            if stripped.startswith('import ') and not line.startswith(' ') and not line.startswith('\t'):
                imports.append(stripped)
            # Handle export function declarations (multi-line)
            elif (stripped.startswith('export default function') or stripped.startswith('export async function') or stripped.startswith('export function')) and not line.startswith(' ') and not line.startswith('\t'):
                # Collect the entire function declaration
                function_lines = [line]
                brace_count = line.count('{') - line.count('}')
                i += 1
                
                # Continue collecting lines until we close all braces
                while i < len(lines) and brace_count > 0:
                    function_lines.append(lines[i])
                    brace_count += lines[i].count('{') - lines[i].count('}')
                    i += 1
                
                exports.append('\n'.join(function_lines))
                continue  # Skip the normal increment since we already advanced i
            # Handle other export statements
            elif stripped.startswith('export ') and not line.startswith(' ') and not line.startswith('\t'):
                exports.append(stripped)
            else:
                main_lines.append(line)
            
            i += 1
        
        return imports, exports, '\n'.join(main_lines)
    
    def _is_complete_import(self, line: str) -> bool:
        """Check if import statement is complete"""
        return (line.endswith(';') or line.endswith('"') or line.endswith("'")) and 'from' in line
    
    def _find_local_dependencies(self, imports: List[str], current_file: Path) -> List[str]:
        """Find local file dependencies from import statements"""
        local_deps = []
        
        for import_stmt in imports:
            import_path = self._extract_import_path(import_stmt)
            if import_path:
                resolved_path = self.resolve_file_path(import_path, current_file)
                if resolved_path and resolved_path.exists():
                    local_deps.append(str(resolved_path))
        
        return local_deps
    
    def _extract_import_path(self, import_stmt: str) -> Optional[str]:
        """Extract the path from an import statement"""
        patterns = [
            r'from\s+["\']([^"\']+)["\']',
            r'import\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, import_stmt)
            if match:
                return match.group(1)
        
        return None
    
    def build_dependency_order(self, entry_files: List[str]) -> List[str]:
        """Build topological order of dependencies"""
        visited = set()
        visiting = set()
        result = []
        
        def visit(file_path: str):
            if file_path in visiting:
                logger.warning(f"Circular dependency detected involving {file_path}")
                return
            
            if file_path in visited:
                return
            
            visiting.add(file_path)
            
            if file_path in self.dependency_graph:
                for dep in self.dependency_graph[file_path]:
                    visit(dep)
            
            visiting.remove(file_path)
            visited.add(file_path)
            result.append(file_path)
        
        for entry_file in entry_files:
            file_info = self.parse_file(Path(entry_file))
            for dep in file_info['local_deps']:
                visit(dep)
        
        for entry_file in entry_files:
            visit(entry_file)
        
        return result
    
    def _create_layout_composition(self, layouts: List[str], page_file: Optional[str]) -> str:
        """Create proper layout composition with page as children"""
        if not layouts and not page_file:
            return ""
        
        composition_parts = []
        
        # Import all components
        component_imports = []
        component_map = {}
        
        # Process layouts
        for i, layout_file in enumerate(layouts):
            layout_info = self.parse_file(Path(layout_file))
            component_name = layout_info['component_info']['component_name']
            if not component_name:
                component_name = f"Layout{i}"
            
            # Clean up component content - remove export statements
            clean_content = self._clean_component_content(layout_info['content'])
            composition_parts.append(f"// Layout from {Path(layout_file).relative_to(self.project_root)}")
            composition_parts.append(clean_content)
            component_map[f"layout_{i}"] = component_name
        
        # Process page
        page_component_name = None
        if page_file:
            page_info = self.parse_file(Path(page_file))
            page_component_name = page_info['component_info']['component_name']
            if not page_component_name:
                page_component_name = "Page"
            
            clean_content = self._clean_component_content(page_info['content'])
            composition_parts.append(f"// Page from {Path(page_file).relative_to(self.project_root)}")
            composition_parts.append(clean_content)
            component_map['page'] = page_component_name
        
        # Create the composed component
        if layouts:
            composition_parts.append("\n// Composed App Component")
            composition_parts.append("function App() {")
            
            # Build nested layout structure
            nested_jsx = page_component_name if page_component_name else "null"
            
            # Wrap from innermost to outermost layout
            for i in reversed(range(len(layouts))):
                layout_name = component_map[f"layout_{i}"]
                nested_jsx = f"React.createElement({layout_name}, null, {nested_jsx})"
            
            composition_parts.append(f"  return {nested_jsx};")
            composition_parts.append("}")
            composition_parts.append("")
            composition_parts.append("export default App;")
        elif page_component_name:
            composition_parts.append(f"\nexport default {page_component_name};")
        
        return '\n'.join(composition_parts)
    
    def create_single_file_for_swc(self, files: List[str], temp_dir: Path) -> Path:
        """Create a single bundled file for SWC compilation with import deduplication"""
        bundled_content = self.bundle_files(files)
        bundled_content = self._apply_react_transforms(bundled_content)
        
        temp_file = temp_dir / "bundled_components.tsx"
        temp_file.write_text(bundled_content, encoding='utf-8')
        
        logger.info(f"Created bundled file: {temp_file}")
        logger.debug(f"Bundled content preview:\n{bundled_content[:500]}...")
        
        return temp_file
    
    def _apply_react_transforms(self, content: str) -> str:
        """Apply React-specific transformations"""
        react_hooks = [
            'useState', 'useEffect', 'useContext', 'useReducer', 
            'useCallback', 'useMemo', 'useRef', 'useLayoutEffect',
            'useImperativeHandle', 'useDebugValue'
        ]
        
        react_components = ['Fragment', 'Component', 'PureComponent']
        react_functions = ['createElement', 'createContext', 'forwardRef', 'memo', 'lazy']
        
        all_react_items = react_hooks + react_components + react_functions
        
        for item in all_react_items:
            pattern = rf'\b(?<!React\.){item}\b(?=\s*[\(\.])'
            replacement = f'React.{item}'
            content = re.sub(pattern, replacement, content)
        
        return content

    def _clean_component_content(self, content: str) -> str:
        """Remove export statements and imports from component content"""
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Skip import statements (they're handled at the bundle level)
            if stripped.startswith('import '):
                continue
            # Convert export default function to regular function
            elif stripped.startswith('export default function'):
                cleaned_lines.append(line.replace('export default ', ''))
            # Skip standalone export default lines (like "export default ComponentName;")
            elif stripped.startswith('export default') and (stripped.endswith(';') or len(stripped.split()) == 3):
                continue
            # Convert other exports to regular declarations
            elif stripped.startswith('export '):
                cleaned_lines.append(line.replace('export ', ''))
            else:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def bundle_files(self, files: List[str]) -> str:
        """Bundle files with proper layout composition and import deduplication"""
        # Reset deduplicator for new bundling operation
        self.deduplicator.reset()
        
        # Separate layouts from pages
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
        
        # Sort layouts by depth (root layout first)
        layouts.sort(key=lambda x: len(Path(x).relative_to(self.app_dir).parts))
        
        # Process all files for import deduplication
        all_files = other_files + layouts + ([page_file] if page_file else [])
        
        # Extract imports from all files
        for file_path in all_files:
            current_file = Path(file_path)
            try:
                content = current_file.read_text(encoding='utf-8')
                self.deduplicator.add_imports_from_content(content, current_file)
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                continue
        
        output_parts = []
        
        # Add deduplicated imports
        deduplicated_imports = self.deduplicator.generate_deduplicated_imports()
        if deduplicated_imports:
            output_parts.extend(deduplicated_imports)
            output_parts.append('')
        
        # Handle other dependencies first
        if other_files:
            ordered_others = self.build_dependency_order(other_files)
            for file_path in ordered_others:
                file_info = self.parse_file(Path(file_path))
                if file_info['content'].strip():
                    relative_path = Path(file_path).relative_to(self.project_root)
                    clean_content = self.deduplicator.remove_imports_from_content(file_info['content'])
                    clean_content = self._clean_component_content(clean_content)
                    output_parts.append(f"// File: {relative_path}")
                    output_parts.append(clean_content)
                    output_parts.append("")
        
        # Create layout composition (with imports already removed by deduplicator)
        composition = self._create_layout_composition_clean(layouts, page_file)
        if composition:
            output_parts.append(composition)
        
        return '\n'.join(output_parts)
    
    def _create_layout_composition_clean(self, layouts: List[str], page_file: Optional[str]) -> str:
        """Create layout composition with clean content (imports already handled)"""
        if not layouts and not page_file:
            return ""
        
        composition_parts = []
        component_map = {}
        
        # Process layouts
        for i, layout_file in enumerate(layouts):
            layout_info = self.parse_file(Path(layout_file))
            component_name = layout_info['component_info']['component_name']
            if not component_name:
                component_name = f"Layout{i}"
            
            # Get clean content without imports
            clean_content = self.deduplicator.remove_imports_from_content(layout_info['content'])
            clean_content = self._clean_component_content(clean_content)
            
            composition_parts.append(f"// Layout from {Path(layout_file).relative_to(self.project_root)}")
            composition_parts.append(clean_content)
            component_map[f"layout_{i}"] = component_name
        
        # Process page
        page_component_name = None
        if page_file:
            page_info = self.parse_file(Path(page_file))
            page_component_name = page_info['component_info']['component_name']
            if not page_component_name:
                page_component_name = "Page"
            
            clean_content = self.deduplicator.remove_imports_from_content(page_info['content'])
            clean_content = self._clean_component_content(clean_content)
            
            composition_parts.append(f"// Page from {Path(page_file).relative_to(self.project_root)}")
            composition_parts.append(clean_content)
            component_map['page'] = page_component_name
        
        # Create the composed component
        if layouts:
            composition_parts.append("\n// Composed App Component")
            composition_parts.append("function App() {")
            
            # Build nested layout structure
            nested_jsx = page_component_name if page_component_name else "null"
            
            # Wrap from innermost to outermost layout
            for i in reversed(range(len(layouts))):
                layout_name = component_map[f"layout_{i}"]