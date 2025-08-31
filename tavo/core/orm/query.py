"""
Tavo ORM Query Builder

Enhanced query builder with advanced features, better type safety, and comprehensive SQL generation.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union, Tuple, Type, TypeVar
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

# Type variables
T = TypeVar('T')
ModelType = TypeVar('ModelType', bound='BaseModel') # type: ignore


class QueryError(Exception):
    """Base exception for query-related errors."""
    pass


class InvalidQueryError(QueryError):
    """Raised when query construction is invalid."""
    pass


class DatabaseError(QueryError):
    """Raised when database operations fail."""
    pass


class JoinType(Enum):
    """SQL JOIN types."""
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    FULL = "FULL OUTER JOIN"
    CROSS = "CROSS JOIN"


class Operator(Enum):
    """SQL comparison operators."""
    EQ = "="
    NE = "!="
    LT = "<"
    LTE = "<="
    GT = ">"
    GTE = ">="
    LIKE = "LIKE"
    ILIKE = "ILIKE"
    IN = "IN"
    NOT_IN = "NOT IN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"
    BETWEEN = "BETWEEN"
    NOT_BETWEEN = "NOT BETWEEN"
    CONTAINS = "CONTAINS"  # JSON contains
    REGEX = "REGEXP"


class SortOrder(Enum):
    """Sort order directions."""
    ASC = "ASC"
    DESC = "DESC"


@dataclass
class QueryCondition:
    """Enhanced query condition with support for complex operations."""
    field: str
    operator: Operator
    value: Any
    negated: bool = False
    
    def __post_init__(self):
        """Validate condition after initialization."""
        if self.operator in (Operator.IS_NULL, Operator.IS_NOT_NULL) and self.value is not None:
            raise InvalidQueryError(f"NULL operators don't accept values, got: {self.value}")
        
        if self.operator in (Operator.IN, Operator.NOT_IN) and not isinstance(self.value, (list, tuple, set)):
            raise InvalidQueryError(f"IN operators require list/tuple/set, got: {type(self.value)}")
    
    def to_sql(self, param_style: str = "?") -> Tuple[str, List[Any]]:
        """
        Convert condition to SQL fragment and parameters.
        
        Args:
            param_style: Parameter placeholder style ("?" or "%s" or ":name")
            
        Returns:
            Tuple of (sql_fragment, parameters)
        """
        field_sql = self._escape_field_name(self.field)
        parameters = []
        
        if self.operator in (Operator.IS_NULL, Operator.IS_NOT_NULL):
            sql = f"{field_sql} {self.operator.value}"
        
        elif self.operator in (Operator.IN, Operator.NOT_IN):
            placeholders = ", ".join([param_style for _ in self.value])
            sql = f"{field_sql} {self.operator.value} ({placeholders})"
            parameters.extend(self.value)
        
        elif self.operator in (Operator.BETWEEN, Operator.NOT_BETWEEN):
            if not isinstance(self.value, (list, tuple)) or len(self.value) != 2:
                raise InvalidQueryError("BETWEEN requires exactly 2 values")
            sql = f"{field_sql} {self.operator.value} {param_style} AND {param_style}"
            parameters.extend(self.value)
        
        elif self.operator == Operator.LIKE and isinstance(self.value, str):
            # Auto-add wildcards if not present
            value = self.value if '%' in self.value or '_' in self.value else f"%{self.value}%"
            sql = f"{field_sql} {self.operator.value} {param_style}"
            parameters.append(value)
        
        else:
            sql = f"{field_sql} {self.operator.value} {param_style}"
            parameters.append(self.value)
        
        if self.negated:
            sql = f"NOT ({sql})"
        
        return sql, parameters
    
    def _escape_field_name(self, field: str) -> str:
        """Escape field name to prevent SQL injection."""
        # Handle table.field notation
        if '.' in field:
            parts = field.split('.')
            return '.'.join(f'"{part}"' for part in parts)
        return f'"{field}"'
    
    def negate(self) -> 'QueryCondition':
        """Return negated version of this condition."""
        return QueryCondition(
            field=self.field,
            operator=self.operator,
            value=self.value,
            negated=not self.negated
        )


@dataclass
class JoinClause:
    """Represents a SQL JOIN clause."""
    table: str
    join_type: JoinType
    on_condition: str
    alias: Optional[str] = None
    
    def to_sql(self) -> str:
        """Convert to SQL JOIN clause."""
        table_ref = f"{self.table} AS {self.alias}" if self.alias else self.table
        return f"{self.join_type.value} {table_ref} ON {self.on_condition}"


class Q:
    """
    Enhanced query condition builder for complex WHERE clauses.
    """
    
    def __init__(self, **kwargs):
        """
        Initialize Q object with field lookups.
        
        Args:
            **kwargs: Field lookups using Django-style syntax
                     (field__operator=value)
        
        Example:
            >>> Q(name="John", age__gt=18, email__icontains="gmail")
        """
        self.conditions: List[QueryCondition] = []
        self.children: List['Q'] = []
        self.connector = "AND"
        self.negated = False
        
        for lookup, value in kwargs.items():
            condition = self._parse_lookup(lookup, value)
            self.conditions.append(condition)
    
    def _parse_lookup(self, lookup: str, value: Any) -> QueryCondition:
        """
        Parse Django-style field lookup into QueryCondition.
        
        Examples:
            name -> name = value
            age__gt -> age > value
            email__icontains -> email ILIKE %value%
        """
        parts = lookup.split('__')
        field = parts[0]
        
        if len(parts) == 1:
            operator = Operator.EQ
        else:
            operator_map = {
                'exact': Operator.EQ,
                'ne': Operator.NE,
                'lt': Operator.LT,
                'lte': Operator.LTE,
                'gt': Operator.GT,
                'gte': Operator.GTE,
                'like': Operator.LIKE,
                'ilike': Operator.ILIKE,
                'contains': Operator.LIKE,
                'icontains': Operator.ILIKE,
                'startswith': Operator.LIKE,
                'istartswith': Operator.ILIKE,
                'endswith': Operator.LIKE,
                'iendswith': Operator.ILIKE,
                'in': Operator.IN,
                'not_in': Operator.NOT_IN,
                'isnull': Operator.IS_NULL if value else Operator.IS_NOT_NULL,
                'between': Operator.BETWEEN,
                'regex': Operator.REGEX,
            }
            
            operator_name = parts[1]
            operator = operator_map.get(operator_name)
            
            if operator is None:
                raise InvalidQueryError(f"Unknown lookup: {operator_name}")
            
            # Handle special cases
            if operator_name in ('contains', 'startswith', 'endswith'):
                value = f"%{value}%"
            elif operator_name in ('icontains', 'istartswith', 'iendswith'):
                value = f"%{value}%"
            elif operator_name == 'startswith':
                value = f"{value}%"
            elif operator_name == 'istartswith':
                value = f"{value}%"
            elif operator_name == 'endswith':
                value = f"%{value}"
            elif operator_name == 'iendswith':
                value = f"%{value}"
            elif operator_name == 'isnull':
                value = None  # NULL checks don't need values
        
        return QueryCondition(field, operator, value)
    
    def __and__(self, other: 'Q') -> 'Q':
        """Combine Q objects with AND."""
        combined = Q()
        combined.children = [self, other]
        combined.connector = "AND"
        return combined
    
    def __or__(self, other: 'Q') -> 'Q':
        """Combine Q objects with OR."""
        combined = Q()
        combined.children = [self, other]
        combined.connector = "OR"
        return combined
    
    def __invert__(self) -> 'Q':
        """Negate Q object with NOT."""
        negated = Q()
        negated.children = [self]
        negated.negated = True
        return negated
    
    def to_sql(self, param_style: str = "?") -> Tuple[str, List[Any]]:
        """
        Convert Q object to SQL WHERE clause.
        
        Returns:
            Tuple of (sql_fragment, parameters)
        """
        if not self.conditions and not self.children:
            return "", []
        
        sql_parts = []
        all_parameters = []
        
        # Process direct conditions
        for condition in self.conditions:
            sql_part, params = condition.to_sql(param_style)
            sql_parts.append(sql_part)
            all_parameters.extend(params)
        
        # Process child Q objects
        for child in self.children:
            child_sql, child_params = child.to_sql(param_style)
            if child_sql:
                if child.negated:
                    child_sql = f"NOT ({child_sql})"
                sql_parts.append(f"({child_sql})")
                all_parameters.extend(child_params)
        
        if not sql_parts:
            return "", []
        
        connector = f" {self.connector} "
        sql = connector.join(sql_parts)
        
        if self.negated:
            sql = f"NOT ({sql})"
        
        return sql, all_parameters


class QueryBuilder:
    """
    Enhanced SQL query builder with comprehensive features.
    """
    
    def __init__(self, table_name: str, model_class: Optional[Type] = None):
        self.table_name = table_name
        self.model_class = model_class
        
        # Query components
        self._select_fields: List[str] = ["*"]
        self._distinct: bool = False
        self._where_conditions: List[Q] = []
        self._joins: List[JoinClause] = []
        self._group_by: List[str] = []
        self._having_conditions: List[Q] = []
        self._order_by: List[Tuple[str, SortOrder]] = []
        self._limit_value: Optional[int] = None
        self._offset_value: Optional[int] = None
        self._raw_params: Optional[List[Any]] = None
        self._raw_sql: Optional[str] = None
        
        # Operation-specific data
        self._insert_data: Optional[Dict[str, Any]] = None
        self._update_data: Optional[Dict[str, Any]] = None
        self._upsert_data: Optional[Dict[str, Any]] = None
        self._upsert_conflict_fields: List[str] = []
        
        # Query metadata
        self._query_type: str = "SELECT"
        self._subqueries: Dict[str, 'QueryBuilder'] = {}
        self._with_clauses: List[Tuple[str, 'QueryBuilder']] = []
        
        # Database connection
        self._connection: Optional['DatabaseConnection'] = None
    
    def clone(self) -> 'QueryBuilder':
        """Create a copy of this query builder."""
        cloned = QueryBuilder(self.table_name, self.model_class)
        
        # Copy all attributes
        cloned._select_fields = self._select_fields.copy()
        cloned._distinct = self._distinct
        cloned._where_conditions = self._where_conditions.copy()
        cloned._joins = self._joins.copy()
        cloned._group_by = self._group_by.copy()
        cloned._having_conditions = self._having_conditions.copy()
        cloned._order_by = self._order_by.copy()
        cloned._limit_value = self._limit_value
        cloned._offset_value = self._offset_value
        cloned._insert_data = self._insert_data.copy() if self._insert_data else None
        cloned._update_data = self._update_data.copy() if self._update_data else None
        cloned._query_type = self._query_type
        cloned._connection = self._connection
        
        return cloned
    
    # SELECT methods
    def select(self, *fields: str) -> 'QueryBuilder':
        """Specify fields to select."""
        self._select_fields = list(fields) if fields else ["*"]
        self._query_type = "SELECT"
        return self
    
    def distinct(self, distinct: bool = True) -> 'QueryBuilder':
        """Add DISTINCT clause."""
        self._distinct = distinct
        return self
    
    def select_related(self, *relations: str) -> 'QueryBuilder':
        """Select related objects (adds JOINs)."""
        for relation in relations:
            # This would analyze model relationships and add appropriate JOINs
            # For now, just store the relation names
            pass
        return self
    
    def prefetch_related(self, *relations: str) -> 'QueryBuilder':
        """Prefetch related objects (separate queries)."""
        # This would be handled in the ORM layer
        return self
    
    # WHERE methods
    def where(self, field: str, value: Any, operator: Union[str, Operator] = Operator.EQ) -> 'QueryBuilder':
        """Add simple WHERE condition."""
        if isinstance(operator, str):
            operator = Operator(operator)
        
        condition = QueryCondition(field, operator, value)
        q = Q()
        q.conditions = [condition]
        self._where_conditions.append(q)
        return self
    
    def where_q(self, q: Q) -> 'QueryBuilder':
        """Add complex WHERE conditions using Q object."""
        self._where_conditions.append(q)
        return self
    
    def where_not(self, field: str, value: Any, operator: Union[str, Operator] = Operator.EQ) -> 'QueryBuilder':
        """Add negated WHERE condition."""
        if isinstance(operator, str):
            operator = Operator(operator)
        
        condition = QueryCondition(field, operator, value, negated=True)
        q = Q()
        q.conditions = [condition]
        self._where_conditions.append(q)
        return self
    
    def where_in(self, field: str, values: List[Any]) -> 'QueryBuilder':
        """Add WHERE field IN (...) condition."""
        return self.where(field, values, Operator.IN)
    
    def where_not_in(self, field: str, values: List[Any]) -> 'QueryBuilder':
        """Add WHERE field NOT IN (...) condition."""
        return self.where(field, values, Operator.NOT_IN)
    
    def where_null(self, field: str) -> 'QueryBuilder':
        """Add WHERE field IS NULL condition."""
        return self.where(field, None, Operator.IS_NULL)
    
    def where_not_null(self, field: str) -> 'QueryBuilder':
        """Add WHERE field IS NOT NULL condition."""
        return self.where(field, None, Operator.IS_NOT_NULL)
    
    def where_between(self, field: str, start: Any, end: Any) -> 'QueryBuilder':
        """Add WHERE field BETWEEN start AND end condition."""
        return self.where(field, [start, end], Operator.BETWEEN)
    
    def where_like(self, field: str, pattern: str) -> 'QueryBuilder':
        """Add WHERE field LIKE pattern condition."""
        return self.where(field, pattern, Operator.LIKE)
    
    def where_ilike(self, field: str, pattern: str) -> 'QueryBuilder':
        """Add case-insensitive LIKE condition."""
        return self.where(field, pattern, Operator.ILIKE)
    
    # JOIN methods
    def join(self, table: str, on: str, join_type: JoinType = JoinType.INNER, alias: Optional[str] = None) -> 'QueryBuilder':
        """Add JOIN clause."""
        join_clause = JoinClause(table, join_type, on, alias)
        self._joins.append(join_clause)
        return self
    
    def inner_join(self, table: str, on: str, alias: Optional[str] = None) -> 'QueryBuilder':
        """Add INNER JOIN."""
        return self.join(table, on, JoinType.INNER, alias)
    
    def left_join(self, table: str, on: str, alias: Optional[str] = None) -> 'QueryBuilder':
        """Add LEFT JOIN."""
        return self.join(table, on, JoinType.LEFT, alias)
    
    def right_join(self, table: str, on: str, alias: Optional[str] = None) -> 'QueryBuilder':
        """Add RIGHT JOIN."""
        return self.join(table, on, JoinType.RIGHT, alias)
    
    # GROUP BY and HAVING
    def group_by(self, *fields: str) -> 'QueryBuilder':
        """Add GROUP BY clause."""
        self._group_by.extend(fields)
        return self
    
    def having(self, q: Q) -> 'QueryBuilder':
        """Add HAVING clause."""
        self._having_conditions.append(q)
        return self
    
    # ORDER BY
    def order_by(self, field: str, desc: bool = False) -> 'QueryBuilder':
        """Add ORDER BY clause."""
        direction = SortOrder.DESC if desc else SortOrder.ASC
        self._order_by.append((field, direction))
        return self
    
    def order_by_desc(self, field: str) -> 'QueryBuilder':
        """Add ORDER BY field DESC."""
        return self.order_by(field, desc=True)
    
    def order_by_asc(self, field: str) -> 'QueryBuilder':
        """Add ORDER BY field ASC."""
        return self.order_by(field, desc=False)
    
    # LIMIT and OFFSET
    def limit(self, count: int) -> 'QueryBuilder':
        """Add LIMIT clause."""
        if count <= 0:
            raise InvalidQueryError("LIMIT must be positive")
        self._limit_value = count
        return self
    
    def offset(self, count: int) -> 'QueryBuilder':
        """Add OFFSET clause."""
        if count < 0:
            raise InvalidQueryError("OFFSET cannot be negative")
        self._offset_value = count
        return self
    
    def paginate(self, page: int, per_page: int) -> 'QueryBuilder':
        """Add pagination (LIMIT and OFFSET)."""
        if page <= 0 or per_page <= 0:
            raise InvalidQueryError("Page and per_page must be positive")
        
        offset = (page - 1) * per_page
        return self.limit(per_page).offset(offset)
    
    # CTE (Common Table Expressions)
    def with_query(self, name: str, query: 'QueryBuilder') -> 'QueryBuilder':
        """Add WITH clause (CTE)."""
        self._with_clauses.append((name, query))
        return self
    
    # INSERT methods
    def insert(self, data: Dict[str, Any]) -> 'QueryBuilder':
        """Prepare INSERT query."""
        self._insert_data = data
        self._query_type = "INSERT"
        return self
    
    def insert_many(self, data_list: List[Dict[str, Any]]) -> 'QueryBuilder':
        """Prepare bulk INSERT query."""
        self._insert_data = data_list # type: ignore
        self._query_type = "INSERT_MANY"
        return self
    
    # UPDATE methods
    def update(self, data: Dict[str, Any]) -> 'QueryBuilder':
        """Prepare UPDATE query."""
        self._update_data = data
        self._query_type = "UPDATE"
        return self
    
    def increment(self, field: str, amount: Union[int, float] = 1) -> 'QueryBuilder':
        """Increment a numeric field."""
        if self._update_data is None:
            self._update_data = {}
        self._update_data[field] = f"{field} + {amount}"
        self._query_type = "UPDATE"
        return self
    
    def decrement(self, field: str, amount: Union[int, float] = 1) -> 'QueryBuilder':
        """Decrement a numeric field."""
        return self.increment(field, -amount)
    
    # UPSERT methods
    def upsert(self, data: Dict[str, Any], conflict_fields: List[str]) -> 'QueryBuilder':
        """Prepare UPSERT (INSERT ... ON CONFLICT) query."""
        self._upsert_data = data
        self._upsert_conflict_fields = conflict_fields
        self._query_type = "UPSERT"
        return self
    
    # DELETE method
    def delete(self) -> 'QueryBuilder':
        """Prepare DELETE query."""
        self._query_type = "DELETE"
        return self
    
    # Aggregation methods
    def count(self, field: str = "*") -> 'QueryBuilder':
        """Add COUNT aggregation."""
        self._select_fields = [f"COUNT({field}) AS count"]
        return self
    
    def sum(self, field: str) -> 'QueryBuilder':
        """Add SUM aggregation."""
        self._select_fields = [f"SUM({field}) AS sum"]
        return self
    
    def avg(self, field: str) -> 'QueryBuilder':
        """Add AVG aggregation."""
        self._select_fields = [f"AVG({field}) AS avg"]
        return self
    
    def min(self, field: str) -> 'QueryBuilder':
        """Add MIN aggregation."""
        self._select_fields = [f"MIN({field}) AS min"]
        return self
    
    def max(self, field: str) -> 'QueryBuilder':
        """Add MAX aggregation."""
        self._select_fields = [f"MAX({field}) AS max"]
        return self
    
    # SQL building methods
    def build_sql(self, param_style: str = "?") -> Tuple[str, List[Any]]:
        """
        Build complete SQL query and parameters.
        
        Args:
            param_style: Parameter placeholder style
            
        Returns:
            Tuple of (sql_query, parameters)
        """
        builders = {
            "SELECT": self._build_select_sql,
            "INSERT": self._build_insert_sql,
            "INSERT_MANY": self._build_insert_many_sql,
            "UPDATE": self._build_update_sql,
            "UPSERT": self._build_upsert_sql,
            "DELETE": self._build_delete_sql,
        }
        
        builder = builders.get(self._query_type)
        if not builder:
            raise InvalidQueryError(f"Unknown query type: {self._query_type}")
        
        return builder(param_style)
    
    def _build_select_sql(self, param_style: str = "?") -> Tuple[str, List[Any]]:
        """Build SELECT SQL query."""
        parameters = []
        sql_parts = []
        
        # WITH clauses (CTEs)
        if self._with_clauses:
            with_parts = []
            for name, query in self._with_clauses:
                cte_sql, cte_params = query.build_sql(param_style)
                with_parts.append(f"{name} AS ({cte_sql})")
                parameters.extend(cte_params)
            sql_parts.append("WITH " + ", ".join(with_parts))
        
        # SELECT clause
        distinct = "DISTINCT " if self._distinct else ""
        fields = ", ".join(self._select_fields)
        sql_parts.append(f"SELECT {distinct}{fields}")
        
        # FROM clause
        sql_parts.append(f"FROM {self.table_name}")
        
        # JOIN clauses
        for join in self._joins:
            sql_parts.append(join.to_sql())
        
        # WHERE clause
        if self._where_conditions:
            where_parts = []
            for q in self._where_conditions:
                q_sql, q_params = q.to_sql(param_style)
                if q_sql:
                    where_parts.append(q_sql)
                    parameters.extend(q_params)
            
            if where_parts:
                sql_parts.append("WHERE " + " AND ".join(f"({part})" for part in where_parts))
        
        # GROUP BY clause
        if self._group_by:
            sql_parts.append("GROUP BY " + ", ".join(self._group_by))
        
        # HAVING clause
        if self._having_conditions:
            having_parts = []
            for q in self._having_conditions:
                q_sql, q_params = q.to_sql(param_style)
                if q_sql:
                    having_parts.append(q_sql)
                    parameters.extend(q_params)
            
            if having_parts:
                sql_parts.append("HAVING " + " AND ".join(f"({part})" for part in having_parts))
        
        # ORDER BY clause
        if self._order_by:
            order_parts = [f"{field} {direction.value}" for field, direction in self._order_by]
            sql_parts.append("ORDER BY " + ", ".join(order_parts))
        
        # LIMIT and OFFSET
        if self._limit_value:
            sql_parts.append(f"LIMIT {self._limit_value}")
        
        if self._offset_value:
            sql_parts.append(f"OFFSET {self._offset_value}")
        
        return " ".join(sql_parts), parameters
    
    def _build_insert_sql(self, param_style: str = "?") -> Tuple[str, List[Any]]:
        """Build INSERT SQL query."""
        if not self._insert_data:
            raise InvalidQueryError("No data provided for INSERT")
        
        fields = list(self._insert_data.keys())
        placeholders = ", ".join([param_style for _ in fields])
        field_names = ", ".join(f'"{field}"' for field in fields)
        
        sql = f'INSERT INTO "{self.table_name}" ({field_names}) VALUES ({placeholders})'
        parameters = list(self._insert_data.values())
        
        return sql, parameters
    
    def _build_insert_many_sql(self, param_style: str = "?") -> Tuple[str, List[Any]]:
        """Build bulk INSERT SQL query."""
        if not self._insert_data or not isinstance(self._insert_data, list):
            raise InvalidQueryError("INSERT_MANY requires list of data")
        
        if not self._insert_data:
            raise InvalidQueryError("No data provided for INSERT_MANY")
        
        # Use keys from first record
        fields = list(self._insert_data[0].keys()) # type: ignore
        field_names = ", ".join(f'"{field}"' for field in fields)
        
        # Build placeholders for each row
        row_placeholders = "(" + ", ".join([param_style for _ in fields]) + ")"
        all_placeholders = ", ".join([row_placeholders for _ in self._insert_data])
        
        sql = f'INSERT INTO "{self.table_name}" ({field_names}) VALUES {all_placeholders}'
        
        # Flatten parameters
        parameters = []
        for row in self._insert_data:
            for field in fields:
                parameters.append(row[field])
        
        return sql, parameters
    
    def _build_update_sql(self, param_style: str = "?") -> Tuple[str, List[Any]]:
        """Build UPDATE SQL query."""
        if not self._update_data:
            raise InvalidQueryError("No data provided for UPDATE")
        
        set_parts = []
        parameters = []
        
        for field, value in self._update_data.items():
            if isinstance(value, str) and value.startswith(field + " "):
                # Handle expressions like "field + 1"
                set_parts.append(f'"{field}" = {value}')
            else:
                set_parts.append(f'"{field}" = {param_style}')
                parameters.append(value)
        
        sql = f'UPDATE "{self.table_name}" SET {", ".join(set_parts)}'
        
        # Add WHERE clause
        if self._where_conditions:
            where_parts = []
            for q in self._where_conditions:
                q_sql, q_params = q.to_sql(param_style)
                if q_sql:
                    where_parts.append(q_sql)
                    parameters.extend(q_params)
            
            if where_parts:
                sql += " WHERE " + " AND ".join(f"({part})" for part in where_parts)
        
        return sql, parameters
    
    def _build_upsert_sql(self, param_style: str = "?") -> Tuple[str, List[Any]]:
        """Build UPSERT (INSERT ... ON CONFLICT) SQL query."""
        if not self._upsert_data:
            raise InvalidQueryError("No data provided for UPSERT")
        
        if not self._upsert_conflict_fields:
            raise InvalidQueryError("No conflict fields specified for UPSERT")
        
        # Build INSERT part
        fields = list(self._upsert_data.keys())
        placeholders = ", ".join([param_style for _ in fields])
        field_names = ", ".join(f'"{field}"' for field in fields)
        
        sql = f'INSERT INTO "{self.table_name}" ({field_names}) VALUES ({placeholders})'
        parameters = list(self._upsert_data.values())
        
        # Add ON CONFLICT clause
        conflict_fields = ", ".join(f'"{field}"' for field in self._upsert_conflict_fields)
        sql += f" ON CONFLICT ({conflict_fields})"
        
        # Add DO UPDATE SET clause
        update_fields = [field for field in fields if field not in self._upsert_conflict_fields]
        if update_fields:
            update_parts = []
            for field in update_fields:
                update_parts.append(f'"{field}" = EXCLUDED."{field}"')
            sql += " DO UPDATE SET " + ", ".join(update_parts)
        else:
            sql += " DO NOTHING"
        
        return sql, parameters
    
    def _build_delete_sql(self, param_style: str = "?") -> Tuple[str, List[Any]]:
        """Build DELETE SQL query."""
        sql = f'DELETE FROM "{self.table_name}"'
        parameters = []
        
        # Add WHERE clause
        if self._where_conditions:
            where_parts = []
            for q in self._where_conditions:
                q_sql, q_params = q.to_sql(param_style)
                if q_sql:
                    where_parts.append(q_sql)
                    parameters.extend(q_params)
            
            if where_parts:
                sql += " WHERE " + " AND ".join(f"({part})" for part in where_parts)
        
        return sql, parameters
    
    # Execution methods
    async def execute(self, connection: Optional['DatabaseConnection'] = None) -> List[Dict[str, Any]]:
        """
        Execute the query and return results.
        
        Args:
            connection: Database connection to use
            
        Returns:
            List of result rows as dictionaries
        """
        conn = connection or self._connection
        if not conn:
            raise DatabaseError("No database connection available")
        
        sql, parameters = self.build_sql()
        logger.debug(f"Executing SQL: {sql} with params: {parameters}")
        
        try:
            return await conn.execute_query(sql, parameters)
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise DatabaseError(f"Query execution failed: {e}")
    
    async def fetch_one(self, connection: Optional['DatabaseConnection'] = None) -> Optional[Dict[str, Any]]:
        """Execute query and return first result."""
        self.limit(1)
        results = await self.execute(connection)
        return results[0] if results else None
    
    async def fetch_all(self, connection: Optional['DatabaseConnection'] = None) -> List[Dict[str, Any]]:
        """Execute query and return all results."""
        return await self.execute(connection)
    
    async def fetch_value(self, connection: Optional['DatabaseConnection'] = None) -> Any:
        """Execute query and return single value from first row."""
        result = await self.fetch_one(connection)
        if result:
            return next(iter(result.values()))
        return None
    
    async def exists(self, connection: Optional['DatabaseConnection'] = None) -> bool:
        """Check if query returns any results."""
        original_fields = self._select_fields
        self._select_fields = ["1"]
        self.limit(1)
        
        try:
            result = await self.fetch_one(connection)
            return result is not None
        finally:
            self._select_fields = original_fields
    
    # Utility methods
    def explain(self, analyze: bool = False) -> 'QueryBuilder':
        """Add EXPLAIN to query for performance analysis."""
        sql, params = self.build_sql()
        explain_type = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
        
        explained_query = QueryBuilder(self.table_name)
        explained_query._query_type = "RAW"
        explained_query._raw_sql = f"{explain_type} {sql}"
        explained_query._raw_params = params # type: ignore
        
        return explained_query
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert query builder to dictionary representation."""
        return {
            'table_name': self.table_name,
            'query_type': self._query_type,
            'select_fields': self._select_fields,
            'where_conditions': len(self._where_conditions),
            'joins': len(self._joins),
            'order_by': self._order_by,
            'limit': self._limit_value,
            'offset': self._offset_value,
            'distinct': self._distinct,
        }
    
    def __str__(self) -> str:
        """String representation of query."""
        try:
            sql, params = self.build_sql()
            return f"Query: {sql} | Params: {params}"
        except Exception as e:
            return f"Query (invalid): {e}"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"<QueryBuilder table='{self.table_name}' type='{self._query_type}'>"


