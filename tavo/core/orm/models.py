"""
Tavo ORM Models

Enhanced BaseModel class with proper typing, validation, and utilities.
"""

import logging
from typing import Dict, Any, Optional, Type, List, ClassVar, TypeVar, Generic, cast
import asyncio

from .fields import Field, IntegerField
from .query import QueryBuilder

logger = logging.getLogger(__name__)

# Type variable for proper return type hinting
T = TypeVar('T', bound='BaseModel')


class ValidationError(Exception):
    """Raised when model validation fails."""
    def __init__(self, field_name: str, message: str, value: Any = None):
        self.field_name = field_name
        self.message = message
        self.value = value
        super().__init__(f"Validation error for field '{field_name}': {message}")


class ModelNotFoundError(Exception):
    """Raised when a model instance is not found."""
    pass


class ModelMeta(type):
    """
    Metaclass for ORM models that processes field definitions.
    """
    
    def __new__(mcs, name: str, bases: tuple, namespace: Dict[str, Any]) -> Type:
        # Extract fields from class definition and parent classes
        fields = {}
        
        # Inherit fields from parent classes
        for base in bases:
            if hasattr(base, '_fields'):
                fields.update(base._fields)
        
        # Process current class fields
        for key, value in list(namespace.items()):
            if isinstance(value, Field):
                value.name = key
                fields[key] = value
                # Remove field from namespace to avoid conflicts
                del namespace[key]
        
        # Add fields and metadata to class
        namespace['_fields'] = fields
        namespace['_table_name'] = namespace.get('_table_name', name.lower())
        namespace['_abstract'] = namespace.get('_abstract', False)
        
        # Ensure primary key exists (unless abstract)
        if not namespace.get('_abstract', False) and not any(f.primary_key for f in fields.values()):
            # Add default id field
            id_field = IntegerField(primary_key=True)
            id_field.name = 'id'
            fields['id'] = id_field
            namespace['_fields'] = fields
        
        cls = super().__new__(mcs, name, bases, namespace)
        return cls


class QuerySet(Generic[T]):
    """
    Lazy queryset for chaining database operations.
    """
    
    def __init__(self, model_class: Type[T], query_builder: Optional[QueryBuilder] = None):
        self.model_class = model_class
        self.query_builder = query_builder or QueryBuilder(model_class._table_name)
        self._result_cache: Optional[List[T]] = None
        self._is_evaluated = False
    
    def filter(self, **kwargs) -> 'QuerySet[T]':
        """Add WHERE conditions to the queryset."""
        new_qs = self._clone()
        
        for field_name, value in kwargs.items():
            if field_name not in self.model_class._fields:
                raise ValueError(f"Unknown field: {field_name}")
            new_qs.query_builder = new_qs.query_builder.where(field_name, value)
        
        return new_qs
    
    def exclude(self, **kwargs) -> 'QuerySet[T]':
        """Add WHERE NOT conditions to the queryset."""
        new_qs = self._clone()
        
        for field_name, value in kwargs.items():
            if field_name not in self.model_class._fields:
                raise ValueError(f"Unknown field: {field_name}")
            new_qs.query_builder = new_qs.query_builder.where_not(field_name, value)
        
        return new_qs
    
    def order_by(self, *fields: str) -> 'QuerySet[T]':
        """Add ORDER BY clause to the queryset."""
        new_qs = self._clone()
        
        for field in fields:
            desc = field.startswith('-')
            field_name = field[1:] if desc else field
            
            if field_name not in self.model_class._fields:
                raise ValueError(f"Unknown field: {field_name}")
            
            new_qs.query_builder = new_qs.query_builder.order_by(field_name, desc=desc)
        
        return new_qs
    
    def limit(self, count: int) -> 'QuerySet[T]':
        """Add LIMIT clause to the queryset."""
        new_qs = self._clone()
        new_qs.query_builder = new_qs.query_builder.limit(count)
        return new_qs
    
    def offset(self, count: int) -> 'QuerySet[T]':
        """Add OFFSET clause to the queryset."""
        new_qs = self._clone()
        new_qs.query_builder = new_qs.query_builder.offset(count)
        return new_qs
    
    async def get(self, **kwargs) -> T:
        """
        Get a single instance matching the criteria.
        Raises ModelNotFoundError if not found or MultipleObjectsReturned if multiple found.
        """
        if kwargs:
            qs = self.filter(**kwargs)
        else:
            qs = self
        
        results = await qs.limit(2)._fetch()
        
        if not results:
            raise ModelNotFoundError(f"No {self.model_class.__name__} matches the given query")
        
        if len(results) > 1:
            raise ValueError(f"Multiple {self.model_class.__name__} objects returned, expected one")
        
        return results[0]
    
    async def first(self) -> Optional[T]:
        """Get the first instance or None if no results."""
        results = await self.limit(1)._fetch()
        return results[0] if results else None
    
    async def last(self) -> Optional[T]:
        """Get the last instance or None if no results."""
        # This would need proper ORDER BY handling in a real implementation
        results = await self._fetch()
        return results[-1] if results else None
    
    async def exists(self) -> bool:
        """Check if any records match the query."""
        result = await self.limit(1)._fetch()
        return len(result) > 0
    
    async def count(self) -> int:
        """Get the count of matching records."""
        # In a real implementation, this would use COUNT() SQL
        results = await self._fetch()
        return len(results)
    
    async def delete(self) -> int:
        """Delete all matching records and return count."""
        count = await self.count()
        await self.query_builder.delete().execute()
        return count
    
    def _clone(self) -> 'QuerySet[T]':
        """Create a copy of this queryset."""
        return QuerySet(self.model_class, self.query_builder.clone() if hasattr(self.query_builder, 'clone') else self.query_builder)
    
    async def _fetch(self) -> List[T]:
        """Execute the query and return results."""
        if not self._is_evaluated:
            results = await self.query_builder.execute()
            self._result_cache = [self.model_class._from_db_row(row) for row in results]
            self._is_evaluated = True
        
        return self._result_cache or []
    
    async def __aiter__(self):
        """Async iterator support."""
        results = await self._fetch()
        for result in results:
            yield result
    
    def __await__(self):
        """Allow await on queryset to get all results."""
        return self._fetch().__await__()


