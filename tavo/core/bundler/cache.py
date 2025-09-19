"""
Cache management utilities for the bundler
"""

import json
import pickle
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict

from .utils import write_file_atomic, safe_mkdir

logger = logging.getLogger(__name__)


@dataclass
class CacheMetadata:
    """Metadata for cache entries"""
    created: float
    last_accessed: float
    access_count: int
    size_bytes: int


class CacheManager:
    """Manages various caches used by the bundler"""
    
    def __init__(self, project_root: Path, use_json_cache: bool = False):
        self.project_root = Path(project_root).resolve()
        self.use_json_cache = use_json_cache
        self.cache_dir = project_root / ".tavo" / "cache"
        self.metadata_file = self.cache_dir / "metadata.json"
        
        safe_mkdir(self.cache_dir)
        
        self._metadata: Dict[str, CacheMetadata] = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, CacheMetadata]:
        """Load cache metadata from disk"""
        if not self.metadata_file.exists():
            return {}
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert back to CacheMetadata objects
            metadata = {}
            for key, item in data.items():
                metadata[key] = CacheMetadata(**item)
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Failed to load cache metadata: {e}")
            return {}
    
    def _save_metadata(self):
        """Save cache metadata to disk"""
        try:
            # Convert CacheMetadata objects to dicts
            data = {}
            for key, metadata in self._metadata.items():
                data[key] = asdict(metadata)
            
            write_file_atomic(self.metadata_file, json.dumps(data, indent=2))
            
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")
    
    def store(self, key: str, data: Any, category: str = "default") -> bool:
        """
        Store data in cache
        
        Args:
            key: Cache key
            data: Data to store
            category: Cache category (for organization)
            
        Returns:
            True if stored successfully
        """
        try:
            cache_file = self.cache_dir / category / f"{key}.cache"
            safe_mkdir(cache_file.parent)
            
            if self.use_json_cache:
                # Try JSON first
                try:
                    content = json.dumps(data, indent=2)
                    cache_file = cache_file.with_suffix('.json')
                except (TypeError, ValueError):
                    logger.warning(f"Data not JSON serializable for key {key}, using pickle")
                    content = pickle.dumps(data)
                    cache_file = cache_file.with_suffix('.pkl')
            else:
                # Use pickle by default for performance
                content = pickle.dumps(data)
                cache_file = cache_file.with_suffix('.pkl')
            
            if isinstance(content, str):
                write_file_atomic(cache_file, content)
                size_bytes = len(content.encode('utf-8'))
            else:
                cache_file.write_bytes(content)
                size_bytes = len(content)
            
            # Update metadata
            now = time.time()
            cache_key = f"{category}/{key}"
            self._metadata[cache_key] = CacheMetadata(
                created=now,
                last_accessed=now,
                access_count=1,
                size_bytes=size_bytes
            )
            
            self._save_metadata()
            return True
            
        except Exception as e:
            logger.error(f"Failed to store cache key {key}: {e}")
            return False
    
    def retrieve(self, key: str, category: str = "default") -> Optional[Any]:
        """
        Retrieve data from cache
        
        Args:
            key: Cache key
            category: Cache category
            
        Returns:
            Cached data or None if not found
        """
        cache_key = f"{category}/{key}"
        
        # Try different file extensions
        for ext in ['.pkl', '.json', '.cache']:
            cache_file = self.cache_dir / category / f"{key}{ext}"
            
            if cache_file.exists():
                try:
                    if ext == '.json':
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    else:
                        with open(cache_file, 'rb') as f:
                            data = pickle.load(f)
                    
                    # Update access metadata
                    if cache_key in self._metadata:
                        metadata = self._metadata[cache_key]
                        metadata.last_accessed = time.time()
                        metadata.access_count += 1
                        self._save_metadata()
                    
                    return data
                    
                except Exception as e:
                    logger.warning(f"Failed to load cache file {cache_file}: {e}")
                    # Try to remove corrupted file
                    try:
                        cache_file.unlink()
                    except:
                        pass
        
        return None
    
    def exists(self, key: str, category: str = "default") -> bool:
        """Check if cache key exists"""
        for ext in ['.pkl', '.json', '.cache']:
            cache_file = self.cache_dir / category / f"{key}{ext}"
            if cache_file.exists():
                return True
        return False
    
    def invalidate(self, key: str, category: str = "default") -> bool:
        """
        Invalidate a cache entry
        
        Args:
            key: Cache key
            category: Cache category
            
        Returns:
            True if invalidated successfully
        """
        cache_key = f"{category}/{key}"
        invalidated = False
        
        # Remove cache files
        for ext in ['.pkl', '.json', '.cache']:
            cache_file = self.cache_dir / category / f"{key}{ext}"
            if cache_file.exists():
                try:
                    cache_file.unlink()
                    invalidated = True
                except Exception as e:
                    logger.warning(f"Failed to remove cache file {cache_file}: {e}")
        
        # Remove metadata
        if cache_key in self._metadata:
            del self._metadata[cache_key]
            self._save_metadata()
        
        return invalidated
    
    def clear_cache(self, category: Optional[str] = None, older_than_days: Optional[int] = None):
        """
        Clear cache entries
        
        Args:
            category: Only clear specific category (None = all)
            older_than_days: Only clear entries older than specified days
        """
        if older_than_days is not None:
            cutoff_time = time.time() - (older_than_days * 24 * 60 * 60)
        else:
            cutoff_time = None
        
        removed_count = 0
        keys_to_remove = []
        
        for cache_key, metadata in self._metadata.items():
            key_category, key_name = cache_key.split('/', 1) if '/' in cache_key else ('default', cache_key)
            
            # Check category filter
            if category is not None and key_category != category:
                continue
            
            # Check age filter
            if cutoff_time is not None and metadata.created >= cutoff_time:
                continue
            
            # Remove cache files
            for ext in ['.pkl', '.json', '.cache']:
                cache_file = self.cache_dir / key_category / f"{key_name}{ext}"
                if cache_file.exists():
                    try:
                        cache_file.unlink()
                        removed_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to remove {cache_file}: {e}")
            
            keys_to_remove.append(cache_key)
        
        # Remove metadata for deleted entries
        for key in keys_to_remove:
            if key in self._metadata:
                del self._metadata[key]
        
        if keys_to_remove:
            self._save_metadata()
        
        if category:
            logger.info(f"Cleared {removed_count} cache entries from category '{category}'")
        else:
            logger.info(f"Cleared {removed_count} cache entries")
    
    def get_stats(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get cache statistics"""
        total_entries = 0
        total_size = 0
        categories = set()
        
        for cache_key, metadata in self._metadata.items():
            key_category = cache_key.split('/', 1)[0] if '/' in cache_key else 'default'
            categories.add(key_category)
            
            if category is None or key_category == category:
                total_entries += 1
                total_size += metadata.size_bytes
        
        return {
            'total_entries': total_entries,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'categories': sorted(categories),
            'cache_dir': str(self.cache_dir)
        }
    
    def optimize(self) -> Dict[str, int]:
        """Optimize cache by removing unused entries"""
        # Remove entries for files that no longer exist
        removed_orphaned = 0
        removed_empty = 0
        
        keys_to_remove = []
        
        for cache_key in self._metadata:
            key_category, key_name = cache_key.split('/', 1) if '/' in cache_key else ('default', cache_key)
            
            # Check if cache files exist
            cache_files_exist = False
            for ext in ['.pkl', '.json', '.cache']:
                cache_file = self.cache_dir / key_category / f"{key_name}{ext}"
                if cache_file.exists():
                    cache_files_exist = True
                    break
            
            if not cache_files_exist:
                keys_to_remove.append(cache_key)
                removed_orphaned += 1
        
        # Remove orphaned metadata
        for key in keys_to_remove:
            del self._metadata[key]
        
        # Remove empty category directories
        for category_dir in self.cache_dir.iterdir():
            if category_dir.is_dir():
                try:
                    if not any(category_dir.iterdir()):
                        category_dir.rmdir()
                        removed_empty += 1
                except:
                    pass
        
        if keys_to_remove:
            self._save_metadata()
        
        logger.info(f"Cache optimization: removed {removed_orphaned} orphaned entries, {removed_empty} empty directories")
        
        return {
            'removed_orphaned': removed_orphaned,
            'removed_empty_dirs': removed_empty
        }