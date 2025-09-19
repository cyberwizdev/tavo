"""
Tests for SWCCompiler caching functionality
"""

import pytest
from pathlib import Path
import tempfile
import shutil
import time
import json

from ..compiler import SWCCompiler, CacheEntry, CompilationResult
from ..installer import SWCInstaller
from unittest.mock import patch, MagicMock


class TestSWCCompilerCache:
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.compiler = SWCCompiler(self.temp_dir)
        
        # Create test files
        self.test_files = []
        for i in range(3):
            file_path = self.temp_dir / f"test{i}.tsx"
            file_path.write_text(f'''
import React from 'react';
export default function Test{i}() {{
  return <div>Test {i}</div>;
}}
            ''')
            self.test_files.append(file_path)
    
    def teardown_method(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir)
    
    def test_cache_key_generation(self):
        """Test cache key generation"""
        # Same files should generate same key
        key1 = self.compiler._get_cache_key(self.test_files, "ssr")
        key2 = self.compiler._get_cache_key(self.test_files, "ssr")
        assert key1 == key2
        
        # Different order should generate same key (files are sorted)
        key3 = self.compiler._get_cache_key(self.test_files[::-1], "ssr")
        assert key1 == key3
        
        # Different compilation type should generate different key
        key4 = self.compiler._get_cache_key(self.test_files, "hydration")
        assert key1 != key4
        
        # Different files should generate different key
        key5 = self.compiler._get_cache_key(self.test_files[:-1], "ssr")
        assert key1 != key5
    
    def test_file_hash_calculation(self):
        """Test file hash calculation"""
        file_path = self.test_files[0]
        
        # Calculate hash
        hash1 = self.compiler._calculate_file_hash(file_path)
        assert hash1
        assert len(hash1) == 64  # SHA256 hex length
        
        # Same file should produce same hash
        hash2 = self.compiler._calculate_file_hash(file_path)
        assert hash1 == hash2
        
        # Modified file should produce different hash
        original_content = file_path.read_text()
        file_path.write_text(original_content + "\n// comment")
        hash3 = self.compiler._calculate_file_hash(file_path)
        assert hash1 != hash3
    
    def test_config_hash_calculation(self):
        """Test configuration hash calculation"""
        hash1 = self.compiler._calculate_config_hash()
        assert hash1
        assert len(hash1) == 64  # SHA256 hex length
        
        # Same config should produce same hash
        hash2 = self.compiler._calculate_config_hash()
        assert hash1 == hash2
    
    def test_cache_entry_creation(self):
        """Test cache entry creation and storage"""
        compiled_js = "console.log('test');"
        bundled_tsx = "import React from 'react';\nexport default function Test() { return null; }"
        file_hashes = self.compiler._calculate_files_hash(self.test_files)
        config_hash = self.compiler._calculate_config_hash()
        compilation_type = "ssr"
        
        # Store in cache
        cache_key = self.compiler._get_cache_key(self.test_files, compilation_type)
        self.compiler._store_in_cache(
            cache_key, compiled_js, bundled_tsx, file_hashes, config_hash, compilation_type
        )
        
        # Verify cache entry exists
        assert cache_key in self.compiler._cache_index
        
        entry = self.compiler._cache_index[cache_key]
        assert entry.compiled_js == compiled_js
        assert entry.bundled_tsx == bundled_tsx
        assert entry.file_hashes == file_hashes
        assert entry.config_hash == config_hash
        assert entry.compilation_type == compilation_type
        assert entry.timestamp > 0
    
    def test_cache_retrieval(self):
        """Test cache retrieval"""
        compiled_js = "console.log('cached');"
        bundled_tsx = "const test = 'bundled';"
        file_hashes = self.compiler._calculate_files_hash(self.test_files)
        config_hash = self.compiler._calculate_config_hash()
        cache_key = self.compiler._get_cache_key(self.test_files, "ssr")
        
        # Store in cache
        self.compiler._store_in_cache(
            cache_key, compiled_js, bundled_tsx, file_hashes, config_hash, "ssr"
        )
        
        # Retrieve from cache
        result = self.compiler._get_from_cache(cache_key)
        assert result is not None
        
        cached_js, cached_tsx = result
        assert cached_js == compiled_js
        assert cached_tsx == bundled_tsx
    
    def test_cache_validity_checks(self):
        """Test cache validity checking"""
        file_hashes = self.compiler._calculate_files_hash(self.test_files)
        config_hash = self.compiler._calculate_config_hash()
        cache_key = self.compiler._get_cache_key(self.test_files, "ssr")
        compilation_type = "ssr"
        
        # Store cache entry
        self.compiler._store_in_cache(
            cache_key, "js_code", "tsx_code", file_hashes, config_hash, compilation_type
        )
        
        # Should be valid initially
        assert self.compiler._is_cache_valid(cache_key, file_hashes, config_hash, compilation_type)
        
        # Invalid if compilation type differs
        assert not self.compiler._is_cache_valid(cache_key, file_hashes, config_hash, "hydration")
        
        # Invalid if config changes
        different_config_hash = "different_hash"
        assert not self.compiler._is_cache_valid(cache_key, file_hashes, different_config_hash, compilation_type)
        
        # Invalid if file changes
        different_file_hashes = file_hashes.copy()
        different_file_hashes[str(self.test_files[0])] = "different_hash"
        assert not self.compiler._is_cache_valid(cache_key, different_file_hashes, config_hash, compilation_type)
    
    def test_cache_invalidation_on_file_change(self):
        """Test that cache is invalidated when files change"""
        # Mock compilation to avoid needing actual SWC
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.return_value = ("compiled_js", "bundled_tsx")
            
            # First compilation - should miss cache
            result1 = self.compiler.compile_files(self.test_files, "ssr")
            assert not result1.cache_hit
            assert mock_compile.call_count == 1
            
            # Second compilation - should hit cache
            result2 = self.compiler.compile_files(self.test_files, "ssr")
            assert result2.cache_hit
            assert mock_compile.call_count == 1  # No additional calls
            
            # Modify a file
            self.test_files[0].write_text("// modified content\nexport default function() { return null; }")
            
            # Third compilation - should miss cache due to file change
            result3 = self.compiler.compile_files(self.test_files, "ssr")
            assert not result3.cache_hit
            assert mock_compile.call_count == 2  # One additional call
    
    def test_cache_persistence(self):
        """Test that cache persists across compiler instances"""
        # Create first compiler and cache something
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.return_value = ("persistent_js", "persistent_tsx")
            
            result1 = self.compiler.compile_files(self.test_files, "ssr")
            assert not result1.cache_hit
        
        # Create new compiler instance
        new_compiler = SWCCompiler(self.temp_dir)
        
        with patch.object(new_compiler, '_compile_with_swc') as mock_compile2:
            mock_compile2.return_value = ("should_not_be_called", "should_not_be_called")
            
            # Should hit cache from previous compiler
            result2 = new_compiler.compile_files(self.test_files, "ssr")
            assert result2.cache_hit
            assert mock_compile2.call_count == 0  # Should not compile
            assert result2.compiled_js == "persistent_js"
    
    def test_cache_clear_all(self):
        """Test clearing all cache"""
        # Store some cache entries
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.return_value = ("js1", "tsx1")
            self.compiler.compile_files(self.test_files[:1], "ssr")
            
            mock_compile.return_value = ("js2", "tsx2")
            self.compiler.compile_files(self.test_files[:2], "hydration")
        
        # Verify cache has entries
        assert len(self.compiler._cache_index) == 2
        
        # Clear all cache
        self.compiler.clear_cache()
        
        # Verify cache is empty
        assert len(self.compiler._cache_index) == 0
        
        # Debug files should be cleaned up too
        debug_files = list(self.compiler.debug_dir.glob("*_bundled.tsx"))
        assert len(debug_files) == 0
    
    def test_cache_clear_by_age(self):
        """Test clearing cache by age"""
        # Create cache entries with different timestamps
        cache_key1 = "old_key"
        cache_key2 = "new_key"
        
        old_time = time.time() - (10 * 24 * 60 * 60)  # 10 days ago
        new_time = time.time()  # Now
        
        # Manually create cache entries with different timestamps
        self.compiler._cache_index[cache_key1] = CacheEntry(
            compiled_js="old_js",
            bundled_tsx="old_tsx",
            file_hashes={},
            config_hash="hash",
            compilation_type="ssr",
            timestamp=old_time
        )
        
        self.compiler._cache_index[cache_key2] = CacheEntry(
            compiled_js="new_js",
            bundled_tsx="new_tsx",
            file_hashes={},
            config_hash="hash",
            compilation_type="ssr",
            timestamp=new_time
        )
        
        # Clear cache older than 7 days
        self.compiler.clear_cache(older_than_days=7)
        
        # Only old entry should be removed
        assert cache_key1 not in self.compiler._cache_index
        assert cache_key2 in self.compiler._cache_index
    
    def test_cache_stats(self):
        """Test cache statistics"""
        # Initially empty
        stats = self.compiler.get_cache_stats()
        assert stats['total_entries'] == 0
        assert stats['total_size_bytes'] == 0
        
        # Add cache entries
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            mock_compile.return_value = ("compiled_js", "bundled_tsx")
            
            self.compiler.compile_files(self.test_files[:1], "ssr")
            self.compiler.compile_files(self.test_files[:2], "hydration")
        
        # Check updated stats
        stats = self.compiler.get_cache_stats()
        assert stats['total_entries'] == 2
        assert stats['total_size_bytes'] > 0
        assert stats['total_size_mb'] > 0
        assert stats['cache_hits'] >= 0
        assert stats['cache_misses'] >= 2
    
    def test_debug_file_creation(self):
        """Test creation of debug files"""
        with patch.object(self.compiler, '_compile_with_swc') as mock_compile:
            bundled_tsx = "const debug = 'content';"
            mock_compile.return_value = ("compiled_js", bundled_tsx)
            
            result = self.compiler.compile_files(self.test_files, "ssr")
            
            # Should create debug file
            assert result.bundled_tsx_path is not None
            assert result.bundled_tsx_path.exists()
            
            # Debug file should contain bundled content
            debug_content = result.bundled_tsx_path.read_text()
            assert bundled_tsx in debug_content
    
    def test_cache_backward_compatibility(self):
        """Test backward compatibility with old cache format"""
        # Simulate old cache entry without bundled_tsx field
        old_cache_data = {
            "test_key": type('OldCacheEntry', (), {
                'compiled_js': 'old_compiled',
                'file_hashes': {'test': 'hash'},
                'config_hash': 'config',
                'compilation_type': 'ssr',
                'timestamp': time.time()
            })()
        }
        
        # Save old format cache
        import pickle
        with open(self.compiler.cache_index_file, 'wb') as f:
            pickle.dump(old_cache_data, f)
        
        # Create new compiler instance - should migrate old cache
        new_compiler = SWCCompiler(self.temp_dir)
        
        # Should load and migrate old cache entry
        assert "test_key" in new_compiler._cache_index
        entry = new_compiler._cache_index["test_key"]
        assert entry.compiled_js == 'old_compiled'
        assert entry.bundled_tsx == ""  # Should be empty for old entries


