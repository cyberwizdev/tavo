"""
Tavo ORM Models

BaseModel class, meta, and model utilities.
"""

import logging
from typing import Dict, Any, Optional, Type, List, ClassVar
from dataclasses import dataclass, field
import asyncio

from .fields import Field, IntegerField
from .query import QueryBuilder

logger = logging.getLogger(__name__)


class ModelMeta(type):
    """
    Metaclass for ORM models that processes field definitions.
    """
    
    def __new__(mcs, name: str, bases: tuple, namespace: Dict[str, Any]) -> Type:
        # Extract fields from class definition
        fields = {}
        
        for key, value in list(namespace.items()):
            if isinstance(value, Field):
                value.name = key
                fields[key] = value
                # Remove field from namespace to avoid conflicts
                del namespace[key]
        
        # Add fields to class
        namespace['_fields'] = fields
        namespace['_table_name'] = namespace.get('_table_name', name.lower())
        
        # Ensure primary key exists
        if not any(f.primary_key for f in fields.values()):
            # Add default id field
            id_field = IntegerField(primary_key=True)
            id_field.name = 'id'
            fields['id'] = id_field
        
        cls = super().__new__(mcs, name, bases, namespace)
        return cls


class BaseModel(metaclass=ModelMeta):
    """
    Base class for all ORM models.
    """
    
    _fields: ClassVar[Dict[str, Field]]
    _table_name: ClassVar[str]
    
    def __init__(self, **kwargs):
        self._data: Dict[str, Any] = {}
        self._original_data: Dict[str, Any] = {}
        self._is_saved = False
        
        # Set field values
        for field_name, field in self._fields.items():
            value = kwargs.get(field_name, field.default)
            if callable(value):
                value = value()
            
            # Validate value
            validated_value = field.validate(value)
            self._data[field_name] = validated_value
            self._original_data[field_name] = validated_value
    
    def __getattr__(self, name: str) -> Any:
        """Get field value."""
        if name in self._fields:
            return self._data.get(name)
        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Set field value with validation."""
        if name.startswith('_') or name in {'_fields', '_table_name'}:
            super().__setattr__(name, value)
            return
        
        if name in self._fields:
            field = self._fields[name]
            validated_value = field.validate(value)
            self._data[name] = validated_value
        else:
            super().__setattr__(name, value)
    
    async def save(self) -> None:
        """
        Save model instance to database.
        
        Raises:
            ValueError: If validation fails
            
        Example:
            >>> user = User(name="John", email="john@example.com")
            >>> await user.save()
        """
        if self._is_saved:
            await self._update()
        else:
            await self._insert()
        
        self._is_saved = True
        self._original_data = self._data.copy()
        logger.debug(f"Saved {self.__class__.__name__} instance")
    
    async def delete(self) -> None:
        """Delete model instance from database."""
        if not self._is_saved:
            raise ValueError("Cannot delete unsaved instance")
        
        pk_field = self._get_primary_key_field()
        pk_value = self._data[pk_field.name] # type: ignore
        
        query = QueryBuilder(self._table_name)
        await query.delete().where(pk_field.name, pk_value).execute() # type: ignore
        
        self._is_saved = False
        logger.debug(f"Deleted {self.__class__.__name__} instance")
    
    async def _insert(self) -> None:
        """Insert new record into database."""
        # TODO: implement actual database insertion
        query = QueryBuilder(self._table_name)
        
        # Prepare data for insertion
        insert_data = {}
        for field_name, field in self._fields.items():
            if field.primary_key and field.name == 'id':
                continue  # Skip auto-increment primary key
            
            value = self._data.get(field_name)
            if value is not None:
                insert_data[field_name] = field.to_db_value(value)
        
        result = await query.insert(insert_data).execute()
        
        # Set primary key if it was auto-generated
        pk_field = self._get_primary_key_field()
        if pk_field.name == 'id' and 'id' not in self._data:
            # TODO: get last insert ID from result
            self._data['id'] = 1  # Mock value
    
    async def _update(self) -> None:
        """Update existing record in database."""
        pk_field = self._get_primary_key_field()
        pk_value = self._data[pk_field.name] # type: ignore
        
        # Find changed fields
        update_data = {}
        for field_name, field in self._fields.items():
            if field.primary_key:
                continue
            
            current_value = self._data.get(field_name)
            original_value = self._original_data.get(field_name)
            
            if current_value != original_value:
                update_data[field_name] = field.to_db_value(current_value)
        
        if update_data:
            query = QueryBuilder(self._table_name)
            await query.update(update_data).where(pk_field.name, pk_value).execute() # type: ignore
    
    def _get_primary_key_field(self) -> Field:
        """Get the primary key field for this model."""
        for field in self._fields.values():
            if field.primary_key:
                return field
        
        raise ValueError(f"No primary key field found for {self.__class__.__name__}")
    
    @classmethod
    async def get(cls, **kwargs) -> Optional['BaseModel']:
        """
        Get single instance by field values.
        
        Args:
            **kwargs: Field values to filter by
            
        Returns:
            Model instance or None if not found
            
        Example:
            >>> user = await User.get(email="john@example.com")
        """
        query = QueryBuilder(cls._table_name)
        
        for field_name, value in kwargs.items():
            if field_name not in cls._fields:
                raise ValueError(f"Unknown field: {field_name}")
            query = query.where(field_name, value)
        
        result = await query.limit(1).execute()
        
        if result:
            return cls._from_db_row(result[0])
        
        return None
    
    @classmethod
    async def filter(cls, **kwargs) -> List['BaseModel']:
        """
        Filter instances by field values.
        
        Args:
            **kwargs: Field values to filter by
            
        Returns:
            List of matching model instances
            
        Example:
            >>> active_users = await User.filter(active=True)
        """
        query = QueryBuilder(cls._table_name)
        
        for field_name, value in kwargs.items():
            if field_name not in cls._fields:
                raise ValueError(f"Unknown field: {field_name}")
            query = query.where(field_name, value)
        
        results = await query.execute()
        return [cls._from_db_row(row) for row in results]
    
    @classmethod
    async def all(cls) -> List['BaseModel']:
        """
        Get all instances of this model.
        
        Returns:
            List of all model instances
        """
        query = QueryBuilder(cls._table_name)
        results = await query.execute()
        return [cls._from_db_row(row) for row in results]
    
    @classmethod
    def _from_db_row(cls, row: Dict[str, Any]) -> 'BaseModel':
        """Create model instance from database row."""
        # Convert database values to Python values
        converted_data = {}
        
        for field_name, field in cls._fields.items():
            if field_name in row:
                db_value = row[field_name]
                converted_data[field_name] = field.from_db_value(db_value)
        
        instance = cls(**converted_data)
        instance._is_saved = True
        instance._original_data = instance._data.copy()
        
        return instance
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Returns:
            Dictionary representation of model
        """
        return self._data.copy()
    
    def __repr__(self) -> str:
        """String representation of model instance."""
        pk_field = self._get_primary_key_field()
        pk_value = self._data.get(pk_field.name, "unsaved") # type: ignore
        return f"<{self.__class__.__name__}({pk_field.name}={pk_value})>"


