"""合并管理员 — Admin 模型并入 User 模型

Revision ID: 4c95f5b53a8a
Revises: fe15f096a5de
Create Date: 2026-07-01 13:58:36.834302

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '4c95f5b53a8a'
down_revision = 'fe15f096a5de'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=True))
    op.execute("UPDATE users SET is_admin = TRUE WHERE username = 'admin'")
    op.execute("UPDATE users SET is_admin = FALSE WHERE is_admin IS NULL")
    op.alter_column('users', 'is_admin', existing_type=sa.Boolean(), nullable=False, server_default='0')

    with op.batch_alter_table('admins', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('username'))
    op.drop_table('admins')


def downgrade():
    op.create_table('admins',
        sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('username', mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=50), nullable=False),
        sa.Column('password_hash', mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=200), nullable=False),
        sa.Column('created_at', mysql.DATETIME(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        mysql_collate='utf8mb4_unicode_ci',
        mysql_default_charset='utf8mb4',
        mysql_engine='InnoDB'
    )
    with op.batch_alter_table('admins', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('username'), ['username'], unique=True)

    if_exists = sa.text("SELECT 1 FROM admins WHERE username = 'admin'")
    conn = op.get_bind()
    result = conn.execute(if_exists).fetchone()
    if not result:
        conn.execute(
            sa.text("INSERT INTO admins (username, password_hash) "
                    "SELECT username, password_hash FROM users WHERE username = 'admin'")
        )
    op.drop_column('users', 'is_admin')