class TestCompilationResult:
    
    def test_compilation_result_creation(self):
        """Test CompilationResult creation"""
        result = CompilationResult(
            compiled_js="console.log('test');",
            bundled_tsx_path=Path("/debug/bundled.tsx"),
            source_files=[Path("test.tsx")],
            cache_hit=True,
            compilation_time=1.5,
            output_size=1024
        )
        
        assert result.compiled_js == "console.log('test');"
        assert result.bundled_tsx_path == Path("/debug/bundled.tsx")
        assert len(result.source_files) == 1
        assert result.cache_hit is True
        assert result.compilation_time == 1.5
        assert result.output_size == 1024


class TestCacheEntry:
    
    def test_cache_entry_creation(self):
        """Test CacheEntry creation"""
        entry = CacheEntry(
            compiled_js="test_js",
            bundled_tsx="test_tsx",
            file_hashes={"file1": "hash1"},
            config_hash="config_hash",
            compilation_type="ssr",
            timestamp=123456.0
        )
        
        assert entry.compiled_js == "test_js"
        assert entry.bundled_tsx == "test_tsx"
        assert entry.file_hashes == {"file1": "hash1"}
        assert entry.config_hash == "config_hash"
        assert entry.compilation_type == "ssr"
        assert entry.timestamp == 123456.0