"""add_user_role_column

Revision ID: 6f9bff6ddd24
Revises: 7fe7cd84d222
Create Date: 2026-02-14 19:31:41.173744

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f9bff6ddd24'
down_revision: Union[str, Sequence[str], None] = '7fe7cd84d222'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add role column to users table with RBAC support."""
    
    # 1. Create enum type in PostgreSQL
    op.execute("CREATE TYPE userrole AS ENUM ('user', 'admin', 'superadmin')")
    
    # 2. Add role column to users table
    op.add_column(
        'users',
        sa.Column(
            'role',
            sa.Enum('user', 'admin', 'superadmin', name='userrole'),
            nullable=False,
            server_default='user'
        )
    )
    
    # 3. Create index for faster role-based queries
    op.create_index('ix_users_role', 'users', ['role'])
   
   
def downgrade() -> None:
    """Remove role column from users table."""
    
    # 1. Drop index
    op.drop_index('ix_users_role', table_name='users')
    
    # 2. Drop column
    op.drop_column('users', 'role')
    
    # 3. Drop enum type
    op.execute("DROP TYPE userrole")
