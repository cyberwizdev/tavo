"""
Tavo ORM Fields

Enhanced field types for the ORM with better validation, type safety, and features.
"""

from typing import Any, Optional, Type, Union, Dict, List, Callable, TypeVar, Generic, Pattern, cast
from datetime import datetime, date, time, timezone
from decimal import Decimal, InvalidOperation
import logging
import json
import re
import uuid

logger = logging.getLogger(__name__)

# Type variables for better type hinting
T = TypeVar('T')
ModelType = TypeVar('ModelType', bound='BaseModel') # type: ignore


class ValidationError(Exception):
    """Raised when field validation fails."""
    def __init__(self, field_name: str, message: str, value: Any = None, code: Optional[str] = None):
        self.field_name = field_name
        self.message = message
        self.value = value
        self.code = code or 'invalid'
        super().__init__(f"Validation error for field '{field_name}': {message}")


class FieldDescriptor:
    """Descriptor for handling field access on model instances."""
    
    def __init__(self, field: 'Field'):
        self.field = field
    
    def __get__(self, instance, owner):
        if instance is None:
            return self.field
        return instance._data.get(self.field.name)
    
    def __set__(self, instance, value):
        if self.field.name in instance._fields:
            validated_value = self.field.validate(value)
            instance._data[self.field.name] = validated_value
            if hasattr(instance, '_is_dirty'):
                instance._is_dirty = True


class Field(Generic[T]):
    """
    Enhanced base field class for ORM models with better type safety and validation.
    """
    
    # Default error messages
    default_error_messages = {
        'required': 'This field is required.',
        'null': 'This field cannot be null.',
        'blank': 'This field cannot be blank.',
        'invalid': 'Invalid value.',
    }

    max_length = None
    min_length = None
    max_value = None
    min_value = None
    max_digits = None
    decimal_places = None
    
    auto_now = False
    auto_now_add = False
    
    def __init__(
        self,
        primary_key: bool = False,
        null: bool = True,
        blank: bool = True,
        default: Any = None,
        unique: bool = False,
        db_column: Optional[str] = None,
        db_index: bool = False,
        validators: Optional[List[Callable[[Any], None]]] = None,
        error_messages: Optional[Dict[str, str]] = None,
        help_text: str = '',
        verbose_name: Optional[str] = None,
        choices: Optional[List[tuple]] = None,
        editable: bool = True
    ):
        self.primary_key = primary_key
        self.null = null
        self.blank = blank
        self.default = default
        self.unique = unique
        self.db_column = db_column
        self.db_index = db_index
        self.validators = validators or []
        self.help_text = help_text
        self.verbose_name = verbose_name
        self.choices = choices
        self.editable = editable
        self.name: Optional[str] = None  # Set by metaclass
        
        # Merge error messages
        messages = {}
        for cls in reversed(self.__class__.__mro__):
            messages.update(getattr(cls, 'default_error_messages', {}))
        messages.update(error_messages or {})
        self.error_messages = messages
        
        # Validate choices format
        if self.choices:
            self._validate_choices()
    
    def _validate_choices(self) -> None:
        """Validate the choices format."""
        if not isinstance(self.choices, (list, tuple)):
            raise ValueError("Choices must be a list or tuple")
        
        for choice in self.choices:
            if not isinstance(choice, (list, tuple)) or len(choice) != 2:
                raise ValueError("Each choice must be a tuple/list of (value, label)")
    
    def get_default(self) -> Any:
        """Get the default value for this field."""
        if callable(self.default):
            return self.default()
        return self.default
    
    def validate(self, value: Any) -> T:
        """
        Comprehensive field validation.
        
        Args:
            value: Value to validate
            
        Returns:
            Validated and converted value
            
        Raises:
            ValidationError: If validation fails
        """
        # Handle None values
        if value is None:
            if not self.null:
                raise ValidationError(
                    self.name or 'field',
                    self.error_messages['null'],
                    value,
                    'null'
                )
            return cast(T, None)
        
        # Handle blank values for string-like fields
        if hasattr(self, '_is_string_like') and self._is_string_like():
            if not self.blank and (value == '' or (isinstance(value, str) and not value.strip())):
                raise ValidationError(
                    self.name or 'field',
                    self.error_messages['blank'],
                    value,
                    'blank'
                )
        
        # Type-specific validation
        try:
            value = self._validate_type(value)
        except (ValueError, TypeError) as e:
            raise ValidationError(
                self.name or 'field',
                str(e) or self.error_messages['invalid'],
                value,
                'invalid'
            )
        
        # Choice validation
        if self.choices:
            valid_choices = [choice[0] for choice in self.choices]
            if value not in valid_choices:
                raise ValidationError(
                    self.name or 'field',
                    f"Value must be one of: {valid_choices}",
                    value,
                    'invalid_choice'
                )
        
        # Custom validators
        for validator in self.validators:
            try:
                validator(value)
            except Exception as e:
                raise ValidationError(
                    self.name or 'field',
                    str(e),
                    value,
                    'validation_failed'
                )
        
        return cast(T, value)
    
    def _validate_type(self, value: Any) -> Any:
        """Override in subclasses for type-specific validation."""
        return value
    
    def _is_string_like(self) -> bool:
        """Check if this field handles string-like values."""
        return False
    
    def to_db_value(self, value: Any) -> Any:
        """Convert Python value to database value."""
        return value
    
    def from_db_value(self, value: Any) -> Any:
        """Convert database value to Python value."""
        return value
    
    def get_sql_type(self) -> str:
        """Get SQL type for this field."""
        return "TEXT"
    
    def get_sql_constraints(self) -> List[str]:
        """Get SQL constraints for this field."""
        constraints = []
        
        if self.primary_key:
            constraints.append("PRIMARY KEY")
        
        if not self.null:
            constraints.append("NOT NULL")
        
        if self.unique and not self.primary_key:
            constraints.append("UNIQUE")
        
        return constraints
    
    def contribute_to_class(self, cls, name: str) -> None:
        """Called when field is added to model class."""
        self.name = name
        if self.db_column is None:
            self.db_column = name
        
        # Set up descriptor
        setattr(cls, name, FieldDescriptor(self))
    
    def __repr__(self) -> str:
        """String representation of field."""
        return f"<{self.__class__.__name__}: {self.name or 'unnamed'}>"


