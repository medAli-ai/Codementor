from datetime import datetime, timedelta
from typing import Optional
import hashlib
import base64
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _prehash_password(password: str) -> str:
    """
    Pre-hash password with SHA256 to avoid bcrypt's 72-byte limit.
    
    This is recommended by OWASP and security experts:
    - Allows unlimited password length
    - No security downside (SHA256 is one-way)
    - bcrypt still provides key stretching
    
    Returns base64-encoded hash (consistent length, URL-safe)
    """
    # Hash to bytes
    hash_bytes = hashlib.sha256(password.encode('utf-8')).digest()
    # Encode as base64 for consistent format (44 chars, always < 72 bytes)
    return base64.b64encode(hash_bytes).decode('ascii')


def get_password_hash(password: str) -> str:
    """
    Hash a password for storage.
    
    Uses SHA256 pre-hash + bcrypt for security and compatibility.
    """
    prehashed = _prehash_password(password)
    return pwd_context.hash(prehashed)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    prehashed = _prehash_password(plain_password)
    return pwd_context.verify(prehashed, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None