"""
Enhanced Tavo ORM Migrations

Robust migration runner with database support, transaction safety, and rollback capabilities.
"""

import asyncio
import logging
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Protocol
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
from enum import Enum
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class MigrationStatus(Enum):
    """Migration status enumeration."""
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Migration:
    """Represents a database migration with enhanced metadata."""
    name: str
    file_path: Path
    checksum: str
    up_sql: str
    down_sql: Optional[str] = None
    description: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    applied_at: Optional[datetime] = None
    status: MigrationStatus = MigrationStatus.PENDING
    
    @classmethod
    def from_file(cls, file_path: Path) -> 'Migration':
        """Create Migration from file with enhanced parsing."""
        content = file_path.read_text()
        checksum = hashlib.sha256(content.encode()).hexdigest()
        
        # Parse migration content
        up_sql, down_sql, metadata = cls._parse_migration_content(content)
        
        return cls(
            name=file_path.stem,
            file_path=file_path,
            checksum=checksum,
            up_sql=up_sql,
            down_sql=down_sql,
            description=metadata.get('description'),
            dependencies=metadata.get('dependencies', [])
        )
    
    @staticmethod
    def _parse_migration_content(content: str) -> tuple[str, Optional[str], Dict[str, Any]]:
        """Parse migration file content into sections."""
        metadata = {}
        
        # Extract metadata from comments
        description_match = re.search(r'--\s*Description:\s*(.+)', content, re.IGNORECASE)
        if description_match:
            metadata['description'] = description_match.group(1).strip()
        
        deps_match = re.search(r'--\s*Depends:\s*(.+)', content, re.IGNORECASE)
        if deps_match:
            metadata['dependencies'] = [d.strip() for d in deps_match.group(1).split(',')]
        
        # Split UP and DOWN sections
        up_match = re.search(r'--\s*UP\s*\n(.*?)(?=--\s*DOWN|$)', content, re.DOTALL | re.IGNORECASE)
        down_match = re.search(r'--\s*DOWN\s*\n(.*?)$', content, re.DOTALL | re.IGNORECASE)
        
        up_sql = up_match.group(1).strip() if up_match else content.strip()
        down_sql = down_match.group(1).strip() if down_match else None
        
        return up_sql, down_sql, metadata