class IntegerField(Field[int]):
    """Enhanced integer field with comprehensive validation."""
    
    default_error_messages = {
        **Field.default_error_messages,
        'invalid': 'Enter a valid integer.',
        'min_value': 'Ensure this value is greater than or equal to {min_value}.',
        'max_value': 'Ensure this value is less than or equal to {max_value}.',
    }
    
    def __init__(
        self, 
        min_value: Optional[int] = None, 
        max_value: Optional[int] = None, 
        **kwargs
    ):
        self.min_value = min_value
        self.max_value = max_value
        super().__init__(**kwargs)
    
    def _validate_type(self, value: Any) -> int:
        """Validate integer value with range checking."""
        if isinstance(value, bool):
            # Handle boolean explicitly since bool is subclass of int
            value = int(value)
        elif isinstance(value, float):
            if not value.is_integer():
                raise ValueError("Float value must be a whole number")
            value = int(value)
        elif isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise ValueError("Invalid integer format")
        elif not isinstance(value, int):
            raise ValueError(f"Expected integer, got {type(value).__name__}")
        
        if self.min_value is not None and value < self.min_value:
            raise ValueError(
                self.error_messages['min_value'].format(min_value=self.min_value)
            )
        
        if self.max_value is not None and value > self.max_value:
            raise ValueError(
                self.error_messages['max_value'].format(max_value=self.max_value)
            )
        
        return value
    
    def get_sql_type(self) -> str:
        return "INTEGER"


class BigIntegerField(IntegerField):
    """64-bit integer field."""
    
    def get_sql_type(self) -> str:
        return "BIGINT"


class SmallIntegerField(IntegerField):
    """16-bit integer field."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault('min_value', -32768)
        kwargs.setdefault('max_value', 32767)
        super().__init__(**kwargs)
    
    def get_sql_type(self) -> str:
        return "SMALLINT"


class PositiveIntegerField(IntegerField):
    """Positive integer field."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault('min_value', 1)
        super().__init__(**kwargs)


