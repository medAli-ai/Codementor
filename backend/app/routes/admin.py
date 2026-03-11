"""
Admin-only routes.

Demonstrates RBAC protection using get_current_admin dependency.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.rbac import get_current_admin, get_current_superadmin
from app.db.session import get_db
from app.models.user import User

router = APIRouter()


@router.get("/stats")
async def get_admin_stats(
    admin: User = Depends(get_current_admin),  # ✅ Requires ADMIN or SUPERADMIN
    db: Session = Depends(get_db),
):
    """
    Get system statistics (admin only).

    Regular users will get 403 Forbidden.
    Admins and superadmins can access.
    """
    from app.models.conversation import Conversation, Message
    from app.models.user import User

    # Get counts
    user_count = db.query(User).count()
    conversation_count = db.query(Conversation).count()
    message_count = db.query(Message).count()

    # Count by role
    from app.models.user import UserRole

    users_by_role = {}
    for role in UserRole:
        count = db.query(User).filter(User.role == role).count()
        users_by_role[role.value] = count

    return {
        "admin": {"username": admin.username, "role": admin.role.value},
        "stats": {
            "total_users": user_count,
            "total_conversations": conversation_count,
            "total_messages": message_count,
            "users_by_role": users_by_role,
        },
    }


@router.get("/users")
async def list_all_users(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """
    List all users (admin only).
    """
    users = db.query(User).all()

    return {
        "total": len(users),
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role.value,
                "is_active": u.is_active,
                "created_at": u.created_at,
            }
            for u in users
        ],
    }


@router.post("/promote/{user_id}")
async def promote_user(
    user_id: int,
    superadmin: User = Depends(get_current_superadmin),  # ✅ SUPERADMIN ONLY!
    db: Session = Depends(get_db),
):
    """
    Promote a user to admin (superadmin only).

    Regular users and even admins cannot access this!
    Only superadmins can promote users.
    """
    from app.models.user import UserRole

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        from fastapi import HTTPException

        raise HTTPException(404, "User not found")

    old_role = user.role.value
    user.role = UserRole.ADMIN
    db.commit()

    return {
        "message": f"User {user.username} promoted from {old_role} to admin",
        "user": {
            "id": user.id,
            "username": user.username,
            "old_role": old_role,
            "new_role": user.role.value,
        },
    }
