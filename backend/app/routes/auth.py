from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user
from app.core.security import create_tokens, get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import RefreshRequest, Token, UserCreate, UserResponse

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""

    # Check if email exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Check if username exists
    existing_username = db.query(User).filter(User.username == user.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )

    # Create user
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=get_password_hash(user.password),
        is_active=True,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@router.post("/login", response_model=Token)  # ✅ Add this line
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    return create_tokens(user, db)


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    Get current user info (requires authentication)
    """
    return current_user


@router.post("/refresh")
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    """
    Exchange a valid refresh token for a new access + refresh token pair.

    WHY token rotation?
    After this call the old refresh token is overwritten in the DB.
    If a stolen token is used first, the legitimate user's next refresh
    will fail (token mismatch) — alerting them to re-login.
    """
    # Look up user by the refresh token stored in DB
    user = db.query(User).filter(User.refresh_token == body.refresh_token).first()

    # No match means invalid, expired, or already rotated token
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    # Issue new token pair — this overwrites user.refresh_token in DB
    return create_tokens(user, db)


@router.post("/logout")
def logout(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Invalidate the refresh token so it can't be used again after logout.
    The client must also clear its localStorage.
    """
    current_user.refresh_token = None
    db.commit()
    return {"message": "Logged out successfully"}
