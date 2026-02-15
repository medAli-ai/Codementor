from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib
import base64
from passlib.context import CryptContext
from jose import jwt, JWTError
from sqlalchemy.orm import Session  # ✅ Import Session type

from app.core.config import settings
from app.models.user import User  # ✅ Import User model
from app.schemas.user import UserResponse  # ✅ Import for response

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _prehash_password(password: str) -> str:
    """
    Pre-hash password with SHA256 to avoid bcrypt's 72-byte limit.
    """
    hash_bytes = hashlib.sha256(password.encode('utf-8')).digest()
    return base64.b64encode(hash_bytes).decode('ascii')


def get_password_hash(password: str) -> str:
    """Hash a password for storage."""
    prehashed = _prehash_password(password)
    return pwd_context.hash(prehashed)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    prehashed = _prehash_password(plain_password)
    return pwd_context.verify(prehashed, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_refresh_token() -> str:
    """Generate a secure random refresh token."""
    return secrets.token_urlsafe(64)


def create_tokens(user: User, db: Session) -> dict:  # ✅ Proper type hints
    """
    Create both access and refresh tokens.
    
    Args:
        user: User model instance
        db: Database session
        
    Returns:
        Dictionary with access_token, refresh_token, token_type, and user info
    """
    # Create access token with user info in JWT
    access_token = create_access_token(data={
        "sub": user.email,
        "user_id": user.id,
        "role": user.role.value  # ✅ Include role in JWT
    })
    
    # Generate refresh token
    refresh_token = generate_refresh_token()
    
    # Store refresh token in database
    user.refresh_token = refresh_token
    db.commit()
    
    # Return token response with user info
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user)  # ✅ Include user in response
    }