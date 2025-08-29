"""
Tavo ORM Query Builder

Query builder with basic select/insert/update/delete and async execution.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


@dataclass
class QueryCondition:
    """Represents a WHERE condition in a query."""
    field: str
    operator: str
    value: Any
    
    def to_sql(self) -> Tuple[str, Any]:
        """Convert condition to SQL fragment and parameter."""
        return f"{self.field} {self.operator} ?", self.value


class Q:
    """
    Query condition builder for complex WHERE clauses.
    """
    
    def __init__(self, **kwargs):
        self.conditions: List[QueryCondition] = []
        self.connector = "AND"
        
        for field_name, value in kwargs.items():
            self.conditions.append(QueryCondition(field_name, "=", value))
    
    def __and__(self, other: 'Q') -> 'Q':
        """Combine conditions with AND."""
        combined = Q()
        combined.conditions = self.conditions + other.conditions
        combined.connector = "AND"
        return combined
    
    def __or__(self, other: 'Q') -> 'Q':
        """Combine conditions with OR."""
        combined = Q()
        combined.conditions = self.conditions + other.conditions
        combined.connector = "OR"
        return combined
    
    def to_sql(self) -> Tuple[str, List[Any]]:
        """
        Convert Q object to SQL WHERE clause.
        
        Returns:
            Tuple of (sql_fragment, parameters)
            
        Example:
            >>> q = Q(name="John") & Q(age__gt=18)
            >>> sql, params = q.to_sql()
        """
        if not self.conditions:
            return "", []
        
        sql_parts = []
        parameters = []
        
        for condition in self.conditions:
            sql_part, param = condition.to_sql()
            sql_parts.append(sql_part)
            parameters.append(param)
        
        sql = f" {self.connector} ".join(sql_parts)
        return sql, parameters


class QueryBuilder:
    """
    SQL query builder with fluent interface.
    """
    
    def __init__(self, table_name: str):
        self.table_name = table_name
        self._select_fields: List[str] = ["*"]
        self._where_conditions: List[QueryCondition] = []
        self._order_by: List[Tuple[str, str]] = []
        self._limit_value: Optional[int] = None
        self._offset_value: Optional[int] = None
        self._insert_data: Optional[Dict[str, Any]] = None
        self._update_data: Optional[Dict[str, Any]] = None
        self._query_type: str = "SELECT"
    
    def select(self, *fields: str) -> 'QueryBuilder':
        """
        Specify fields to select.
        
        Args:
            *fields: Field names to select
            
        Returns:
            QueryBuilder instance for chaining
            
        Example:
            >>> query = QueryBuilder("users").select("name", "email")
        """
        self._select_fields = list(fields) if fields else ["*"]
        self._query_type = "SELECT"
        return self
    
    def where(self, field: str, value: Any, operator: str = "=") -> 'QueryBuilder':
        """
        Add WHERE condition.
        
        Args:
            field: Field name
            value: Value to compare
            operator: Comparison operator
            
        Returns:
            QueryBuilder instance for chaining
        """
        condition = QueryCondition(field, operator, value)
        self._where_conditions.append(condition)
        return self
    
    def where_q(self, q: Q) -> 'QueryBuilder':
        """
        Add complex WHERE conditions using Q object.
        
        Args:
            q: Q object with conditions
            
        Returns:
            QueryBuilder instance for chaining
        """
        self._where_conditions.extend(q.conditions)
        return self
    
    def order_by(self, field: str, direction: str = "ASC") -> 'QueryBuilder':
        """
        Add ORDER BY clause.
        
        Args:
            field: Field to order by
            direction: Sort direction ("ASC" or "DESC")
            
        Returns:
            QueryBuilder instance for chaining
        """
        self._order_by.append((field, direction.upper()))
        return self
    
    def limit(self, count: int) -> 'QueryBuilder':
        """
        Add LIMIT clause.
        
        Args:
            count: Maximum number of results
            
        Returns:
            QueryBuilder instance for chaining
        """
        self._limit_value = count
        return self
    
    def offset(self, count: int) -> 'QueryBuilder':
        """
        Add OFFSET clause.
        
        Args:
            count: Number of results to skip
            
        Returns:
            QueryBuilder instance for chaining
        """
        self._offset_value = count
        return self
    
    def insert(self, data: Dict[str, Any]) -> 'QueryBuilder':
        """
        Prepare INSERT query.
        
        Args:
            data: Data to insert
            
        Returns:
            QueryBuilder instance for chaining
        """
        self._insert_data = data
        self._query_type = "INSERT"
        return self
    
    def update(self, data: Dict[str, Any]) -> 'QueryBuilder':
        """
        Prepare UPDATE query.
        
        Args:
            data: Data to update
            
        Returns:
            QueryBuilder instance for chaining
        """
        self._update_data = data
        self._query_type = "UPDATE"
        return self
    
    def delete(self) -> 'QueryBuilder':
        """
        Prepare DELETE query.
        
        Returns:
            QueryBuilder instance for chaining
        """
        self._query_type = "DELETE"
        return self
    
    def build_sql(self) -> Tuple[str, List[Any]]:
        """
        Build SQL query and parameters.
        
        Returns:
            Tuple of (sql_query, parameters)
            
        Example:
            >>> query = QueryBuilder("users").where("age", 18, ">")
            >>> sql, params = query.build_sql()
        """
        if self._query_type == "SELECT":
            return self._build_select_sql()
        elif self._query_type == "INSERT":
            return self._build_insert_sql()
        elif self._query_type == "UPDATE":
            return self._build_update_sql()
        elif self._query_type == "DELETE":
            return self._build_delete_sql()
        else:
            raise ValueError(f"Unknown query type: {self._query_type}")
    
    def _build_select_sql(self) -> Tuple[str, List[Any]]:
        """Build SELECT SQL query."""
        fields = ", ".join(self._select_fields)
        sql = f"SELECT {fields} FROM {self.table_name}"
        parameters = []
        
        # Add WHERE clause
        if self._where_conditions:
            where_parts = []
            for condition in self._where_conditions:
                sql_part, param = condition.to_sql()
                where_parts.append(sql_part)
                parameters.append(param)
            
            sql += " WHERE " + " AND ".join(where_parts)
        
        # Add ORDER BY
        if self._order_by:
            order_parts = [f"{field} {direction}" for field, direction in self._order_by]
            sql += " ORDER BY " + ", ".join(order_parts)
        
        # Add LIMIT and OFFSET
        if self._limit_value:
            sql += f" LIMIT {self._limit_value}"
        
        if self._offset_value:
            sql += f" OFFSET {self._offset_value}"
        
        return sql, parameters
    
    def _build_insert_sql(self) -> Tuple[str, List[Any]]:
        """Build INSERT SQL query."""
        if not self._insert_data:
            raise ValueError("No data provided for INSERT")
        
        fields = list(self._insert_data.keys())
        placeholders = ", ".join(["?" for _ in fields])
        field_names = ", ".join(fields)
        
        sql = f"INSERT INTO {self.table_name} ({field_names}) VALUES ({placeholders})"
        parameters = list(self._insert_data.values())
        
        return sql, parameters
    
    def _build_update_sql(self) -> Tuple[str, List[Any]]:
        """Build UPDATE SQL query."""
        if not self._update_data:
            raise ValueError("No data provided for UPDATE")
        
        set_parts = []
        parameters = []
        
        for field, value in self._update_data.items():
            set_parts.append(f"{field} = ?")
            parameters.append(value)
        
        sql = f"UPDATE {self.table_name} SET {', '.join(set_parts)}"
        
        # Add WHERE clause
        if self._where_conditions:
            where_parts = []
            for condition in self._where_conditions:
                sql_part, param = condition.to_sql()
                where_parts.append(sql_part)
                parameters.append(param)
            
            sql += " WHERE " + " AND ".join(where_parts)
        
        return sql, parameters
    
    def _build_delete_sql(self) -> Tuple[str, List[Any]]:
        """Build DELETE SQL query."""
        sql = f"DELETE FROM {self.table_name}"
        parameters = []
        
        # Add WHERE clause
        if self._where_conditions:
            where_parts = []
            for condition in self._where_conditions:
                sql_part, param = condition.to_sql()
                where_parts.append(sql_part)
                parameters.append(param)
            
            sql += " WHERE " + " AND ".join(where_parts)
        
        return sql, parameters
    
    async def execute(self) -> List[Dict[str, Any]]:
        """
        Execute the query and return results.
        
        Returns:
            List of result rows as dictionaries
            
        Raises:
            Exception: If query execution fails
        """
        sql, parameters = self.build_sql()
        logger.debug(f"Executing SQL: {sql} with params: {parameters}")
        
        # TODO: implement actual database execution
        # This would use a database connection to execute the query
        
        # Mock implementation
        if self._query_type == "SELECT":
            return [{"id": 1, "name": "Mock User", "email": "mock@example.com"}]
        else:
            return [{"affected_rows": 1}]
    
    def __str__(self) -> str:
        """String representation of query."""
        sql, params = self.build_sql()
        return f"Query: {sql} | Params: {params}"


class DatabaseConnection:
    """
    Database connection manager for query execution.
    """
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._connection = None
    
    async def connect(self) -> None:
        """Establish database connection."""
        # TODO: implement actual database connection
        logger.info("Database connection established")
    
    async def disconnect(self) -> None:
        """Close database connection."""
        # TODO: implement connection cleanup
        logger.info("Database connection closed")
    
    async def execute_query(self, sql: str, parameters: List[Any]) -> List[Dict[str, Any]]:
        """
        Execute SQL query with parameters.
        
        Args:
            sql: SQL query string
            parameters: Query parameters
            
        Returns:
            Query results
        """
        # TODO: implement actual query execution
        logger.debug(f"Executing: {sql}")
        return []


if __name__ == "__main__":
    # Example usage
    async def main():
        # Build a SELECT query
        query = (QueryBuilder("users")
                .select("name", "email")
                .where("age", 18, ">")
                .where("active", True)
                .order_by("name")
                .limit(10))
        
        sql, params = query.build_sql()
        print(f"SQL: {sql}")
        print(f"Parameters: {params}")
        
        # Build an INSERT query
        insert_query = QueryBuilder("users").insert({
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30
        })
        
        insert_sql, insert_params = insert_query.build_sql()
        print(f"Insert SQL: {insert_sql}")
        print(f"Insert Parameters: {insert_params}")
    
    asyncio.run(main())

# Unit tests as comments:
# 1. test_query_builder_select() - verify SELECT query building with various conditions
# 2. test_query_builder_insert() - test INSERT query generation
# 3. test_q_object_combinations() - verify Q object AND/OR logic works correctly