"""
Create superadmin account.
Usage: uv run python scripts/create_superadmin.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def create_superadmin(email: str, username: str, password: str):
    db = SessionLocal()

    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            if existing.role == UserRole.SUPERADMIN:
                print(f"✅ {username} is already a superadmin!")
            else:
                existing.role = UserRole.SUPERADMIN
                db.commit()
                print(f"✅ Upgraded {username} to superadmin!")
            return

        user = User(
            email=email,
            username=username,
            hashed_password=get_password_hash(password),
            role=UserRole.SUPERADMIN,
            is_active=True,
        )

        db.add(user)
        db.commit()

        print(f"✅ Superadmin created: {username}")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("🔐 Create Superadmin\n")
    email = input("Email: ").strip()
    username = input("Username: ").strip()
    password = input("Password: ").strip()

    if not all([email, username, password]) or len(password) < 8:
        print("❌ Invalid input!")
        sys.exit(1)

    create_superadmin(email, username, password)
