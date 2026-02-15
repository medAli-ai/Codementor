"""
Role-Based Access Control (RBAC)
"""
from fastapi import Depends, HTTPException, status
from app.models.user import User, UserRole
from app.core.deps import get_current_user

def require_role(required_role: UserRole):
    """Role hierarchy: SUPERADMIN > ADMIN > USER"""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        role_hierarchy = {
            UserRole.USER: 1,
            UserRole.ADMIN: 2,
            UserRole.SUPERADMIN: 3
        }
        
        user_level = role_hierarchy.get(current_user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role.value} role or higher"
            )
        
        return current_user
    
    return role_checker


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin or superadmin."""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return current_user


def get_current_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """Require superadmin only."""
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Superadmin access required")
    return current_user


def check_ownership_or_admin(resource_user_id: int, current_user: User) -> bool:
    """Check if user owns resource OR is admin."""
    return resource_user_id == current_user.id or current_user.role in [UserRole.ADMIN, UserRole.SUPERADMIN]