class PositiveSmallIntegerField(SmallIntegerField):
    """Positive small integer field."""
    
    def __init__(self, **kwargs):
        kwargs['min_value'] = max(kwargs.get('min_value', 1), 1)
        super().__init__(**kwargs)


class FloatField(Field[float]):
    """Floating point number field."""
    
    default_error_messages = {
        **Field.default_error_messages,
        'invalid': 'Enter a valid number.',
    }
    
    def _validate_type(self, value: Any) -> float:
        """Validate float value."""
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                raise ValueError("Invalid float format")
        else:
            raise ValueError(f"Expected number, got {type(value).__name__}")
    
    def get_sql_type(self) -> str:
        return "REAL"


class DecimalField(Field[Decimal]):
    """Decimal field for precise decimal numbers."""
    
    default_error_messages = {
        **Field.default_error_messages,
        'invalid': 'Enter a valid decimal number.',
        'max_digits': 'Ensure that there are no more than {max_digits} digits in total.',
        'decimal_places': 'Ensure that there are no more than {decimal_places} decimal places.',
    }
    
    def __init__(self, max_digits: int, decimal_places: int, **kwargs):
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        super().__init__(**kwargs)
    
    def _validate_type(self, value: Any) -> Decimal:
        """Validate decimal value."""
        try:
            if isinstance(value, Decimal):
                decimal_value = value
            else:
                decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError("Invalid decimal format")
        
        # Check total digits
        sign, digits, exponent = decimal_value.as_tuple()
        if len(digits) > self.max_digits:
            raise ValueError(
                self.error_messages['max_digits'].format(max_digits=self.max_digits)
            )
        
        # Check decimal places
        if exponent < 0 and abs(exponent) > self.decimal_places: # type: ignore
            raise ValueError(
                self.error_messages['decimal_places'].format(decimal_places=self.decimal_places)
            )
        
        return decimal_value
    
    def to_db_value(self, value: Any) -> str:
        """Convert Decimal to string for database storage."""
        if isinstance(value, Decimal):
            return str(value)
        return value
    
    def from_db_value(self, value: Any) -> Decimal:
        """Convert database string to Decimal."""
        if isinstance(value, str):
            return Decimal(value)
        elif isinstance(value, (int, float)):
            return Decimal(str(value))
        return value
    
    def get_sql_type(self) -> str:
        return f"DECIMAL({self.max_digits},{self.decimal_places})"


class CharField(Field[str]):
    """Character field with enhanced string validation."""
    
    default_error_messages = {
        **Field.default_error_messages,
        'max_length': 'Ensure this value has at most {max_length} characters (it has {length}).',
        'min_length': 'Ensure this value has at least {min_length} characters (it has {length}).',
    }
    
    def __init__(
        self, 
        max_length: Optional[int] = None, 
        min_length: Optional[int] = None,
        strip: bool = True,
        **kwargs
    ):
        self.max_length = max_length
        self.min_length = min_length
        self.strip = strip
        super().__init__(**kwargs)
    
    def _is_string_like(self) -> bool:
        return True
    
    def _validate_type(self, value: Any) -> str:
        """Validate string value with length constraints."""
        if not isinstance(value, str):
            value = str(value)
        
        if self.strip:
            value = value.strip()
        
        length = len(value)
        
        if self.max_length and length > self.max_length:
            raise ValueError(
                self.error_messages['max_length'].format(
                    max_length=self.max_length, 
                    length=length
                )
            )
        
        if self.min_length and length < self.min_length:
            raise ValueError(
                self.error_messages['min_length'].format(
                    min_length=self.min_length, 
                    length=length
                )
            )
        
        return value
    
    def get_sql_type(self) -> str:
        if self.max_length:
            return f"VARCHAR({self.max_length})"
        return "TEXT"


# Alias for backwards compatibility
StringField = CharField


