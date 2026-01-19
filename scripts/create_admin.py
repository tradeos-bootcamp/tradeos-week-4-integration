# migrations/versions/001_add_users_table.py
"""add users table

Revision ID: 001
Revises: 
Create Date: 2024-01-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Создаем enum для ролей
    user_role_enum = postgresql.ENUM('admin', 'manager', 'user', name='userrole')
    user_role_enum.create(op.get_bind())
    
    # Создаем таблицу users
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('role', user_role_enum, nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создаем индексы
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    
    # Добавляем связь между продуктами и пользователями (если нужно)
    op.add_column('products', sa.Column('created_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_products_created_by', 'products', 'users', ['created_by_id'], ['id'])

def downgrade() -> None:
    # Удаляем связь
    op.drop_constraint('fk_products_created_by', 'products', type_='foreignkey')
    op.drop_column('products', 'created_by_id')
    
    # Удаляем таблицу users
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    
    # Удаляем enum
    user_role_enum = postgresql.ENUM('admin', 'manager', 'user', name='userrole')
    user_role_enum.drop(op.get_bind())