class BaseModel(metaclass=ModelMeta):
    """
    Base class for all ORM models with improved typing and functionality.
    """
    
    _fields: ClassVar[Dict[str, Field]]
    _table_name: ClassVar[str]
    _abstract: ClassVar[bool] = False
    
    def __init__(self, **kwargs):
        self._data: Dict[str, Any] = {}
        self._original_data: Dict[str, Any] = {}
        self._is_saved = False
        self._is_dirty = False
        
        # Set field values
        for field_name, field in self._fields.items():
            value = kwargs.get(field_name)
            
            # Use default value if not provided
            if value is None:
                value = field.get_default()
            
            # Validate and set value
            try:
                validated_value = field.validate(value)
                self._data[field_name] = validated_value
                self._original_data[field_name] = validated_value
            except Exception as e:
                raise ValidationError(field_name, str(e), value)
    
    def __getattr__(self, name: str) -> Any:
        """Get field value."""
        if name in self._fields:
            return self._data.get(name)
        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Set field value with validation."""
        if name.startswith('_') or name in {'_fields', '_table_name', '_abstract'}:
            super().__setattr__(name, value)
            return
        
        if name in self._fields:
            field = self._fields[name]
            try:
                validated_value = field.validate(value)
                
                # Check if value actually changed
                current_value = self._data.get(name)
                if current_value != validated_value:
                    self._data[name] = validated_value
                    self._is_dirty = True
            except Exception as e:
                raise ValidationError(name, str(e), value)
        else:
            super().__setattr__(name, value)
    
    def is_dirty(self) -> bool:
        """Check if the instance has unsaved changes."""
        return self._is_dirty or self._data != self._original_data
    
    def get_dirty_fields(self) -> Dict[str, Any]:
        """Get dictionary of fields that have changed."""
        dirty = {}
        for field_name in self._fields:
            current = self._data.get(field_name)
            original = self._original_data.get(field_name)
            if current != original:
                dirty[field_name] = current
        return dirty
    
    def clean(self) -> None:
        """
        Hook for custom validation logic.
        Override in subclasses to add model-level validation.
        """
        pass
    
    def full_clean(self) -> None:
        """
        Validate the model instance completely.
        Calls field validation and custom clean() method.
        """
        # Validate all fields
        for field_name, field in self._fields.items():
            value = self._data.get(field_name)
            try:
                validated_value = field.validate(value)
                self._data[field_name] = validated_value
            except Exception as e:
                raise ValidationError(field_name, str(e), value)
        
        # Call custom validation
        self.clean()
    
    async def save(self, force_insert: bool = False, force_update: bool = False) -> None:
        """
        Save model instance to database.
        
        Args:
            force_insert: Force INSERT even if instance appears to be saved
            force_update: Force UPDATE even if instance appears to be new
        
        Raises:
            ValidationError: If validation fails
        """
        # Validate before saving
        self.full_clean()
        
        if force_insert or (not self._is_saved and not force_update):
            await self._insert()
        else:
            await self._update()
        
        self._is_saved = True
        self._is_dirty = False
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
    
    async def refresh_from_db(self, fields: Optional[List[str]] = None) -> None:
        """
        Reload the instance from the database.
        
        Args:
            fields: Specific fields to refresh, or None for all fields
        """
        if not self._is_saved:
            raise ValueError("Cannot refresh unsaved instance")
        
        pk_field = self._get_primary_key_field()
        pk_value = self._data[pk_field.name] # type: ignore
        
        fresh_instance = await self.__class__.objects.get(**{pk_field.name: pk_value}) # type: ignore
        
        if fields is None:
            fields = list(self._fields.keys())
        
        for field_name in fields:
            if field_name in fresh_instance._data:
                self._data[field_name] = fresh_instance._data[field_name]
                self._original_data[field_name] = fresh_instance._data[field_name]
        
        self._is_dirty = False
    
    async def _insert(self) -> None:
        """Insert new record into database."""
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
        if pk_field.name == 'id' and self._data.get('id') is None:
            # TODO: get last insert ID from result
            self._data['id'] = 1  # Mock value
            self._original_data['id'] = 1
    
    async def _update(self) -> None:
        """Update existing record in database."""
        if not self.is_dirty():
            return  # No changes to save
        
        pk_field = self._get_primary_key_field()
        pk_value = self._data[pk_field.name] # type: ignore
        
        # Find changed fields
        dirty_fields = self.get_dirty_fields()
        update_data = {}
        
        for field_name, value in dirty_fields.items():
            if field_name == pk_field.name:
                continue  # Don't update primary key
            
            field = self._fields[field_name]
            update_data[field_name] = field.to_db_value(value)
        
        if update_data:
            query = QueryBuilder(self._table_name)
            await query.update(update_data).where(pk_field.name, pk_value).execute() # type: ignore
    
    def _get_primary_key_field(self) -> Field:
        """Get the primary key field for this model."""
        for field in self._fields.values():
            if field.primary_key:
                return field
        
        raise ValueError(f"No primary key field found for {self.__class__.__name__}")
    
    def _get_primary_key_value(self) -> Any:
        """Get the primary key value for this instance."""
        pk_field = self._get_primary_key_field()
        return self._data.get(pk_field.name) # type: ignore
    
    @classmethod
    @property
    def objects(cls: Type[T]) -> QuerySet[T]:
        """
        Get a QuerySet for this model.
        
        Returns:
            QuerySet instance for chaining queries
        """
        return QuerySet(cls)
    
    @classmethod
    async def get(cls: Type[T], **kwargs) -> T:
        """
        Get single instance by field values.
        
        Args:
            **kwargs: Field values to filter by
            
        Returns:
            Model instance
            
        Raises:
            ModelNotFoundError: If no instance found
            ValueError: If multiple instances found
            
        Example:
            >>> user = await User.get(email="john@example.com")
        """
        return await cls.objects.get(**kwargs)
    
    @classmethod
    async def get_or_none(cls: Type[T], **kwargs) -> Optional[T]:
        """
        Get single instance by field values, return None if not found.
        
        Args:
            **kwargs: Field values to filter by
            
        Returns:
            Model instance or None if not found
        """
        try:
            return await cls.get(**kwargs)
        except ModelNotFoundError:
            return None
    
    @classmethod
    async def get_or_create(cls: Type[T], defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple[T, bool]:
        """
        Get or create an instance.
        
        Args:
            defaults: Default values for creation
            **kwargs: Field values to search/create with
            
        Returns:
            Tuple of (instance, created_flag)
        """
        try:
            instance = await cls.get(**kwargs)
            return instance, False
        except ModelNotFoundError:
            create_data = kwargs.copy()
            if defaults:
                create_data.update(defaults)
            
            instance = cls(**create_data)
            await instance.save()
            return instance, True
    
    @classmethod
    async def filter(cls: Type[T], **kwargs) -> List[T]:
        """
        Filter instances by field values.
        
        Args:
            **kwargs: Field values to filter by
            
        Returns:
            List of matching model instances
            
        Example:
            >>> active_users = await User.filter(active=True)
        """
        return await cls.objects.filter(**kwargs)
    
    @classmethod
    async def all(cls: Type[T]) -> List[T]:
        """
        Get all instances of this model.
        
        Returns:
            List of all model instances
        """
        return await cls.objects
    
    @classmethod
    async def create(cls: Type[T], **kwargs) -> T:
        """
        Create and save a new instance.
        
        Args:
            **kwargs: Field values for the new instance
            
        Returns:
            Saved model instance
            
        Example:
            >>> user = await User.create(name="John", email="john@example.com")
        """
        instance = cls(**kwargs)
        await instance.save()
        return instance
    
    @classmethod
    async def bulk_create(cls: Type[T], instances: List[T], batch_size: Optional[int] = None) -> List[T]:
        """
        Create multiple instances efficiently.
        
        Args:
            instances: List of model instances to create
            batch_size: Optional batch size for bulk operations
            
        Returns:
            List of created instances
        """
        # TODO: Implement actual bulk create with database
        for instance in instances:
            await instance.save()
        
        return instances
    
    @classmethod
    def _from_db_row(cls: Type[T], row: Dict[str, Any]) -> T:
        """Create model instance from database row."""
        # Convert database values to Python values
        converted_data = {}
        
        for field_name, field in cls._fields.items():
            if field_name in row:
                db_value = row[field_name]
                converted_data[field_name] = field.from_db_value(db_value)
        
        instance = cls(**converted_data)
        instance._is_saved = True
        instance._is_dirty = False
        instance._original_data = instance._data.copy()
        
        return instance
    
    def to_dict(self, include: Optional[List[str]] = None, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Args:
            include: Fields to include (None means all)
            exclude: Fields to exclude
            
        Returns:
            Dictionary representation of model
        """
        data = self._data.copy()
        
        if include is not None:
            data = {k: v for k, v in data.items() if k in include}
        
        if exclude is not None:
            data = {k: v for k, v in data.items() if k not in exclude}
        
        return data
    
    def __eq__(self, other) -> bool:
        """Check equality based on primary key."""
        if not isinstance(other, self.__class__):
            return False
        
        # If both have primary keys, compare them
        try:
            self_pk = self._get_primary_key_value()
            other_pk = other._get_primary_key_value()
            
            if self_pk is not None and other_pk is not None:
                return self_pk == other_pk
        except ValueError:
            pass
        
        # Fall back to comparing all data
        return self._data == other._data
    
    def __hash__(self) -> int:
        """Hash based on primary key or all data."""
        try:
            pk_value = self._get_primary_key_value()
            if pk_value is not None:
                return hash((self.__class__, pk_value))
        except ValueError:
            pass
        
        # Fall back to hashing all data
        return hash((self.__class__, tuple(sorted(self._data.items()))))
    
    def __repr__(self) -> str:
        """String representation of model instance."""
        try:
            pk_field = self._get_primary_key_field()
            pk_value = self._data.get(pk_field.name, "unsaved") # type: ignore
            return f"<{self.__class__.__name__}({pk_field.name}={pk_value})>"
        except ValueError:
            return f"<{self.__class__.__name__}(no_pk)>"
    
    def __str__(self) -> str:
        """String representation of model instance."""
        return self.__repr__()