class DatabaseAdapter(Protocol):
    """Protocol for database adapters."""
    
    async def execute(self, sql: str, params: Optional[Dict] = None) -> None:
        """Execute SQL statement."""
        ...
    
    async def fetch_all(self, sql: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Fetch all results from query."""
        ...
    
    async def begin_transaction(self) -> None:
        """Begin database transaction."""
        ...
    
    async def commit_transaction(self) -> None:
        """Commit database transaction."""
        ...
    
    async def rollback_transaction(self) -> None:
        """Rollback database transaction."""
        ...
    
    async def close(self) -> None:
        """Close database connection."""
        ...


class SQLiteAdapter:
    """SQLite database adapter implementation."""
    
    def __init__(self, database_path: Union[str, Path]):
        self.database_path = Path(database_path)
        self._connection = None
        self._transaction_active = False
    
    async def _get_connection(self):
        """Get database connection (mock implementation)."""
        if self._connection is None:
            # In real implementation, this would use aiosqlite or similar
            logger.debug(f"Connecting to SQLite database: {self.database_path}")
            self._connection = f"mock_connection_{self.database_path}"
        return self._connection
    
    async def execute(self, sql: str, params: Optional[Dict] = None) -> None:
        """Execute SQL statement."""
        await self._get_connection()
        logger.debug(f"Executing SQL: {sql[:100]}...")
        # Mock execution
        
    async def fetch_all(self, sql: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Fetch all results from query."""
        await self._get_connection()
        logger.debug(f"Fetching: {sql[:100]}...")
        
        # Mock response based on query type
        if "tavo_migrations" in sql:
            return [
                {
                    "name": "20240101_120000_initial_schema",
                    "checksum": "abc123def456",
                    "applied_at": "2024-01-01T12:00:00",
                    "status": "applied"
                }
            ]
        return []
    
    async def begin_transaction(self) -> None:
        """Begin database transaction."""
        await self._get_connection()
        logger.debug("BEGIN TRANSACTION")
        self._transaction_active = True
    
    async def commit_transaction(self) -> None:
        """Commit database transaction."""
        logger.debug("COMMIT TRANSACTION")
        self._transaction_active = False
    
    async def rollback_transaction(self) -> None:
        """Rollback database transaction."""
        logger.debug("ROLLBACK TRANSACTION")
        self._transaction_active = False
    
    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            logger.debug("Closing database connection")
            self._connection = None


class MigrationError(Exception):
    """Base exception for migration errors."""
    pass


class MigrationValidationError(MigrationError):
    """Raised when migration validation fails."""
    pass


class MigrationRunner:
    """
    Enhanced database migration runner with robust error handling and rollback support.
    """
    
    def __init__(self, migrations_dir: Path, db_adapter: DatabaseAdapter):
        self.migrations_dir = migrations_dir
        self.db_adapter = db_adapter
        self._migrations_cache: Optional[List[Migration]] = None
    
    async def initialize(self) -> None:
        """Initialize the migration system."""
        await self._ensure_migrations_table()
        logger.info("Migration system initialized")
    
    async def create_migration(
        self, 
        name: str, 
        description: str = "", 
        up_sql: str = "", 
        down_sql: str = "",
        dependencies: Optional[List[str]] = None
    ) -> Path:
        """
        Create a new migration file with enhanced templating.
        
        Args:
            name: Migration name (will be prefixed with timestamp)
            description: Human-readable description
            up_sql: SQL for applying the migration
            down_sql: SQL for rolling back the migration
            dependencies: List of migration names this depends on
            
        Returns:
            Path to created migration file
        """
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp prefix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{name}.sql"
        
        migration_file = self.migrations_dir / filename
        
        # Create migration content
        content = self._create_migration_template(
            description=description,
            up_sql=up_sql,
            down_sql=down_sql,
            dependencies=dependencies or []
        )
        
        migration_file.write_text(content)
        
        # Clear cache to force reload
        self._migrations_cache = None
        
        logger.info(f"Created migration: {filename}")
        return migration_file
    
    async def get_migrations(self, status_filter: Optional[MigrationStatus] = None) -> List[Migration]:
        """
        Get migrations with optional status filtering.
        
        Args:
            status_filter: Filter migrations by status
            
        Returns:
            List of Migration objects
        """
        if self._migrations_cache is None:
            await self._load_migrations()
        
        migrations = self._migrations_cache or []
        
        if status_filter:
            migrations = [m for m in migrations if m.status == status_filter]
        
        return migrations
    
    async def get_pending_migrations(self) -> List[Migration]:
        """Get list of migrations that haven't been applied."""
        return await self.get_migrations(MigrationStatus.PENDING)
    
    async def apply_migrations(
        self, 
        target: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Apply pending migrations with enhanced error handling.
        
        Args:
            target: Specific migration to apply up to (None for all)
            dry_run: If True, validate but don't execute migrations
            
        Returns:
            Dictionary with application results
        """
        pending = await self.get_pending_migrations()
        
        if not pending:
            return {"applied": 0, "skipped": 0, "errors": []}
        
        # Validate migration chain
        await self._validate_migration_chain(pending)
        
        # Filter to target if specified
        if target:
            target_index = next(
                (i for i, m in enumerate(pending) if m.name == target),
                None
            )
            if target_index is not None:
                pending = pending[:target_index + 1]
            else:
                raise MigrationError(f"Target migration '{target}' not found")
        
        results = {"applied": 0, "skipped": 0, "errors": []}
        
        if dry_run:
            logger.info(f"DRY RUN: Would apply {len(pending)} migrations")
            for migration in pending:
                logger.info(f"  - {migration.name}: {migration.description}")
            results["would_apply"] = len(pending)
            return results
        
        for migration in pending:
            try:
                async with self._transaction():
                    await self._apply_single_migration(migration)
                    results["applied"] += 1
                    logger.info(f"✓ Applied: {migration.name}")
            except Exception as e:
                error_msg = f"Failed to apply {migration.name}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                break  # Stop on first error
        
        logger.info(f"Migration complete: {results['applied']} applied, {len(results['errors'])} errors")
        return results
    
    async def rollback_to(self, target: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Rollback migrations to a specific target.
        
        Args:
            target: Migration name to rollback to
            dry_run: If True, validate but don't execute rollbacks
            
        Returns:
            Dictionary with rollback results
        """
        applied_migrations = await self.get_migrations(MigrationStatus.APPLIED)
        applied_migrations.reverse()  # Rollback in reverse order
        
        # Find target migration
        target_index = None
        for i, migration in enumerate(applied_migrations):
            if migration.name == target:
                target_index = i
                break
        
        if target_index is None:
            raise MigrationError(f"Target migration '{target}' not found or not applied")
        
        to_rollback = applied_migrations[:target_index]
        
        results = {"rolled_back": 0, "errors": []}
        
        if dry_run:
            logger.info(f"DRY RUN: Would rollback {len(to_rollback)} migrations")
            for migration in to_rollback:
                logger.info(f"  - {migration.name}")
            results["would_rollback"] = len(to_rollback)
            return results
        
        for migration in to_rollback:
            try:
                if not migration.down_sql:
                    raise MigrationError(f"Migration {migration.name} has no rollback SQL")
                
                async with self._transaction():
                    await self._rollback_single_migration(migration)
                    results["rolled_back"] += 1
                    logger.info(f"✓ Rolled back: {migration.name}")
            except Exception as e:
                error_msg = f"Failed to rollback {migration.name}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                break
        
        return results
    
    async def get_status(self) -> Dict[str, Any]:
        """Get comprehensive migration status."""
        migrations = await self.get_migrations()
        
        status_counts = {}
        for status in MigrationStatus:
            status_counts[status.value] = len([m for m in migrations if m.status == status])
        
        return {
            "total_migrations": len(migrations),
            "status_breakdown": status_counts,
            "migrations_dir": str(self.migrations_dir),
            "last_applied": self._get_last_applied_migration(migrations),
            "pending_count": status_counts.get("pending", 0)
        }
    
    def _get_last_applied_migration(self, migrations: List[Migration]) -> Optional[str]:
        """Get the name of the last applied migration."""
        applied = [m for m in migrations if m.status == MigrationStatus.APPLIED]
        if applied:
            return max(applied, key=lambda m: m.applied_at or datetime.min).name
        return None
    
    async def _load_migrations(self) -> None:
        """Load and cache all migrations with their status."""
        file_migrations = self._discover_migrations()
        applied_data = await self._get_applied_migrations()
        
        # Create lookup for applied migrations
        applied_lookup = {data["name"]: data for data in applied_data}
        
        # Set status for each migration
        for migration in file_migrations:
            if migration.name in applied_lookup:
                applied_info = applied_lookup[migration.name]
                migration.status = MigrationStatus(applied_info.get("status", "applied"))
                migration.applied_at = applied_info.get("applied_at")
            else:
                migration.status = MigrationStatus.PENDING
        
        self._migrations_cache = sorted(file_migrations, key=lambda m: m.name)
    
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
        try:
            return await self.db_adapter.fetch_all(
                "SELECT name, checksum, applied_at, status FROM tavo_migrations ORDER BY applied_at"
            )
        except Exception as e:
            logger.warning(f"Could not fetch applied migrations: {e}")
            return []
    
    async def _validate_migration_chain(self, migrations: List[Migration]) -> None:
        """Validate that migration dependencies are satisfied."""
        all_migrations = await self.get_migrations()
        
        # Create lookup for migrations by short name, preferring the latest version
        migration_lookup = {}
        for m in sorted(all_migrations, key=lambda x: x.name):
            short_name = self._extract_short_name(m.name)
            # Always use the latest migration with this short name
            if short_name not in migration_lookup or m.name > migration_lookup[short_name].name:
                migration_lookup[short_name] = m
            # Also allow lookup by full name
            migration_lookup[m.name] = m
        
        # Sort pending migrations by timestamp to ensure correct order
        sorted_pending = sorted(migrations, key=lambda m: m.name)
        
        # Build execution order respecting dependencies
        execution_order = []
        remaining = sorted_pending.copy()
        max_iterations = len(remaining) * 2  # Prevent infinite loops
        iteration = 0
        
        while remaining and iteration < max_iterations:
            iteration += 1
            made_progress = False
            
            for i, migration in enumerate(remaining):
                can_execute = True
                
                # Check if all dependencies are satisfied
                for dependency in migration.dependencies:
                    dep_migration = migration_lookup.get(dependency)
                    
                    if not dep_migration:
                        raise MigrationValidationError(
                            f"Migration {migration.name} depends on '{dependency}', "
                            f"but it's not found"
                        )
                    
                    # Dependency is satisfied if:
                    # 1. It's already applied, OR
                    # 2. It's already in our execution order
                    is_applied = dep_migration.status == MigrationStatus.APPLIED
                    is_in_execution_order = any(m.name == dep_migration.name for m in execution_order)
                    
                    if not (is_applied or is_in_execution_order):
                        can_execute = False
                        break
                
                if can_execute:
                    execution_order.append(migration)
                    remaining.pop(i)
                    made_progress = True
                    break
            
            if not made_progress:
                # Circular dependency or unresolvable dependency
                unresolved = [m.name for m in remaining]
                raise MigrationValidationError(
                    f"Cannot resolve migration dependencies. "
                    f"Circular dependency or missing dependencies in: {unresolved}"
                )
        
        # Update the migrations list to follow the correct execution order
        migrations.clear()
        migrations.extend(execution_order)
    
    def _extract_short_name(self, migration_name: str) -> str:
        """Extract short name from timestamped migration name."""
        # Remove timestamp prefix (YYYYMMDD_HHMMSS_)
        parts = migration_name.split('_', 2)
        if len(parts) >= 3:
            return parts[2]  # Return everything after second underscore
        return migration_name
    
    @asynccontextmanager
    async def _transaction(self):
        """Context manager for database transactions."""
        await self.db_adapter.begin_transaction()
        try:
            yield
            await self.db_adapter.commit_transaction()
        except Exception:
            await self.db_adapter.rollback_transaction()
            raise
    
    async def _apply_single_migration(self, migration: Migration) -> None:
        """Apply a single migration within a transaction."""
        logger.debug(f"Applying migration: {migration.name}")
        
        # Execute the migration SQL
        await self.db_adapter.execute(migration.up_sql)
        
        # Record migration as applied
        await self._record_migration_applied(migration)
        
        # Update cache
        migration.status = MigrationStatus.APPLIED
        migration.applied_at = datetime.now()
    
    async def _rollback_single_migration(self, migration: Migration) -> None:
        """Rollback a single migration within a transaction."""
        if not migration.down_sql:
            raise MigrationError(f"Migration {migration.name} has no rollback SQL")
        
        logger.debug(f"Rolling back migration: {migration.name}")
        
        # Execute rollback SQL
        await self.db_adapter.execute(migration.down_sql)
        
        # Remove migration record
        await self.db_adapter.execute(
            "DELETE FROM tavo_migrations WHERE name = :name",
            {"name": migration.name}
        )
        
        # Update cache
        migration.status = MigrationStatus.PENDING
        migration.applied_at = None
    
    async def _record_migration_applied(self, migration: Migration) -> None:
        """Record that a migration has been applied."""
        await self.db_adapter.execute(
            """
            INSERT INTO tavo_migrations (name, checksum, applied_at, status)
            VALUES (:name, :checksum, :applied_at, :status)
            """,
            {
                "name": migration.name,
                "checksum": migration.checksum,
                "applied_at": datetime.now().isoformat(),
                "status": MigrationStatus.APPLIED.value
            }
        )
    
    async def _ensure_migrations_table(self) -> None:
        """Ensure the migrations tracking table exists."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS tavo_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL UNIQUE,
            checksum VARCHAR(64) NOT NULL,
            applied_at TIMESTAMP NOT NULL,
            status VARCHAR(20) DEFAULT 'applied',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        await self.db_adapter.execute(create_table_sql)
        logger.debug("Migrations table ensured")
    
    def _create_migration_template(
        self, 
        description: str, 
        up_sql: str, 
        down_sql: str,
        dependencies: List[str]
    ) -> str:
        """Create migration file content from template."""
        deps_comment = f"-- Depends: {', '.join(dependencies)}" if dependencies else ""
        
        return f"""-- Migration: {description}
-- Created: {datetime.now().isoformat()}
{deps_comment}

-- UP
{up_sql}

-- DOWN
{down_sql}
"""


# CLI-style functions for easy integration
async def create_migration(
    migrations_dir: Path,
    name: str,
    description: str = "",
    **kwargs
) -> Path:
    """Convenience function to create a migration."""
    adapter = SQLiteAdapter(":memory:")  # Default adapter
    runner = MigrationRunner(migrations_dir, adapter)
    
    return await runner.create_migration(name, description, **kwargs)


async def apply_all_migrations(migrations_dir: Path, db_path: Path) -> Dict[str, Any]:
    """Convenience function to apply all pending migrations."""
    adapter = SQLiteAdapter(db_path)
    runner = MigrationRunner(migrations_dir, adapter)
    
    try:
        await runner.initialize()
        return await runner.apply_migrations()
    finally:
        await adapter.close()


if __name__ == "__main__":
    # Enhanced example usage
    async def main():
        migrations_dir = Path("migrations")
        db_path = Path("database.db")
        
        # Initialize runner
        adapter = SQLiteAdapter(db_path)
        runner = MigrationRunner(migrations_dir, adapter)
        
        try:
            await runner.initialize()
            
            # Create example migrations
            await runner.create_migration(
                name="create_users_table",
                description="Create users table with basic fields",
                up_sql="""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX idx_users_email ON users(email);
                CREATE INDEX idx_users_username ON users(username);
                """,
                down_sql="""
                DROP INDEX IF EXISTS idx_users_username;
                DROP INDEX IF EXISTS idx_users_email;
                DROP TABLE IF EXISTS users;
                """
            )
            
            await runner.create_migration(
                name="add_user_profile_table",
                description="Add user profiles table",
                up_sql="""
                CREATE TABLE user_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    first_name VARCHAR(50),
                    last_name VARCHAR(50),
                    bio TEXT,
                    avatar_url VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                
                CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
                """,
                down_sql="DROP TABLE IF EXISTS user_profiles;",
                dependencies=["create_users_table"]  # This will now resolve correctly
            )
            
            # Get status
            status = await runner.get_status()
            print(f"\nMigration Status:")
            print(f"Total migrations: {status['total_migrations']}")
            print(f"Pending: {status['pending_count']}")
            print(f"Status breakdown: {status['status_breakdown']}")
            
            # Apply migrations
            print(f"\nApplying migrations...")
            results = await runner.apply_migrations()
            print(f"Applied: {results['applied']}")
            if results['errors']:
                print(f"Errors: {results['errors']}")
            
            # Show final status
            final_status = await runner.get_status()
            print(f"\nFinal Status: {final_status['status_breakdown']}")
            
        finally:
            await adapter.close()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(main())