class TextField(Field[str]):
    """Large text field for long content."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault('blank', True)
        super().__init__(**kwargs)
    
    def _is_string_like(self) -> bool:
        return True
    
    def _validate_type(self, value: Any) -> str:
        """Validate text value."""
        if not isinstance(value, str):
            value = str(value)
        return value
    
    def get_sql_type(self) -> str:
        return "TEXT"


class EmailField(CharField):
    """Email field with email format validation."""
    
    default_error_messages = {
        **CharField.default_error_messages,
        'invalid': 'Enter a valid email address.',
    }
    
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    def __init__(self, **kwargs):
        kwargs.setdefault('max_length', 254)
        super().__init__(**kwargs)
    
    def _validate_type(self, value: Any) -> str:
        """Validate email format."""
        value = super()._validate_type(value)
        
        if value and not self.EMAIL_REGEX.match(value):
            raise ValueError("Invalid email format")
        
        return value


class URLField(CharField):
    """URL field with URL format validation."""
    
    default_error_messages = {
        **CharField.default_error_messages,
        'invalid': 'Enter a valid URL.',
    }
    
    URL_REGEX = re.compile(
        r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.]*))?(?:#(?:\w*))?)?$'
    )
    
    def __init__(self, **kwargs):
        kwargs.setdefault('max_length', 200)
        super().__init__(**kwargs)
    
    def _validate_type(self, value: Any) -> str:
        """Validate URL format."""
        value = super()._validate_type(value)
        
        if value and not self.URL_REGEX.match(value):
            raise ValueError("Invalid URL format")
        
        return value


class SlugField(CharField):
    """Slug field for URL-friendly strings."""
    _source_field: Any = None
    
    default_error_messages = {
        **CharField.default_error_messages,
        'invalid': 'Enter a valid slug (letters, numbers, underscores, hyphens only).',
    }
    
    SLUG_REGEX = re.compile(r'^[-\w]+$')
    
    def __init__(self, **kwargs):
        kwargs.setdefault('max_length', 50)
        super().__init__(**kwargs)
    
    def _validate_type(self, value: Any) -> str:
        """Validate slug format."""
        value = super()._validate_type(value)
        
        if value and not self.SLUG_REGEX.match(value):
            raise ValueError("Invalid slug format")
        
        return value


class UUIDField(Field[uuid.UUID]):
    """UUID field."""
    
    default_error_messages = {
        **Field.default_error_messages,
        'invalid': 'Enter a valid UUID.',
    }
    
    def _validate_type(self, value: Any) -> uuid.UUID:
        """Validate UUID value."""
        if isinstance(value, uuid.UUID):
            return value
        elif isinstance(value, str):
            try:
                return uuid.UUID(value)
            except ValueError:
                raise ValueError("Invalid UUID format")
        else:
            raise ValueError(f"Expected UUID or string, got {type(value).__name__}")
    
    def to_db_value(self, value: Any) -> str:
        """Convert UUID to string for database."""
        if isinstance(value, uuid.UUID):
            return str(value)
        return value
    
    def from_db_value(self, value: Any) -> uuid.UUID:
        """Convert database string to UUID."""
        if isinstance(value, str):
            return uuid.UUID(value)
        return value
    
    def get_sql_type(self) -> str:
        return "UUID"


class BooleanField(Field[bool]):
    """Enhanced boolean field."""
    
    default_error_messages = {
        **Field.default_error_messages,
        'invalid': 'Enter a valid boolean value.',
    }
    
    TRUE_VALUES = {True, 'true', '1', 'yes', 'on', 'y', 't', 1}
    FALSE_VALUES = {False, 'false', '0', 'no', 'off', 'n', 'f', 0}
    
    def __init__(self, **kwargs):
        kwargs.setdefault('blank', True)
        super().__init__(**kwargs)
    
    def _validate_type(self, value: Any) -> bool:
        """Validate boolean value with flexible parsing."""
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            value = value.lower().strip()
        
        if value in self.TRUE_VALUES:
            return True
        elif value in self.FALSE_VALUES:
            return False
        else:
            raise ValueError(f"Invalid boolean value: {value}")
    
    def get_sql_type(self) -> str:
        return "BOOLEAN"


class DateTimeField(Field[datetime]):
    """Enhanced DateTime field with timezone support."""
    
    default_error_messages = {
        **Field.default_error_messages,
        'invalid': 'Enter a valid date/time.',
    }
    
    def __init__(
        self, 
        auto_now: bool = False, 
        auto_now_add: bool = False,
        timezone_aware: bool = True,
        **kwargs
    ):
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add
        self.timezone_aware = timezone_aware
        
        if auto_now_add:
            kwargs.setdefault('default', self._get_current_time)
            kwargs.setdefault('editable', False)
        
        super().__init__(**kwargs)
    
    def _get_current_time(self) -> datetime:
        """Get current time with timezone awareness."""
        if self.timezone_aware:
            return datetime.now(timezone.utc)
        return datetime.now()
    
    def _validate_type(self, value: Any) -> datetime:
        """Validate datetime value."""
        if isinstance(value, datetime):
            # Handle timezone awareness
            if self.timezone_aware and value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            elif not self.timezone_aware and value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            return value
        
        if isinstance(value, date):
            # Convert date to datetime
            dt = datetime.combine(value, time())
            if self.timezone_aware:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        
        if isinstance(value, str):
            try:
                # Try parsing ISO format
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if self.timezone_aware and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                raise ValueError("Invalid datetime format")
        
        raise ValueError(f"Expected datetime, got {type(value).__name__}")
    
    def to_db_value(self, value: Any) -> str:
        """Convert datetime to ISO string for database."""
        if isinstance(value, datetime):
            return value.isoformat()
        return value
    
    def from_db_value(self, value: Any) -> datetime:
        """Convert database value to datetime."""
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if self.timezone_aware and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        return value
    
    def get_sql_type(self) -> str:
        return "TIMESTAMP"


class DateField(Field[date]):
    """Date field."""
    
    default_error_messages = {
        **Field.default_error_messages,
        'invalid': 'Enter a valid date.',
    }
    
    def _validate_type(self, value: Any) -> date:
        """Validate date value."""
        if isinstance(value, date):
            return value
        
        if isinstance(value, datetime):
            return value.date()
        
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                raise ValueError("Invalid date format")
        
        raise ValueError(f"Expected date, got {type(value).__name__}")
    
    def to_db_value(self, value: Any) -> str:
        """Convert date to string for database."""
        if isinstance(value, date):
            return value.isoformat()
        return value
    
    def from_db_value(self, value: Any) -> date:
        """Convert database value to date."""
        if isinstance(value, str):
            return datetime.fromisoformat(value).date()
        return value
    
    def get_sql_type(self) -> str:
        return "DATE"


class TimeField(Field[time]):
    """Time field."""
    
    default_error_messages = {
        **Field.default_error_messages,
        'invalid': 'Enter a valid time.',
    }
    
    def _validate_type(self, value: Any) -> time:
        """Validate time value."""
        if isinstance(value, time):
            return value
        
        if isinstance(value, datetime):
            return value.time()
        
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(f"2000-01-01T{value}").time()
            except ValueError:
                raise ValueError("Invalid time format")
        
        raise ValueError(f"Expected time, got {type(value).__name__}")
    
    def to_db_value(self, value: Any) -> str:
        """Convert time to string for database."""
        if isinstance(value, time):
            return value.isoformat()
        return value
    
    def from_db_value(self, value: Any) -> time:
        """Convert database value to time."""
        if isinstance(value, str):
            return datetime.fromisoformat(f"2000-01-01T{value}").time()
        return value
    
    def get_sql_type(self) -> str:
        return "TIME"


class JSONField(Field[Any]):
    """Enhanced JSON field for storing structured data."""
    
    default_error_messages = {
        **Field.default_error_messages,
        'invalid': 'Enter valid JSON.',
    }
    
    def __init__(self, encoder: Optional[json.JSONEncoder] = None, **kwargs):
        self.encoder = encoder
        super().__init__(**kwargs)
    
    def _validate_type(self, value: Any) -> Any:
        """Validate JSON-serializable value."""
        if value is None:
            return value
        
        try:
            # Test JSON serialization
            json.dumps(value, cls=self.encoder) # type: ignore
            return value
        except (TypeError, ValueError) as e:
            raise ValueError(f"Value is not JSON serializable: {e}")
    
    def to_db_value(self, value: Any) -> Optional[str]:
        """Convert to JSON string for database."""
        if value is None:
            return None
        return json.dumps(value, cls=self.encoder) # type: ignore
    
    def from_db_value(self, value: Any) -> Any:
        """Convert from JSON string to Python object."""
        if value is None or value == '':
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value
    
    def get_sql_type(self) -> str:
        return "JSON"


class ForeignKeyField(Field[Any]):
    """Enhanced foreign key field."""
    
    def __init__(
        self, 
        to: Union[str, Type], 
        on_delete: str = "CASCADE",
        related_name: Optional[str] = None,
        to_field: str = 'id',
        **kwargs
    ):
        self.to = to
        self.on_delete = on_delete
        self.related_name = related_name
        self.to_field = to_field
        super().__init__(**kwargs)
    
    def _validate_type(self, value: Any) -> Any:
        """Validate foreign key value."""
        # In a real implementation, this would check if the referenced object exists
        # For now, just validate that it's a valid ID type
        if value is None:
            return value
        
        if isinstance(value, int):
            return value
        
        # If it's a model instance, get its primary key
        if hasattr(value, '_get_primary_key_value'):
            return value._get_primary_key_value()
        
        # Try to convert to int
        try:
            return int(value)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid foreign key value: {value}")
    
    def get_sql_type(self) -> str:
        return "INTEGER"  # Assuming integer primary keys


class ManyToManyField(Field[List[Any]]):
    """Many-to-many relationship field."""
    
    def __init__(
        self, 
        to: Union[str, Type], 
        through: Optional[str] = None,
        related_name: Optional[str] = None,
        **kwargs
    ):
        self.to = to
        self.through = through
        self.related_name = related_name
        kwargs.setdefault('editable', False)
        super().__init__(**kwargs)
    
    def _validate_type(self, value: Any) -> List[Any]:
        """Validate many-to-many value."""
        if value is None:
            return []
        
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("Many-to-many field value must be a list, tuple, or set")
        
        return list(value)
    
    def get_sql_type(self) -> str:
        # Many-to-many fields don't have a direct SQL type
        # They use intermediate tables
        return "TEXT"


# Validation functions
def validate_min_length(min_length: int) -> Callable[[str], None]:
    """Validator for minimum string length."""
    def validator(value: str) -> None:
        if len(value) < min_length:
            raise ValidationError(
                'field',
                f'Value must be at least {min_length} characters long'
            )
    return validator


def validate_max_length(max_length: int) -> Callable[[str], None]:
    """Validator for maximum string length."""
    def validator(value: str) -> None:
        if len(value) > max_length:
            raise ValidationError(
                'field',
                f'Value must be at most {max_length} characters long'
            )
    return validator


def validate_regex(pattern: Union[str, Pattern], message: str = "Invalid format") -> Callable[[str], None]:
    """Validator for regex pattern matching."""
    if isinstance(pattern, str):
        pattern = re.compile(pattern)
    
    def validator(value: str) -> None:
        if not pattern.match(value):
            raise ValidationError('field', message)
    return validator


def validate_range(min_value: Any, max_value: Any) -> Callable[[Any], None]:
    """Validator for value range."""
    def validator(value: Any) -> None:
        if min_value is not None and value < min_value:
            raise ValidationError('field', f'Value must be at least {min_value}')
        if max_value is not None and value > max_value:
            raise ValidationError('field', f'Value must be at most {max_value}')
    return validator


def validate_not_empty(value: Any) -> None:
    """Validator to ensure value is not empty."""
    if not value:
        raise ValidationError('field', 'This field cannot be empty')


def validate_positive(value: Union[int, float]) -> None:
    """Validator to ensure value is positive."""
    if value <= 0:
        raise ValidationError('field', 'Value must be positive')


def validate_non_negative(value: Union[int, float]) -> None:
    """Validator to ensure value is non-negative."""
    if value < 0:
        raise ValidationError('field', 'Value cannot be negative')


# Field factory functions
def create_field(field_type: str, **kwargs) -> Field:
    """
    Enhanced factory function to create fields by type name.
    
    Args:
        field_type: Type of field to create
        **kwargs: Field configuration
        
    Returns:
        Field instance
        
    Example:
        >>> field = create_field("string", max_length=100)
        >>> isinstance(field, CharField)
        True
        >>> field = create_field("email", max_length=255)
        >>> isinstance(field, EmailField)
        True
    """
    field_classes = {
        # Integer fields
        "integer": IntegerField,
        "int": IntegerField,
        "biginteger": BigIntegerField,
        "bigint": BigIntegerField,
        "smallinteger": SmallIntegerField,
        "smallint": SmallIntegerField,
        "positiveinteger": PositiveIntegerField,
        "posint": PositiveIntegerField,
        "positivesmallinteger": PositiveSmallIntegerField,
        "possmallint": PositiveSmallIntegerField,
        
        # Float and decimal fields
        "float": FloatField,
        "real": FloatField,
        "decimal": DecimalField,
        
        # String fields
        "string": CharField,
        "char": CharField,
        "varchar": CharField,
        "text": TextField,
        "email": EmailField,
        "url": URLField,
        "slug": SlugField,
        
        # Date/time fields
        "datetime": DateTimeField,
        "timestamp": DateTimeField,
        "date": DateField,
        "time": TimeField,
        
        # Other fields
        "boolean": BooleanField,
        "bool": BooleanField,
        "json": JSONField,
        "uuid": UUIDField,
        "foreignkey": ForeignKeyField,
        "fk": ForeignKeyField,
        "manytomany": ManyToManyField,
        "m2m": ManyToManyField,
    }
    
    field_class = field_classes.get(field_type.lower())
    if not field_class:
        available_types = ', '.join(sorted(field_classes.keys()))
        raise ValueError(f"Unknown field type: {field_type}. Available types: {available_types}")
    
    return field_class(**kwargs)


def create_choice_field(choices: List[tuple], field_type: str = "string", **kwargs) -> Field:
    """
    Create a field with choices constraint.
    
    Args:
        choices: List of (value, label) tuples
        field_type: Base field type
        **kwargs: Additional field options
        
    Returns:
        Field instance with choices
        
    Example:
        >>> STATUS_CHOICES = [('active', 'Active'), ('inactive', 'Inactive')]
        >>> field = create_choice_field(STATUS_CHOICES, 'string', max_length=20)
    """
    kwargs['choices'] = choices
    return create_field(field_type, **kwargs)


# Specialized field creation helpers
def auto_field(**kwargs) -> IntegerField:
    """Create an auto-incrementing primary key field."""
    kwargs.update({
        'primary_key': True,
        'null': False,
        'editable': False
    })
    return IntegerField(**kwargs)


def created_at_field(**kwargs) -> DateTimeField:
    """Create a 'created at' timestamp field."""
    kwargs.update({
        'auto_now_add': True,
        'null': False,
        'editable': False
    })
    return DateTimeField(**kwargs)


def updated_at_field(**kwargs) -> DateTimeField:
    """Create an 'updated at' timestamp field."""
    kwargs.update({
        'auto_now': True,
        'null': False,
        'editable': False
    })
    return DateTimeField(**kwargs)


def slug_from_field(source_field: str, **kwargs) -> SlugField:
    """Create a slug field that auto-generates from another field."""
    kwargs.update({
        'unique': True,
        'editable': False
    })
    # In a real implementation, this would set up auto-generation
    slug_field = SlugField(**kwargs)
    slug_field._source_field = source_field
    return slug_field


# Field inspection utilities
def get_field_info(field: Field) -> Dict[str, Any]:
    """
    Get comprehensive information about a field.
    
    Args:
        field: Field instance to inspect
        
    Returns:
        Dictionary with field information
    """
    info = {
        'name': field.name,
        'type': field.__class__.__name__,
        'sql_type': field.get_sql_type(),
        'constraints': field.get_sql_constraints(),
        'null': field.null,
        'blank': field.blank,
        'unique': field.unique,
        'primary_key': field.primary_key,
        'db_index': field.db_index,
        'default': field.default,
        'help_text': field.help_text,
        'verbose_name': field.verbose_name,
        'choices': field.choices,
        'editable': field.editable,
    }
    
    # Add field-specific information
    if hasattr(field, 'max_length'):
        info['max_length'] = field.max_length
    if hasattr(field, 'min_length'):
        info['min_length'] = field.min_length
    if hasattr(field, 'max_value'):
        info['max_value'] = field.max_value
    if hasattr(field, 'min_value'):
        info['min_value'] = field.min_value
    if hasattr(field, 'max_digits'):
        info['max_digits'] = field.max_digits
    if hasattr(field, 'decimal_places'):
        info['decimal_places'] = field.decimal_places
    if hasattr(field, 'auto_now'):
        info['auto_now'] = field.auto_now
    if hasattr(field, 'auto_now_add'):
        info['auto_now_add'] = field.auto_now_add
    
    return info


def validate_field_value(field: Field, value: Any) -> tuple[bool, Optional[str]]:
    """
    Validate a value against a field without raising exceptions.
    
    Args:
        field: Field to validate against
        value: Value to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        field.validate(value)
        return True, None
    except ValidationError as e:
        return False, e.message
    except Exception as e:
        return False, str(e)