class AbstractModel(BaseModel):
    """
    Abstract base model that won't create database tables.
    """
    _abstract = True


def create_model_class(
    name: str, 
    fields: Dict[str, Field], 
    table_name: Optional[str] = None,
    abstract: bool = False
) -> Type[BaseModel]:
    """
    Dynamically create a model class.
    
    Args:
        name: Model class name
        fields: Dictionary of field definitions
        table_name: Database table name (defaults to lowercase class name)
        abstract: Whether this is an abstract model
        
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
        '_abstract': abstract,
        **fields
    }
    
    base_class = AbstractModel if abstract else BaseModel
    return cast(Type[BaseModel], type(name, (base_class,), attrs))


if __name__ == "__main__":
    # Example usage
    from .fields import StringField, IntegerField, DateTimeField, BooleanField
    
    # Define a User model
    class User(BaseModel):
        _table_name = "users"
        
        name = StringField(max_length=100, null=False)
        email = StringField(unique=True, null=False)
        age = IntegerField(min_value=0, max_value=150)
        is_active = BooleanField(default=True)
        created_at = DateTimeField(auto_now_add=True)
        
        def clean(self):
            """Custom validation."""
            if self.age and self.age < 13: # type: ignore
                raise ValidationError('age', 'Users must be at least 13 years old')
    
    # Define an abstract model
    class TimestampedModel(AbstractModel):
        created_at = DateTimeField(auto_now_add=True)
        updated_at = DateTimeField(auto_now=True)
    
    # Model inheriting from abstract model
    class Post(TimestampedModel):
        _table_name = "posts"
        
        title = StringField(max_length=200, null=False)
        content = StringField()
        author_id = IntegerField()
    
    async def main():
        # Create and save a user
        user = User(name="John Doe", email="john@example.com", age=30)
        print(f"Created user: {user}")
        print(f"User data: {user.to_dict()}")
        print(f"Is dirty: {user.is_dirty()}")
        
        # Using QuerySet
        # all_users = await User.objects.filter(is_active=True).order_by('-created_at')
        # first_user = await User.objects.first()
        
        # Get or create pattern
        # user, created = await User.get_or_create(
        #     email="jane@example.com",
        #     defaults={'name': 'Jane Doe', 'age': 25}
        # )
        
        print("ORM examples completed!")
    
    asyncio.run(main())