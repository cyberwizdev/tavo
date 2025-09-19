"""
App Router file resolution and import path handling
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

from .constants import (
    APP_DIR_NAME, LAYOUT_FILES, PAGE_FILES, LOADING_FILES, 
    HEAD_FILES, ROUTE_FILES, DYNAMIC_ROUTE_PATTERN, 
    CATCH_ALL_ROUTE_PATTERN, SUPPORTED_EXTENSIONS
)
from .utils import normalize_path, read_file

logger = logging.getLogger(__name__)


@dataclass
class RouteNode:
    """Represents a single route in the App Router tree"""
    path: str
    file_path: Optional[Path]
    route_type: str  # 'layout', 'page', 'loading', 'head', 'route'
    children: List['RouteNode']
    route_segment: str
    is_dynamic: bool = False
    is_catch_all: bool = False


@dataclass 
class RouteEntry:
    """Complete route entry with all associated files"""
    route_path: str
    layout_chain: List[Path]  # Outermost to innermost
    page_file: Optional[Path]
    loading_file: Optional[Path]
    head_file: Optional[Path]
    route_file: Optional[Path]
    all_files: Set[Path]


class ImportResolver:
    """Resolves imports and creates bundled files for SWC compilation"""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.app_dir = self.project_root / APP_DIR_NAME
        self._route_cache: Optional[List[RouteEntry]] = None
        self._import_aliases = {
            "@/": str(self.project_root / ""),
            "~/": str(self.project_root / ""),
            "components/": str(self.project_root / "components" / ""),
            "app/": str(self.app_dir / ""),
        }
    
    def resolve_routes(self) -> List[RouteEntry]:
        """
        Resolve all routes from the app directory
        
        Returns:
            List of RouteEntry objects representing all routes
        """
        if self._route_cache is not None:
            return self._route_cache
        
        if not self.app_dir.exists():
            logger.warning(f"App directory not found: {self.app_dir}")
            return []
        
        # Build route tree
        route_tree = self._build_route_tree()
        
        # Convert tree to flat route entries
        route_entries = self._tree_to_entries(route_tree)
        
        # Sort routes for consistent ordering
        route_entries.sort(key=lambda x: (x.route_path.count('/'), x.route_path))
        
        self._route_cache = route_entries
        logger.info(f"Resolved {len(route_entries)} routes")
        
        return route_entries
    
    def _build_route_tree(self) -> List[RouteNode]:
        """Build route tree from filesystem"""
        routes = []
        
        # Start from app directory
        for item in sorted(self.app_dir.iterdir()):
            if item.is_dir():
                route_node = self._process_route_directory(item, "")
                if route_node:
                    routes.append(route_node)
            elif item.name in PAGE_FILES:
                # Root page
                root_node = RouteNode(
                    path="/",
                    file_path=item,
                    route_type="page",
                    children=[],
                    route_segment="",
                    is_dynamic=False
                )
                routes.append(root_node)
        
        # Also check for root layout and other files
        for file_type, file_names in [
            ("layout", LAYOUT_FILES),
            ("loading", LOADING_FILES), 
            ("head", HEAD_FILES),
            ("route", ROUTE_FILES)
        ]:
            for file_name in file_names:
                root_file = self.app_dir / file_name
                if root_file.exists():
                    node = RouteNode(
                        path="/",
                        file_path=root_file,
                        route_type=file_type,
                        children=[],
                        route_segment="",
                        is_dynamic=False
                    )
                    routes.append(node)
        
        return routes
    
    def _process_route_directory(self, directory: Path, parent_path: str) -> Optional[RouteNode]:
        """Process a single route directory"""
        dir_name = directory.name
        
        # Handle dynamic routes
        is_dynamic = False
        is_catch_all = False
        segment = dir_name
        
        if re.match(CATCH_ALL_ROUTE_PATTERN, dir_name):
            is_catch_all = True
            is_dynamic = True
            segment = re.sub(CATCH_ALL_ROUTE_PATTERN, r"\1", dir_name)
        elif re.match(DYNAMIC_ROUTE_PATTERN, dir_name):
            is_dynamic = True
            segment = re.sub(DYNAMIC_ROUTE_PATTERN, r"\1", dir_name)
        
        current_path = f"{parent_path}/{dir_name}" if parent_path else f"/{dir_name}"
        
        # Find route files in this directory
        route_files = {}
        for file_type, file_names in [
            ("layout", LAYOUT_FILES),
            ("page", PAGE_FILES),
            ("loading", LOADING_FILES),
            ("head", HEAD_FILES),
            ("route", ROUTE_FILES)
        ]:
            for file_name in file_names:
                file_path = directory / file_name
                if file_path.exists():
                    route_files[file_type] = file_path
                    break
        
        # Process child directories
        children = []
        for child_dir in sorted(directory.iterdir()):
            if child_dir.is_dir():
                child_node = self._process_route_directory(child_dir, current_path)
                if child_node:
                    children.append(child_node)
        
        # Create nodes for each file type found
        nodes = []
        for file_type, file_path in route_files.items():
            node = RouteNode(
                path=current_path,
                file_path=file_path,
                route_type=file_type,
                children=children,
                route_segment=segment,
                is_dynamic=is_dynamic,
                is_catch_all=is_catch_all
            )
            nodes.append(node)
        
        # If we have children but no files, create a container node
        if children and not route_files:
            node = RouteNode(
                path=current_path,
                file_path=None,
                route_type="directory",
                children=children,
                route_segment=segment,
                is_dynamic=is_dynamic,
                is_catch_all=is_catch_all
            )
            nodes.append(node)
        
        return nodes[0] if nodes else None
    
    def _tree_to_entries(self, tree: List[RouteNode]) -> List[RouteEntry]:
        """Convert route tree to flat list of entries"""
        entries = []
        
        # Group nodes by path to combine layout/page/etc for same route
        path_groups = defaultdict(list)
        
        def collect_nodes(nodes, parent_layouts=None):
            if parent_layouts is None:
                parent_layouts = []
            
            for node in nodes:
                if node.file_path:
                    path_groups[node.path].append(node)
                
                # If this is a layout, add it to parent layouts for children
                child_layouts = parent_layouts.copy()
                if node.route_type == "layout" and node.file_path:
                    child_layouts.append(node.file_path)
                
                collect_nodes(node.children, child_layouts)
        
        collect_nodes(tree)
        
        # Convert groups to entries
        for path, nodes in path_groups.items():
            # Find layout chain by walking up the directory tree
            layout_chain = self._find_layout_chain(path)
            
            # Extract files by type
            page_file = None
            loading_file = None
            head_file = None
            route_file = None
            
            for node in nodes:
                if node.route_type == "page":
                    page_file = node.file_path
                elif node.route_type == "loading":
                    loading_file = node.file_path
                elif node.route_type == "head":
                    head_file = node.file_path
                elif node.route_type == "route":
                    route_file = node.file_path
            
            # Only create entry if there's a page or route file
            if page_file or route_file:
                all_files = set()
                if page_file:
                    all_files.add(page_file)
                if loading_file:
                    all_files.add(loading_file)
                if head_file:
                    all_files.add(head_file)
                if route_file:
                    all_files.add(route_file)
                all_files.update(layout_chain)
                
                entry = RouteEntry(
                    route_path=path,
                    layout_chain=layout_chain,
                    page_file=page_file,
                    loading_file=loading_file,
                    head_file=head_file,
                    route_file=route_file,
                    all_files=all_files
                )
                entries.append(entry)
        
        return entries
    
    def _find_layout_chain(self, route_path: str) -> List[Path]:
        """Find layout chain for a route path"""
        layouts = []
        
        # Start from root and walk down the path
        current_path = self.app_dir
        layouts_found = []
        
        # Check root layout
        for layout_name in LAYOUT_FILES:
            root_layout = current_path / layout_name
            if root_layout.exists():
                layouts_found.append(root_layout)
                break
        
        # Walk down the route segments
        if route_path != "/":
            segments = [s for s in route_path.split("/") if s]
            
            for segment in segments:
                current_path = current_path / segment
                
                # Look for layout in this directory
                for layout_name in LAYOUT_FILES:
                    layout_file = current_path / layout_name
                    if layout_file.exists():
                        layouts_found.append(layout_file)
                        break
        
        return layouts_found
    
    def create_entry_bundle_files_for_route(self, route_entry: RouteEntry) -> List[Path]:
        """
        Get list of source files needed to build a route bundle
        
        Args:
            route_entry: Route entry to get files for
            
        Returns:
            List of file paths needed for the bundle
        """
        files = list(route_entry.all_files)
        
        # Add shared utilities and dependencies
        shared_dirs = ["components", "lib", "utils", "hooks"]
        for dir_name in shared_dirs:
            shared_dir = self.project_root / dir_name
            if shared_dir.exists():
                files.extend(self._find_importable_files(shared_dir))
        
        # Remove duplicates and sort
        unique_files = sorted(set(files))
        
        return unique_files
    
    def _find_importable_files(self, directory: Path) -> List[Path]:
        """Find all importable files in a directory"""
        files = []
        
        for item in directory.rglob("*"):
            if item.is_file() and item.suffix in SUPPORTED_EXTENSIONS:
                files.append(item)
        
        return files
    
    def create_single_file_for_swc(self, files: List[Path], temp_dir: Path) -> Path:
        """
        Create a single bundled TSX file from multiple source files
        
        Args:
            files: List of source files to bundle
            temp_dir: Temporary directory to write bundled file
            
        Returns:
            Path to the bundled file
        """
        temp_dir.mkdir(parents=True, exist_ok=True)
        bundled_file = temp_dir / "bundled.tsx"
        
        # Separate layout files from page files and other components
        layout_files = []
        page_file = None
        other_files = []
        
        for file_path in files:
            file_name = file_path.name
            if file_name in LAYOUT_FILES:
                layout_files.append(file_path)
            elif file_name in PAGE_FILES:
                page_file = file_path
            else:
                other_files.append(file_path)
        
        # Use LayoutComposer for layout and page composition
        if page_file:
            from .layouts import LayoutComposer
            composer = LayoutComposer()
            
            # Sort layout files by depth (outermost to innermost)
            layout_files.sort(key=lambda f: len(f.parts))
            
            try:
                composed_content = composer.compose_layouts(layout_files, page_file)
            except Exception as e:
                logger.error(f"Failed to compose layouts: {e}")
                # Fallback to simple composition
                composed_content = self._fallback_composition(layout_files, page_file, other_files)
        else:
            # No page file, use fallback
            composed_content = self._fallback_composition(layout_files, None, other_files)
        
        # Add other component imports with resolved paths
        if other_files:
            additional_imports = []
            for file_path in other_files:
                # Resolve import path relative to project root
                try:
                    rel_path = file_path.relative_to(self.project_root)
                    import_path = str(rel_path).replace('\\', '/').replace('.tsx', '').replace('.ts', '').replace('.jsx', '').replace('.js', '')
                    
                    # Add import for the component
                    component_name = file_path.stem.replace('-', '').replace('_', '')
                    additional_imports.append(f'// Import from {import_path}')
                    
                except ValueError:
                    logger.warning(f"Could not resolve relative path for {file_path}")
            
            if additional_imports:
                composed_content = '\n'.join(additional_imports) + '\n\n' + composed_content
        
        # Write bundled file
        bundled_file.write_text(composed_content, encoding="utf-8")
        
        logger.info(f"Created bundled file: {bundled_file}")
        return bundled_file
    
    def _fallback_composition(self, layout_files: List[Path], page_file: Optional[Path], other_files: List[Path]) -> str:
        """Fallback composition when LayoutComposer fails"""
        lines = ['import React from "react";', '']
        
        # Add simple component
        if page_file:
            try:
                page_content = read_file(page_file)
                # Extract just the component function if possible
                if 'export default' in page_content:
                    lines.append('// Fallback page component')
                    lines.append(page_content.replace('export default', 'const PageComponent ='))
                    lines.append('')
                    lines.append('export default PageComponent;')
                else:
                    lines.append('export default function FallbackPage() { return <div>Page content</div>; }')
            except Exception as e:
                logger.error(f"Fallback composition failed: {e}")
                lines.append('export default function ErrorPage() { return <div>Error loading page</div>; }')
        else:
            lines.append('export default function EmptyPage() { return <div>No page found</div>; }')
        
        return '\n'.join(lines)
    
    def _process_file_content(self, content: str, file_path: Path) -> Dict:
        """Process individual file content for bundling"""
        lines = content.split("\n")
        imports = set()
        exports = []
        code_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith("import "):
                # Resolve import paths
                resolved_import = self._resolve_import_path(stripped, file_path)
                imports.add(resolved_import)
            elif stripped.startswith("export "):
                exports.append(line)
            else:
                code_lines.append(line)
        
        return {
            "imports": imports,
            "exports": exports,
            "code": "\n".join(code_lines)
        }
    
    def _resolve_import_path(self, import_line: str, current_file: Path) -> str:
        """Resolve import path aliases"""
        # Extract the import path
        import_match = re.search(r'from\s+["\']([^"\']+)["\']', import_line)
        if not import_match:
            return import_line
        
        import_path = import_match.group(1)
        
        # Check for aliases
        for alias, real_path in self._import_aliases.items():
            if import_path.startswith(alias):
                resolved_path = import_path.replace(alias, real_path, 1)
                return import_line.replace(import_path, resolved_path)
        
        # Handle relative imports
        if import_path.startswith("."):
            current_dir = current_file.parent
            resolved_path = (current_dir / import_path).resolve()
            rel_path = resolved_path.relative_to(self.project_root)
            return import_line.replace(import_path, str(rel_path))
        
        return import_line
    
    def invalidate_cache(self) -> None:
        """Invalidate the route cache"""
        self._route_cache = None
        logger.info("Route cache invalidated")