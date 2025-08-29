"""
Bino ORM Fields

Field types for the ORM (Integer, String, DateTime, ForeignKey, etc.).
"""

from typing import Any, Optional, Type, Union, Dict
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class Field:
    """
    Base field class for ORM models.
    """
    
    def __init__(
        self,
        primary_key: bool = False,
        null: bool = True,
        default: Any = None,
        unique: bool = False,
        db_column: Optional[str] = None
    ):
        self.primary_key = primary_key
        self.null = null
        self.default = default
        self.unique = unique
        self.db_column = db_column
        self.name: Optional[str] = None  # Set by metaclass
    
    def validate(self, value: Any) -> Any:
        """
        Validate and convert field value.
        
        Args:
            value: Value to validate
            
        Returns:
            Validated value
            
        Raises:
            ValueError: If validation fails
        """
        if value is None:
            if not self.null and self.default is None:
                raise ValueError(f"Field {self.name} cannot be null")
            return self.default if value is None else value
        
        return self._validate_type(value)
    
    def _validate_type(self, value: Any) -> Any:
        """Override in subclasses for type-specific validation."""
        return value
    
    def to_db_value(self, value: Any) -> Any:
        """Convert Python value to database value."""
        return value
    
    def from_db_value(self, value: Any) -> Any:
        """Convert database value to Python value."""
        return value
    
    def get_sql_type(self) -> str:
        """Get SQL type for this field."""
        return "TEXT"


class IntegerField(Field):
    """Integer field type."""
    
    def __init__(self, min_value: Optional[int] = None, max_value: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value
    
    def _validate_type(self, value: Any) -> int:
        """
        Validate integer value.
        
        Example:
            >>> field = IntegerField(min_value=0, max_value=100)
            >>> field._validate_type(50)
            50
        """
        if not isinstance(value, int):
            try:
                value = int(value)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid integer value: {value}")
        
        if self.min_value is not None and value < self.min_value:
            raise ValueError(f"Value {value} is below minimum {self.min_value}")
        
        if self.max_value is not None and value > self.max_value:
            raise ValueError(f"Value {value} is above maximum {self.max_value}")
        
        return value
    
    def get_sql_type(self) -> str:
        return "INTEGER"


class StringField(Field):
    """String field type."""
    
    def __init__(self, max_length: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.max_length = max_length
    
    def _validate_type(self, value: Any) -> str:
        """Validate string value."""
        if not isinstance(value, str):
            value = str(value)
        
        if self.max_length and len(value) > self.max_length:
            raise ValueError(f"String too long: {len(value)} > {self.max_length}")
        
        return value
    
    def get_sql_type(self) -> str:
        if self.max_length:
            return f"VARCHAR({self.max_length})"
        return "TEXT"


class DateTimeField(Field):
    """DateTime field type."""
    
    def __init__(self, auto_now: bool = False, auto_now_add: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add
        
        if auto_now_add:
            kwargs.setdefault('default', datetime.now)
    
    def _validate_type(self, value: Any) -> datetime:
        """Validate datetime value."""
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise ValueError(f"Invalid datetime string: {value}")
        
        raise ValueError(f"Invalid datetime value: {value}")
    
    def to_db_value(self, value: Any) -> str:
        """Convert datetime to ISO string for database."""
        if isinstance(value, datetime):
            return value.isoformat()
        return value
    
    def from_db_value(self, value: Any) -> datetime:
        """Convert database value to datetime."""
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value
    
    def get_sql_type(self) -> str:
        return "TIMESTAMP"


class ForeignKeyField(Field):
    """Foreign key field type."""
    
    def __init__(self, to: Union[str, Type], on_delete: str = "CASCADE", **kwargs):
        super().__init__(**kwargs)
        self.to = to
        self.on_delete = on_delete
    
    def _validate_type(self, value: Any) -> Any:
        """Validate foreign key value."""
        # TODO: implement foreign key validation
        # This would check if the referenced object exists
        return value
    
    def get_sql_type(self) -> str:
        return "INTEGER"  # Assuming integer primary keys


class BooleanField(Field):
    """Boolean field type."""
    
    def _validate_type(self, value: Any) -> bool:
        """Validate boolean value."""
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            if value.lower() in ("true", "1", "yes", "on"):
                return True
            elif value.lower() in ("false", "0", "no", "off"):
                return False
        
        if isinstance(value, int):
            return bool(value)
        
        raise ValueError(f"Invalid boolean value: {value}")
    
    def get_sql_type(self) -> str:
        return "BOOLEAN"


class JSONField(Field):
    """JSON field type for storing structured data."""
    
    def _validate_type(self, value: Any) -> Any:
        """Validate JSON-serializable value."""
        try:
            # Test JSON serialization
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            raise ValueError(f"Value is not JSON serializable: {value}")
    
    def to_db_value(self, value: Any) -> str:
        """Convert to JSON string for database."""
        return json.dumps(value)
    
    def from_db_value(self, value: Any) -> Any:
        """Convert from JSON string to Python object."""
        if isinstance(value, str):
            return json.loads(value)
        return value
    
    def get_sql_type(self) -> str:
        return "JSON"


def create_field(field_type: str, **kwargs) -> Field:
    """
    Factory function to create fields by type name.
    
    Args:
        field_type: Type of field to create
        **kwargs: Field configuration
        
    Returns:
        Field instance
        
    Example:
        >>> field = create_field("string", max_length=100)
        >>> isinstance(field, StringField)
        True
    """
    field_classes = {
        "integer": IntegerField,
        "string": StringField,
        "datetime": DateTimeField,
        "boolean": BooleanField,
        "json": JSONField,
        "foreignkey": ForeignKeyField
    }
    
    field_class = field_classes.get(field_type.lower())
    if not field_class:
        raise ValueError(f"Unknown field type: {field_type}")
    
    return field_class(**kwargs)


if __name__ == "__main__":
    # Example usage
    
    # Create various field types
    id_field = IntegerField(primary_key=True)
    name_field = StringField(max_length=100, null=False)
    created_field = DateTimeField(auto_now_add=True)
    active_field = BooleanField(default=True)
    
    # Test validation
    try:
        validated_name = name_field.validate("John Doe")
        print(f"Valid name: {validated_name}")
        
        validated_id = id_field.validate(123)
        print(f"Valid ID: {validated_id}")
        
    except ValueError as e:
        print(f"Validation error: {e}")

# Unit tests as comments:
# 1. test_field_validation() - verify each field type validates correctly
# 2. test_field_sql_types() - test SQL type generation for all field types
# 3. test_field_db_conversion() - verify to_db_value/from_db_value work correctly