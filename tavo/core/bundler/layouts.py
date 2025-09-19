"""
Layout composition for nested React components with robust parsing and composition
"""

import re
import logging
import ast
from pathlib import Path
from typing import List, Optional, Dict, Set, Tuple
from dataclasses import dataclass

from .utils import read_file

logger = logging.getLogger(__name__)


@dataclass
class ComponentInfo:
    """Enhanced information about a React component"""
    name: str
    raw_content: str
    extracted_imports: List[str]
    extracted_top_level_code: List[str]
    component_function_name: str
    component_function_body: str
    default_export: bool
    named_exports: List[str]
    props_interface: Optional[str] = None
    has_hooks: bool = False
    has_server_side_props: bool = False
    has_hydration_function: bool = False


class LayoutComposer:
    """Composes nested layouts into single virtual components with robust parsing"""
    
    def __init__(self):
        self.component_counter = 0
        self._reserved_names = {'React', 'Component', 'Fragment', 'useState', 'useEffect'}
    
    def compose_layouts(self, layout_files: List[Path], page_file: Path) -> str:
        """
        Compose layout files and page into a single TSX component
        
        Args:
            layout_files: List of layout file paths (outermost to innermost)
            page_file: Page component file path
            
        Returns:
            Composed TSX content
        """
        try:
            # Read all file contents
            layout_contents = []
            for layout_file in layout_files:
                content = read_file(layout_file)
                layout_contents.append(content)
            
            page_content = read_file(page_file)
            
            return self.compose_layouts_clean(layout_contents, page_content)
            
        except Exception as e:
            logger.error(f"Failed to compose layouts: {e}")
            raise
    
    def compose_layouts_clean(self, layout_contents: List[str], page_content: str) -> str:
        """
        Compose layout contents and page content into single TSX
        
        Args:
            layout_contents: List of layout file contents (outermost to innermost)
            page_content: Page component content
            
        Returns:
            Composed TSX content as string
        """
        # Parse all components with enhanced parsing
        components = []
        
        # Process layouts
        for i, content in enumerate(layout_contents):
            comp_info = self._parse_component_enhanced(content, f"Layout{i}")
            components.append(comp_info)
        
        # Process page
        page_info = self._parse_component_enhanced(page_content, "Page")
        components.append(page_info)
        
        # Generate composed component
        composed_tsx = self._generate_composed_component_enhanced(components)
        
        return composed_tsx
    
    def _parse_component_enhanced(self, content: str, fallback_name: str) -> ComponentInfo:
        """Enhanced parsing of React component from content"""
        
        # Extract imports
        imports = self._extract_imports_enhanced(content)
        
        # Extract top-level code (interfaces, types, constants, functions)
        top_level_code = self._extract_top_level_code(content)
        
        # Find main component function
        component_name, component_body = self._extract_main_component(content, fallback_name)
        
        # Check for various features
        has_hooks = self._has_react_hooks(content)
        has_server_side_props = 'getServerSideProps' in content
        has_hydration_function = any(func_name in content for func_name in ['hydrate', 'hydrateRoot'])
        
        # Extract exports
        default_export = self._has_default_export(content)
        named_exports = self._extract_named_exports(content)
        
        # Extract props interface
        props_interface = self._extract_props_interface(content, component_name)
        
        return ComponentInfo(
            name=component_name,
            raw_content=content,
            extracted_imports=imports,
            extracted_top_level_code=top_level_code,
            component_function_name=component_name,
            component_function_body=component_body,
            default_export=default_export,
            named_exports=named_exports,
            props_interface=props_interface,
            has_hooks=has_hooks,
            has_server_side_props=has_server_side_props,
            has_hydration_function=has_hydration_function
        )
    
    def _extract_imports_enhanced(self, content: str) -> List[str]:
        """Extract all import statements with better parsing"""
        imports = []
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Handle single-line imports
            if line.startswith('import ') and (';' in line or line.endswith("'") or line.endswith('"')):
                imports.append(line.rstrip(';'))
                i += 1
                continue
            
            # Handle multi-line imports
            if line.startswith('import '):
                import_lines = [line]
                i += 1
                
                # Continue collecting lines until we find the end
                while i < len(lines):
                    current_line = lines[i].strip()
                    import_lines.append(current_line)
                    
                    if (';' in current_line or 
                        current_line.endswith("'") or 
                        current_line.endswith('"') or
                        'from' in current_line):
                        break
                    i += 1
                
                # Join and clean the multi-line import
                full_import = ' '.join(import_lines).strip().rstrip(';')
                imports.append(full_import)
                i += 1
                continue
            
            i += 1
        
        return imports
    
    def _extract_top_level_code(self, content: str) -> List[str]:
        """Extract top-level code blocks (interfaces, types, constants, functions)"""
        top_level_blocks = []
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('//') or line.startswith('/*'):
                i += 1
                continue
            
            # Skip imports (handled separately)
            if line.startswith('import '):
                # Skip to end of import
                while i < len(lines) and not (';' in lines[i] or lines[i].strip().endswith('"') or lines[i].strip().endswith("'")):
                    i += 1
                i += 1
                continue
            
            # Skip export default (handled separately)
            if line.startswith('export default'):
                i += 1
                continue
            
            # Capture interfaces and types
            if line.startswith('interface ') or line.startswith('type '):
                block_lines = []
                brace_count = 0
                
                while i < len(lines):
                    current_line = lines[i]
                    block_lines.append(current_line)
                    
                    # Count braces to find end of block
                    brace_count += current_line.count('{') - current_line.count('}')
                    
                    i += 1
                    if brace_count == 0 and ('{' in current_line or ';' in current_line):
                        break
                
                top_level_blocks.append('\n'.join(block_lines))
                continue
            
            # Capture function declarations (but not the main component)
            if (line.startswith('function ') or 
                line.startswith('const ') or 
                line.startswith('let ') or 
                line.startswith('var ') or
                line.startswith('export function ') or
                line.startswith('export const ') or
                line.startswith('export async function ')):
                
                # Check if this is the main component function
                if self._is_main_component_line(line):
                    i += 1
                    continue
                
                block_lines = []
                brace_count = 0
                paren_count = 0
                in_function = False
                
                while i < len(lines):
                    current_line = lines[i]
                    block_lines.append(current_line)
                    
                    # Track braces and parentheses
                    brace_count += current_line.count('{') - current_line.count('}')
                    paren_count += current_line.count('(') - current_line.count(')')
                    
                    if '{' in current_line:
                        in_function = True
                    
                    i += 1
                    
                    # End conditions
                    if in_function and brace_count == 0:
                        break
                    elif not in_function and (';' in current_line or current_line.strip().endswith(',')):
                        break
                
                top_level_blocks.append('\n'.join(block_lines))
                continue
            
            i += 1
        
        return top_level_blocks
    
    def _extract_main_component(self, content: str, fallback_name: str) -> Tuple[str, str]:
        """Extract the main React component function"""
        
        # Try to find export default function
        export_default_match = re.search(
            r'export\s+default\s+function\s+(\w+)\s*\([^)]*\)\s*\{',
            content,
            re.MULTILINE
        )
        
        if export_default_match:
            component_name = export_default_match.group(1)
            # Extract the full function body
            start_pos = export_default_match.start()
            function_body = self._extract_function_body(content, start_pos)
            return component_name, function_body
        
        # Try to find function declaration followed by export default
        function_matches = re.finditer(
            r'function\s+(\w+)\s*\([^)]*\)\s*\{',
            content,
            re.MULTILINE
        )
        
        for match in function_matches:
            func_name = match.group(1)
            if f'export default {func_name}' in content:
                start_pos = match.start()
                function_body = self._extract_function_body(content, start_pos)
                return func_name, function_body
        
        # Try to find const component with arrow function
        const_match = re.search(
            r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*\{',
            content,
            re.MULTILINE
        )
        
        if const_match:
            component_name = const_match.group(1)
            if f'export default {component_name}' in content:
                start_pos = const_match.start()
                function_body = self._extract_function_body(content, start_pos)
                return component_name, function_body
        
        # Fallback: create a simple component wrapper
        logger.warning(f"Could not find main component in content, using fallback: {fallback_name}")
        return fallback_name, f"function {fallback_name}() {{ return null; }}"
    
    def _extract_function_body(self, content: str, start_pos: int) -> str:
        """Extract complete function body from starting position"""
        lines = content[start_pos:].split('\n')
        function_lines = []
        brace_count = 0
        started = False
        
        for line in lines:
            function_lines.append(line)
            
            if '{' in line:
                started = True
            
            if started:
                brace_count += line.count('{') - line.count('}')
                
                if brace_count == 0:
                    break
        
        return '\n'.join(function_lines)
    
    def _is_main_component_line(self, line: str) -> bool:
        """Check if a line defines the main component function"""
        # Look for patterns that suggest this is the main component
        main_patterns = [
            r'export\s+default\s+function',
            r'function\s+\w+.*\{\s*return\s*<',
            r'const\s+\w+\s*=\s*\([^)]*\)\s*=>\s*\{'
        ]
        
        for pattern in main_patterns:
            if re.search(pattern, line):
                return True
        
        return False
    
    def _has_react_hooks(self, content: str) -> bool:
        """Check if content uses React hooks"""
        hook_patterns = [
            r'\buseState\b', r'\buseEffect\b', r'\buseContext\b',
            r'\buseReducer\b', r'\buseCallback\b', r'\buseMemo\b',
            r'\buseRef\b', r'\buseLayoutEffect\b'
        ]
        
        for pattern in hook_patterns:
            if re.search(pattern, content):
                return True
        
        return False
    
    def _has_default_export(self, content: str) -> bool:
        """Check if content has default export"""
        return 'export default' in content
    
    def _extract_named_exports(self, content: str) -> List[str]:
        """Extract named exports from content"""
        exports = []
        
        # Look for export { ... }
        export_block_match = re.search(r'export\s*\{\s*([^}]+)\s*\}', content)
        if export_block_match:
            export_list = export_block_match.group(1)
            exports.extend([name.strip() for name in export_list.split(',')])
        
        # Look for export const/function/etc
        export_statements = re.findall(r'export\s+(?:const|function|class)\s+(\w+)', content)
        exports.extend(export_statements)
        
        return [name for name in exports if name]
    
    def _extract_props_interface(self, content: str, component_name: str) -> Optional[str]:
        """Extract props interface for component if present"""
        # Look for interface ComponentNameProps
        interface_pattern = rf'interface\s+{component_name}Props\s*\{{[^}}]*\}}'
        interface_match = re.search(interface_pattern, content, re.DOTALL)
        if interface_match:
            return interface_match.group(0)
        
        # Look for type ComponentNameProps
        type_pattern = rf'type\s+{component_name}Props\s*=\s*\{{[^}}]*\}}'
        type_match = re.search(type_pattern, content, re.DOTALL)
        if type_match:
            return type_match.group(0)
        
        return None
    
    def _generate_composed_component_enhanced(self, components: List[ComponentInfo]) -> str:
        """Generate the final composed component with enhanced logic"""
        lines = []
        
        # Collect all unique imports
        all_imports = set()
        for comp in components:
            all_imports.update(comp.extracted_imports)
        
        # Ensure React import is present
        react_imported = any('from "react"' in imp or "from 'react'" in imp for imp in all_imports)
        if not react_imported:
            lines.append('import React from "react";')
        
        # Add other imports (deduplicated)
        unique_imports = self._deduplicate_imports(list(all_imports))
        lines.extend(unique_imports)
        
        if unique_imports:
            lines.append('')
        
        # Collect all unique top-level code
        all_top_level = []
        seen_interfaces = set()
        seen_functions = set()
        
        for comp in components:
            for code_block in comp.extracted_top_level_code:
                # Deduplicate interfaces and types
                if code_block.strip().startswith(('interface ', 'type ')):
                    interface_name = self._extract_interface_name(code_block)
                    if interface_name and interface_name not in seen_interfaces:
                        seen_interfaces.add(interface_name)
                        all_top_level.append(code_block)
                # Deduplicate functions
                elif code_block.strip().startswith(('function ', 'const ', 'export function')):
                    func_name = self._extract_function_name(code_block)
                    if func_name and func_name not in seen_functions:
                        seen_functions.add(func_name)
                        all_top_level.append(code_block)
                else:
                    all_top_level.append(code_block)
        
        # Add top-level code
        for code_block in all_top_level:
            lines.append(code_block)
            lines.append('')
        
        # Generate individual component functions (without export default)
        component_names = []
        for i, comp in enumerate(components):
            # Generate unique component name
            if i < len(components) - 1:  # Layout
                unique_name = f"Layout{i}Component"
            else:  # Page
                unique_name = f"PageComponent"
            
            component_names.append(unique_name)
            
            # Clean the component function body (remove export default)
            clean_body = self._clean_component_function(comp.component_function_body, comp.component_function_name, unique_name)
            lines.append(clean_body)
            lines.append('')
        
        # Generate the composed component
        lines.append('// Composed route component')
        lines = [line.replace('export default', '') for line in lines]
        lines.append('export default function ComposedRoute(props: any = {}) {')
        
        # Build nested JSX structure
        jsx_structure = self._build_nested_jsx_enhanced(component_names)
        lines.append(f'  return {jsx_structure};')
        
        lines.append('}')
        
        return '\n'.join(lines)
    
    def _deduplicate_imports(self, imports: List[str]) -> List[str]:
        """Deduplicate and clean import statements"""
        # Group by module
        module_imports = {}
        
        for imp in imports:
            # Extract module name
            module_match = re.search(r'from\s+["\']([^"\']+)["\']', imp)
            if not module_match:
                continue
            
            module_name = module_match.group(1)
            
            if module_name not in module_imports:
                module_imports[module_name] = {
                    'default': None,
                    'named': set(),
                    'namespace': None
                }
            
            # Parse import type
            if imp.startswith('import * as'):
                namespace_match = re.search(r'import\s+\*\s+as\s+(\w+)', imp)
                if namespace_match:
                    module_imports[module_name]['namespace'] = namespace_match.group(1)
            elif imp.startswith('import {') or '{ ' in imp:
                # Named imports
                named_match = re.search(r'import\s+\{\s*([^}]+)\s*\}', imp)
                if named_match:
                    named_list = named_match.group(1)
                    names = [name.strip() for name in named_list.split(',')]
                    module_imports[module_name]['named'].update(names)
            elif 'import ' in imp and ' from ' in imp:
                # Default import
                default_match = re.search(r'import\s+(\w+)\s+from', imp)
                if default_match:
                    module_imports[module_name]['default'] = default_match.group(1)
        
        # Rebuild imports
        result = []
        for module, imports_info in sorted(module_imports.items()):
            import_parts = []
            
            if imports_info['default']:
                import_parts.append(imports_info['default'])
            
            if imports_info['named']:
                named_str = ', '.join(sorted(imports_info['named']))
                import_parts.append(f'{{ {named_str} }}')
            
            if imports_info['namespace']:
                import_parts.append(f"* as {imports_info['namespace']}")
            
            if import_parts:
                import_statement = f"import {', '.join(import_parts)} from \"{module}\";"
                result.append(import_statement)
        
        return result
    
    def _extract_interface_name(self, code_block: str) -> Optional[str]:
        """Extract interface name from code block"""
        match = re.search(r'(?:interface|type)\s+(\w+)', code_block)
        return match.group(1) if match else None
    
    def _extract_function_name(self, code_block: str) -> Optional[str]:
        """Extract function name from code block"""
        # Try function declaration
        func_match = re.search(r'function\s+(\w+)', code_block)
        if func_match:
            return func_match.group(1)
        
        # Try const declaration
        const_match = re.search(r'const\s+(\w+)\s*=', code_block)
        if const_match:
            return const_match.group(1)
        
        return None
    
    def _clean_component_function(self, function_body: str, original_name: str, new_name: str) -> str:
        """Clean component function body and rename if needed"""
        # Remove export default
        cleaned = re.sub(r'export\s+default\s+', '', function_body)
        
        # Replace function name if different
        if original_name != new_name:
            # Replace function declaration
            cleaned = re.sub(
                rf'\bfunction\s+{re.escape(original_name)}\b',
                f'function {new_name}',
                cleaned
            )
            
            # Replace const declaration
            cleaned = re.sub(
                rf'\bconst\s+{re.escape(original_name)}\s*=',
                f'const {new_name} =',
                cleaned
            )
        
        return cleaned
    
    def _build_nested_jsx_enhanced(self, component_names: List[str]) -> str:
        """Build nested JSX structure from component names"""
        if not component_names:
            return 'null'
        
        if len(component_names) == 1:
            return f'React.createElement({component_names[0]}, props)'
        
        # Build nested structure: Layout0 > Layout1 > ... > Page
        jsx = f'React.createElement({component_names[-1]}, props)'  # Start with innermost (page)
        
        # Wrap with layouts from innermost to outermost
        for comp_name in reversed(component_names[:-1]):
            jsx = f'React.createElement({comp_name}, {{ ...props, children: {jsx} }})'
        
        return jsx