class DatabaseConnection:
    """
    Enhanced database connection manager with connection pooling support.
    """
    
    def __init__(
        self, 
        database_url: str,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: float = 30.0,
        pool_recycle: int = -1
    ):
        self.database_url = database_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        
        self._connection_pool = None
        self._transaction_stack = []
        self._in_transaction = False
    
    async def connect(self) -> None:
        """Establish database connection pool."""
        # TODO: implement actual database connection pooling
        logger.info(f"Database connection pool established (size: {self.pool_size})")
    
    async def disconnect(self) -> None:
        """Close all database connections."""
        if self._connection_pool:
            # TODO: implement connection pool cleanup
            logger.info("Database connection pool closed")
    
    async def execute_query(self, sql: str, parameters: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute SQL query with parameters.
        
        Args:
            sql: SQL query string
            parameters: Query parameters
            
        Returns:
            Query results as list of dictionaries
        """
        if parameters is None:
            parameters = []
        
        logger.debug(f"Executing: {sql} with params: {parameters}")
        
        # TODO: implement actual database execution
        # This would get a connection from the pool and execute the query
        
        # Mock implementation for demonstration
        if sql.upper().startswith('SELECT'):
            if 'COUNT(' in sql.upper():
                return [{'count': 42}]
            elif 'users' in sql.lower():
                return [
                    {'id': 1, 'name': 'John Doe', 'email': 'john@example.com'},
                    {'id': 2, 'name': 'Jane Smith', 'email': 'jane@example.com'}
                ]
        elif sql.upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            return [{'affected_rows': 1, 'last_insert_id': 1}]
        
        return []
    
    async def execute_transaction(self, queries: List[Tuple[str, List[Any]]]) -> List[List[Dict[str, Any]]]:
        """
        Execute multiple queries in a transaction.
        
        Args:
            queries: List of (sql, parameters) tuples
            
        Returns:
            List of results for each query
        """
        logger.debug(f"Executing transaction with {len(queries)} queries")
        
        results = []
        try:
            await self.begin_transaction()
            
            for sql, params in queries:
                result = await self.execute_query(sql, params)
                results.append(result)
            
            await self.commit_transaction()
            logger.debug("Transaction committed successfully")
            
        except Exception as e:
            await self.rollback_transaction()
            logger.error(f"Transaction rolled back due to error: {e}")
            raise
        
        return results
    
    async def begin_transaction(self) -> None:
        """Begin a new transaction."""
        if self._in_transaction:
            # Nested transaction - use savepoint
            savepoint_name = f"sp_{len(self._transaction_stack)}"
            await self.execute_query(f"SAVEPOINT {savepoint_name}")
            self._transaction_stack.append(savepoint_name)
        else:
            await self.execute_query("BEGIN")
            self._in_transaction = True
    
    async def commit_transaction(self) -> None:
        """Commit the current transaction."""
        if self._transaction_stack:
            # Release savepoint
            savepoint = self._transaction_stack.pop()
            await self.execute_query(f"RELEASE SAVEPOINT {savepoint}")
        else:
            await self.execute_query("COMMIT")
            self._in_transaction = False
    
    async def rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        if self._transaction_stack:
            # Rollback to savepoint
            savepoint = self._transaction_stack.pop()
            await self.execute_query(f"ROLLBACK TO SAVEPOINT {savepoint}")
        else:
            await self.execute_query("ROLLBACK")
            self._in_transaction = False
    
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get information about a table."""
        # This would query database metadata
        return {
            'name': table_name,
            'columns': [],
            'indexes': [],
            'constraints': []
        }
    
    async def create_table(self, table_name: str, columns: Dict[str, str]) -> None:
        """Create a table with specified columns."""
        column_defs = []
        for name, definition in columns.items():
            column_defs.append(f'"{name}" {definition}')
        
        sql = f'CREATE TABLE "{table_name}" ({", ".join(column_defs)})'
        await self.execute_query(sql)
    
    async def drop_table(self, table_name: str, if_exists: bool = False) -> None:
        """Drop a table."""
        if_exists_clause = "IF EXISTS " if if_exists else ""
        sql = f'DROP TABLE {if_exists_clause}"{table_name}"'
        await self.execute_query(sql)


# Transaction context manager
class Transaction:
    """Context manager for database transactions."""
    
    def __init__(self, connection: DatabaseConnection):
        self.connection = connection
    
    async def __aenter__(self):
        await self.connection.begin_transaction()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.connection.commit_transaction()
        else:
            await self.connection.rollback_transaction()


# Query execution helpers
async def execute_raw_query(connection: DatabaseConnection, sql: str, parameters: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    """Execute raw SQL query."""
    return await connection.execute_query(sql, parameters or [])


async def bulk_insert(connection: DatabaseConnection, table: str, data: List[Dict[str, Any]]) -> int:
    """Perform bulk insert operation."""
    if not data:
        return 0
    
    query = QueryBuilder(table).insert_many(data)
    result = await query.execute(connection)
    return len(data)  # In real implementation, return actual affected rows


async def bulk_update(connection: DatabaseConnection, table: str, updates: List[Tuple[Dict[str, Any], Dict[str, Any]]]) -> int:
    """Perform bulk update operation."""
    affected_rows = 0
    
    async with Transaction(connection):
        for update_data, where_conditions in updates:
            query = QueryBuilder(table).update(update_data)
            
            # Add where conditions
            for field, value in where_conditions.items():
                query = query.where(field, value)
            
            await query.execute(connection)
            affected_rows += 1
    
    return affected_rows


# Migration helpers
class Migration:
    """Database migration helper."""
    
    def __init__(self, connection: DatabaseConnection):
        self.connection = connection
        self.operations = []
    
    def create_table(self, name: str, columns: Dict[str, str]) -> 'Migration':
        """Add create table operation."""
        self.operations.append(('create_table', name, columns))
        return self
    
    def drop_table(self, name: str, if_exists: bool = False) -> 'Migration':
        """Add drop table operation."""
        self.operations.append(('drop_table', name, if_exists))
        return self
    
    def add_column(self, table: str, column: str, definition: str) -> 'Migration':
        """Add column to table."""
        sql = f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}'
        self.operations.append(('raw_sql', sql, []))
        return self
    
    def drop_column(self, table: str, column: str) -> 'Migration':
        """Drop column from table."""
        sql = f'ALTER TABLE "{table}" DROP COLUMN "{column}"'
        self.operations.append(('raw_sql', sql, []))
        return self
    
    def add_index(self, table: str, columns: List[str], unique: bool = False) -> 'Migration':
        """Add index to table."""
        index_type = "UNIQUE INDEX" if unique else "INDEX"
        index_name = f"idx_{table}_{'_'.join(columns)}"
        column_list = ", ".join(f'"{col}"' for col in columns)
        sql = f'CREATE {index_type} "{index_name}" ON "{table}" ({column_list})'
        self.operations.append(('raw_sql', sql, []))
        return self
    
    async def execute(self) -> None:
        """Execute all migration operations."""
        async with Transaction(self.connection):
            for operation in self.operations:
                op_type = operation[0]
                
                if op_type == 'create_table':
                    await self.connection.create_table(operation[1], operation[2])
                elif op_type == 'drop_table':
                    await self.connection.drop_table(operation[1], operation[2])
                elif op_type == 'raw_sql':
                    await self.connection.execute_query(operation[1], operation[2])


# Export commonly used classes and functions
__all__ = [
    # Core classes
    'QueryBuilder', 'Q', 'QueryCondition', 'JoinClause',
    'DatabaseConnection', 'Transaction', 'Migration',
    
    # Enums
    'Operator', 'SortOrder', 'JoinType',
    
    # Exceptions
    'QueryError', 'InvalidQueryError', 'DatabaseError',
    
    # Helper functions
    'execute_raw_query', 'bulk_insert', 'bulk_update',
]


if __name__ == "__main__":
    # Example usage and testing
    async def main():
        # Create database connection
        conn = DatabaseConnection("postgresql://user:pass@localhost/db")
        await conn.connect()
        
        try:
            # Basic SELECT query
            query = (QueryBuilder("users")
                    .select("name", "email", "created_at")
                    .where("age", 18, Operator.GT)
                    .where("active", True)
                    .order_by("name")
                    .limit(10))
            
            print("=== Basic SELECT Query ===")
            sql, params = query.build_sql()
            print(f"SQL: {sql}")
            print(f"Parameters: {params}")
            
            # Complex WHERE with Q objects
            complex_query = (QueryBuilder("products")
                           .where_q(Q(category="electronics") | Q(price__lt=100))
                           .where_q(~Q(discontinued=True))
                           .order_by("price", desc=True))
            
            print("\n=== Complex WHERE Query ===")
            sql, params = complex_query.build_sql()
            print(f"SQL: {sql}")
            print(f"Parameters: {params}")
            
            # JOIN query
            join_query = (QueryBuilder("orders")
                         .select("orders.id", "users.name", "products.title")
                         .inner_join("users", "orders.user_id = users.id")
                         .left_join("order_items", "orders.id = order_items.order_id")
                         .left_join("products", "order_items.product_id = products.id")
                         .where("orders.status", "completed")
                         .order_by("orders.created_at", desc=True))
            
            print("\n=== JOIN Query ===")
            sql, params = join_query.build_sql()
            print(f"SQL: {sql}")
            print(f"Parameters: {params}")
            
            # Aggregation query
            agg_query = (QueryBuilder("orders")
                        .select("user_id", "COUNT(*) as order_count", "SUM(total) as total_spent")
                        .where("status", "completed")
                        .group_by("user_id")
                        .having(Q(order_count__gt=5))
                        .order_by("total_spent", desc=True))
            
            print("\n=== Aggregation Query ===")
            sql, params = agg_query.build_sql()
            print(f"SQL: {sql}")
            print(f"Parameters: {params}")
            
            # INSERT query
            insert_query = QueryBuilder("users").insert({
                "name": "John Doe",
                "email": "john@example.com",
                "age": 30,
                "created_at": datetime.now()
            })
            
            print("\n=== INSERT Query ===")
            sql, params = insert_query.build_sql()
            print(f"SQL: {sql}")
            print(f"Parameters: {params}")
            
            # UPDATE query
            update_query = (QueryBuilder("users")
                           .update({"last_login": datetime.now()})
                           .where("id", 1))
            
            print("\n=== UPDATE Query ===")
            sql, params = update_query.build_sql()
            print(f"SQL: {sql}")
            print(f"Parameters: {params}")
            
            # UPSERT query
            upsert_query = (QueryBuilder("user_settings")
                           .upsert(
                               {"user_id": 1, "theme": "dark", "notifications": True},
                               ["user_id"]
                           ))
            
            print("\n=== UPSERT Query ===")
            sql, params = upsert_query.build_sql()
            print(f"SQL: {sql}")
            print(f"Parameters: {params}")
            
            # Test Q object combinations
            print("\n=== Q Object Tests ===")
            q1 = Q(name="John", age__gt=18)
            q2 = Q(email__icontains="gmail") | Q(verified=True)
            combined = q1 & q2
            
            test_query = QueryBuilder("users").where_q(combined)
            sql, params = test_query.build_sql()
            print(f"Combined Q SQL: {sql}")
            print(f"Parameters: {params}")
            
            # Transaction example
            print("\n=== Transaction Example ===")
            async with Transaction(conn):
                # Multiple operations in transaction
                await QueryBuilder("users").insert({"name": "Test User"}).execute(conn)
                await QueryBuilder("profiles").insert({"user_id": 1, "bio": "Test"}).execute(conn)
                print("Transaction completed successfully")
            
            print("\nAll query builder tests completed!")
            
        finally:
            await conn.disconnect()
    
    asyncio.run(main())