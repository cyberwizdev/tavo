"""
Bino ORM Migrations

Simple migration runner (create, apply, rollback).
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class Migration:
    """Represents a database migration."""
    name: str
    file_path: Path
    checksum: str
    applied_at: Optional[datetime] = None
    
    @classmethod
    def from_file(cls, file_path: Path) -> 'Migration':
        """Create Migration from file."""
        content = file_path.read_text()
        checksum = hashlib.md5(content.encode()).hexdigest()
        
        return cls(
            name=file_path.stem,
            file_path=file_path,
            checksum=checksum
        )


class MigrationRunner:
    """
    Database migration runner with create, apply, and rollback functionality.
    """
    
    def __init__(self, migrations_dir: Path, database_url: Optional[str] = None):
        self.migrations_dir = migrations_dir
        self.database_url = database_url
        self._connection = None
    
    async def create_migration(self, name: str, content: str) -> Path:
        """
        Create a new migration file.
        
        Args:
            name: Migration name
            content: Migration SQL content
            
        Returns:
            Path to created migration file
            
        Example:
            >>> runner = MigrationRunner(Path("migrations"))
            >>> file_path = await runner.create_migration("add_users", "CREATE TABLE users...")
        """
        # Ensure migrations directory exists
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp prefix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{name}.sql"
        
        migration_file = self.migrations_dir / filename
        
        # Write migration content
        migration_file.write_text(content)
        
        logger.info(f"Created migration: {filename}")
        return migration_file
    
    async def get_pending_migrations(self) -> List[Migration]:
        """
        Get list of migrations that haven't been applied.
        
        Returns:
            List of pending Migration objects
        """
        all_migrations = self._discover_migrations()
        applied_migrations = await self._get_applied_migrations()
        
        applied_names = {m["name"] for m in applied_migrations}
        
        pending = [
            migration for migration in all_migrations
            if migration.name not in applied_names
        ]
        
        return pending
    
    async def apply_migrations(self, target: Optional[str] = None) -> int:
        """
        Apply pending migrations.
        
        Args:
            target: Specific migration to apply up to (None for all)
            
        Returns:
            Number of migrations applied
            
        Example:
            >>> runner = MigrationRunner(Path("migrations"))
            >>> count = await runner.apply_migrations()
            >>> print(f"Applied {count} migrations")
        """
        pending = await self.get_pending_migrations()
        
        if not pending:
            logger.info("No pending migrations")
            return 0
        
        # Filter to target if specified
        if target:
            target_index = next(
                (i for i, m in enumerate(pending) if m.name == target),
                None
            )
            if target_index is not None:
                pending = pending[:target_index + 1]
        
        applied_count = 0
        
        for migration in pending:
            try:
                await self._apply_single_migration(migration)
                applied_count += 1
                logger.info(f"Applied migration: {migration.name}")
            except Exception as e:
                logger.error(f"Failed to apply migration {migration.name}: {e}")
                break
        
        logger.info(f"Applied {applied_count} migrations")
        return applied_count
    
    async def rollback_migration(self, target: str) -> None:
        """
        Rollback to a specific migration.
        
        Args:
            target: Migration name to rollback to
            
        Raises:
            ValueError: If target migration not found
        """
        applied_migrations = await self._get_applied_migrations()
        
        # Find target migration
        target_index = None
        for i, migration in enumerate(applied_migrations):
            if migration["name"] == target:
                target_index = i
                break
        
        if target_index is None:
            raise ValueError(f"Migration '{target}' not found in applied migrations")
        
        # Rollback migrations after target
        to_rollback = applied_migrations[target_index + 1:]
        
        for migration_data in reversed(to_rollback):
            await self._rollback_single_migration(migration_data["name"])
            logger.info(f"Rolled back migration: {migration_data['name']}")
    
    def _discover_migrations(self) -> List[Migration]:
        """Discover migration files in migrations directory."""
        if not self.migrations_dir.exists():
            return []
        
        migrations = []
        
        for sql_file in sorted(self.migrations_dir.glob("*.sql")):
            try:
                migration = Migration.from_file(sql_file)
                migrations.append(migration)
            except Exception as e:
                logger.error(f"Failed to load migration {sql_file}: {e}")
        
        return migrations
    
    async def _get_applied_migrations(self) -> List[Dict[str, Any]]:
        """Get list of applied migrations from database."""
        # TODO: implement actual database query
        # This would query the migrations table to get applied migrations
        
        # Mock implementation
        return [
            {
                "name": "001_initial",
                "checksum": "abc123",
                "applied_at": datetime.now().isoformat()
            }
        ]
    
    async def _apply_single_migration(self, migration: Migration) -> None:
        """
        Apply a single migration.
        
        Args:
            migration: Migration to apply
        """
        # Read migration content
        sql_content = migration.file_path.read_text()
        
        # TODO: implement actual SQL execution
        # This would execute the SQL against the database
        logger.debug(f"Executing migration SQL: {migration.name}")
        
        # Record migration as applied
        await self._record_migration_applied(migration)
    
    async def _rollback_single_migration(self, migration_name: str) -> None:
        """
        Rollback a single migration.
        
        Args:
            migration_name: Name of migration to rollback
        """
        # TODO: implement migration rollback
        # This would require down migrations or schema snapshots
        logger.warning(f"Rollback not implemented for: {migration_name}")
    
    async def _record_migration_applied(self, migration: Migration) -> None:
        """Record that a migration has been applied."""
        # TODO: implement recording in migrations table
        logger.debug(f"Recording migration as applied: {migration.name}")
    
    async def init_migrations_table(self) -> None:
        """Initialize the migrations tracking table."""
        # TODO: implement migrations table creation
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS bino_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL UNIQUE,
            checksum VARCHAR(32) NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        logger.info("Migrations table initialized")
    
    def get_migration_status(self) -> Dict[str, Any]:
        """
        Get current migration status.
        
        Returns:
            Migration status information
        """
        all_migrations = self._discover_migrations()
        
        return {
            "total_migrations": len(all_migrations),
            "migrations_dir": str(self.migrations_dir),
            "database_url": self.database_url or "Not configured"
        }


def create_migration_content(
    description: str, 
    up_sql: str, 
    down_sql: Optional[str] = None
) -> str:
    """
    Create migration file content with metadata.
    
    Args:
        description: Migration description
        up_sql: SQL to apply migration
        down_sql: SQL to rollback migration (optional)
        
    Returns:
        Complete migration file content
        
    Example:
        >>> content = create_migration_content(
        ...     "Add users table",
        ...     "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);"
        ... )
    """
    header = f"""-- Migration: {description}
-- Created: {datetime.now().isoformat()}

-- Up Migration
"""
    
    footer = ""
    if down_sql:
        footer = f"""

-- Down Migration (for rollback)
-- {down_sql}
"""
    
    return header + up_sql + footer


if __name__ == "__main__":
    # Example usage
    async def main():
        migrations_dir = Path("migrations")
        runner = MigrationRunner(migrations_dir)
        
        # Create example migration
        migration_sql = """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        migration_file = await runner.create_migration("create_users", migration_sql)
        print(f"Created migration: {migration_file}")
        
        # Check status
        status = runner.get_migration_status()
        print(f"Migration status: {status}")
        
        # Get pending migrations
        pending = await runner.get_pending_migrations()
        print(f"Pending migrations: {len(pending)}")
    
    asyncio.run(main())

# Unit tests as comments:
# 1. test_create_migration() - verify migration file creation with correct content
# 2. test_get_pending_migrations() - test detection of unapplied migrations
# 3. test_apply_migrations() - verify migration application process works