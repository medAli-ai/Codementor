"""
Admin-only routes.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import get_current_admin, get_current_superadmin
from app.db.session import get_db
from app.models.conversation import Conversation, Message
from app.models.user import User, UserRole

router = APIRouter()


@router.get("/stats")
async def get_admin_stats(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    conversation_count = (await db.execute(select(func.count(Conversation.id)))).scalar_one()
    message_count = (await db.execute(select(func.count(Message.id)))).scalar_one()

    users_by_role = {}
    for role in UserRole:
        count = (
            await db.execute(select(func.count(User.id)).where(User.role == role))
        ).scalar_one()
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
async def list_all_users(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User))
    users = result.scalars().all()

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
    superadmin: User = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        from fastapi import HTTPException

        raise HTTPException(404, "User not found")

    old_role = user.role.value
    user.role = UserRole.ADMIN
    await db.commit()

    return {
        "message": f"User {user.username} promoted from {old_role} to admin",
        "user": {
            "id": user.id,
            "username": user.username,
            "old_role": old_role,
            "new_role": user.role.value,
        },
    }
