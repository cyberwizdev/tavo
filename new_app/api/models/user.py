"""
User Model

Example simple user model (dataclass) to demonstrate ORM usage.
"""

from typing import Optional, List
from tavo.core.orm import BaseModel
from tavo.core.orm.fields import StringField, DateTimeField, BooleanField, IntegerField


class User(BaseModel):
    """
    User model demonstrating Tavo ORM usage.
    
    Example:
        >>> user = User(name="John Doe", email="john@example.com")
        >>> await user.save()
        >>> print(f"Created user: {user.name}")
    """
    
    _table_name = "users"
    
    # Fields
    name = StringField(max_length=100, null=False)
    email = StringField(max_length=255, unique=True, null=False)
    age = IntegerField(min_value=0, max_value=150, null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    def __str__(self) -> str:
        """String representation of user."""
        return f"User(name='{self.name}', email='{self.email}')"
    
    @classmethod
    async def get_by_email(cls, email: str) -> Optional['User']:
        """
        Get user by email address.
        
        Args:
            email: Email address to search for
            
        Returns:
            User instance or None if not found
            
        Example:
            >>> user = await User.get_by_email("john@example.com")
        """
        return await cls.get(email=email)
    
    @classmethod
    async def get_active_users(cls):
        """
        Get all active users.
        
        Returns:
            List of active User instances
        """
        return await cls.filter(is_active=True)
    
    async def deactivate(self) -> None:
        """Deactivate user account."""
        self.is_active = False
        await self.save()
    
    async def activate(self) -> None:
        """Activate user account."""
        self.is_active = True
        await self.save()
    
    def to_public_dict(self) -> dict:
        """
        Convert to dictionary with public fields only.
        
        Returns:
            Dictionary with safe-to-expose user data
        """
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None # type: ignore
        }


# Unit tests as doctests:
def test_user_creation():
    """
    Test user model creation and validation.
    
    >>> user = User(name="Test User", email="test@example.com", age=25)
    >>> user.name
    'Test User'
    >>> user.is_active
    True
    """
    pass


def test_user_validation():
    """
    Test user field validation.
    
    >>> try:
    ...     user = User(name="", email="invalid-email")
    ... except ValueError as e:
    ...     print("Validation failed as expected")
    """
    pass


if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Example usage
        user = User(
            name="John Doe",
            email="john@example.com", 
            age=30
        )
        
        print(f"Created user: {user}")
        print(f"Public data: {user.to_public_dict()}")
        
        # Note: save() would require database connection
        # await user.save()
    
    asyncio.run(main())

# Unit tests as comments:
# 1. test_user_email_uniqueness() - verify email uniqueness constraint works
# 2. test_user_activation_methods() - test activate/deactivate functionality
# 3. test_user_public_dict() - verify sensitive data is excluded from public dict