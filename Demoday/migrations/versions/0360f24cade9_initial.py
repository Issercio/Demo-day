"""Initial

Revision ID: 0360f24cade9
Revises: 
Create Date: 2025-06-27 15:16:59.360031

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0360f24cade9'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False)
    )
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False, unique=True),
        sa.Column('password', sa.String(length=120), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True)
    )
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=True)
    )
    op.create_table(
        'prices',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True)
    )
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False)
    )

def downgrade():
    op.drop_table('reviews')
    op.drop_table('prices')
    op.drop_table('products')
    op.drop_table('users')
    op.drop_table('categories')