# Export commonly used field types for convenience
__all__ = [
    # Base classes
    'Field', 'ValidationError', 'FieldDescriptor',
    
    # Numeric fields
    'IntegerField', 'BigIntegerField', 'SmallIntegerField', 
    'PositiveIntegerField', 'PositiveSmallIntegerField',
    'FloatField', 'DecimalField',
    
    # String fields
    'CharField', 'StringField', 'TextField', 'EmailField', 
    'URLField', 'SlugField',
    
    # Date/time fields
    'DateTimeField', 'DateField', 'TimeField',
    
    # Other fields
    'BooleanField', 'UUIDField', 'JSONField',
    'ForeignKeyField', 'ManyToManyField',
    
    # Validators
    'validate_min_length', 'validate_max_length', 'validate_regex',
    'validate_range', 'validate_not_empty', 'validate_positive',
    'validate_non_negative',
    
    # Factory functions
    'create_field', 'create_choice_field',
    
    # Helper functions
    'auto_field', 'created_at_field', 'updated_at_field', 'slug_from_field',
    'get_field_info', 'validate_field_value',
]


if __name__ == "__main__":
    # Example usage and testing
    
    # Create various field types
    id_field = auto_field()
    name_field = CharField(max_length=100, null=False, blank=False)
    email_field = EmailField(unique=True)
    age_field = IntegerField(min_value=0, max_value=150, validators=[validate_non_negative])
    bio_field = TextField(blank=True)
    created_field = created_at_field()
    updated_field = updated_at_field()
    active_field = BooleanField(default=True)
    score_field = DecimalField(max_digits=5, decimal_places=2)
    uuid_field = UUIDField()
    
    # Field with choices
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ]
    status_field = create_choice_field(STATUS_CHOICES, 'string', max_length=20, default='draft')
    
    # Test validation
    test_fields = [
        (name_field, "John Doe", True),
        (name_field, "", False),  # Should fail because blank=False
        (email_field, "john@example.com", True),
        (email_field, "invalid-email", False),
        (age_field, 25, True),
        (age_field, -5, False),  # Should fail min_value validation
        (age_field, 200, False),  # Should fail max_value validation
        (status_field, "published", True),
        (status_field, "invalid_status", False),  # Should fail choices validation
        (uuid_field, "550e8400-e29b-41d4-a716-446655440000", True),
        (uuid_field, "invalid-uuid", False),
    ]
    
    print("Field Validation Tests:")
    print("=" * 50)
    
    for field, value, expected_valid in test_fields:
        is_valid, error = validate_field_value(field, value)
        status = "✓" if is_valid == expected_valid else "✗"
        print(f"{status} {field.__class__.__name__}: {value} -> {'Valid' if is_valid else f'Error: {error}'}")
    
    print("\nField Information:")
    print("=" * 50)
    
    for field in [name_field, email_field, age_field, status_field]:
        field.name = f"test_{field.__class__.__name__.lower()}"
        info = get_field_info(field)
        print(f"{field.name}: {info}")
    
    print("\nFactory Function Tests:")
    print("=" * 50)
    
    # Test factory functions
    factory_tests = [
        ("string", {"max_length": 50}, CharField),
        ("email", {}, EmailField),
        ("integer", {"min_value": 0}, IntegerField),
        ("boolean", {"default": False}, BooleanField),
        ("datetime", {"auto_now": True}, DateTimeField),
        ("decimal", {"max_digits": 10, "decimal_places": 2}, DecimalField),
    ]
    
    for field_type, kwargs, expected_class in factory_tests:
        field = create_field(field_type, **kwargs)
        status = "✓" if isinstance(field, expected_class) else "✗"
        print(f"{status} create_field('{field_type}') -> {field.__class__.__name__}")
    
    print("\nAll tests completed!")