def create_model_class(
    name: str, 
    fields: Dict[str, Field], 
    table_name: Optional[str] = None
) -> Type[BaseModel]:
    """
    Dynamically create a model class.
    
    Args:
        name: Model class name
        fields: Dictionary of field definitions
        table_name: Database table name (defaults to lowercase class name)
        
    Returns:
        Model class
        
    Example:
        >>> User = create_model_class("User", {
        ...     "name": StringField(max_length=100),
        ...     "email": StringField(unique=True)
        ... })
    """
    attrs = {
        '_table_name': table_name or name.lower(),
        **fields
    }
    
    return type(name, (BaseModel,), attrs)


if __name__ == "__main__":
    # Example usage
    from .fields import StringField, IntegerField, DateTimeField
    
    # Define a User model
    class User(BaseModel):
        _table_name = "users"
        
        name = StringField(max_length=100, null=False)
        email = StringField(unique=True, null=False)
        age = IntegerField(min_value=0, max_value=150)
        created_at = DateTimeField(auto_now_add=True)
    
    async def main():
        # Create and save a user
        user = User(name="John Doe", email="john@example.com", age=30)
        print(f"Created user: {user}")
        print(f"User data: {user.to_dict()}")
        
        # Note: save() would require database connection
        # await user.save()
    
    asyncio.run(main())

# Unit tests as comments:
# 1. test_model_field_validation() - verify field validation works on model instances
# 2. test_model_save_and_retrieve() - test save/get cycle with database
# 3. test_model_metaclass() - verify metaclass processes fields correctly