"""Initial migration

Revision ID: 447035678cd1
Revises: 
Create Date: 2026-01-19 16:08:49.118786

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '447035678cd1'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('telegram_id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('last_active', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('telegram_id')
    )
    
    # Create profiles table
    op.create_table('profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=True),
    sa.Column('age', sa.Integer(), nullable=True),
    sa.Column('gender', sa.String(length=20), nullable=True),
    sa.Column('bio', sa.Text(), nullable=True),
    sa.Column('location', sa.String(length=100), nullable=True),
    sa.Column('interests', sa.JSON(), nullable=True),
    sa.Column('preferred_age_min', sa.Integer(), nullable=True),
    sa.Column('preferred_age_max', sa.Integer(), nullable=True),
    sa.Column('preferred_gender', sa.String(length=20), nullable=True),
    sa.Column('preferred_location', sa.String(length=100), nullable=True),
    sa.Column('profile_completeness', sa.Float(), nullable=True),
    sa.Column('photo_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    
    # Create photos table
    op.create_table('photos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('profile_id', sa.Integer(), nullable=True),
    sa.Column('s3_path', sa.String(length=255), nullable=False),
    sa.Column('telegram_file_id', sa.String(length=255), nullable=True),
    sa.Column('is_main', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create ratings table
    op.create_table('ratings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('profile_id', sa.Integer(), nullable=True),
    sa.Column('primary_rating', sa.Float(), nullable=True),
    sa.Column('behavioral_rating', sa.Float(), nullable=True),
    sa.Column('combined_rating', sa.Float(), nullable=True),
    sa.Column('last_calculated', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('profile_id')
    )
    
    # Create interactions table
    op.create_table('interactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('from_profile_id', sa.Integer(), nullable=True),
    sa.Column('to_profile_id', sa.Integer(), nullable=True),
    sa.Column('type', sa.String(length=10), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['from_profile_id'], ['profiles.id'], ),
    sa.ForeignKeyConstraint(['to_profile_id'], ['profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create matches table
    op.create_table('matches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('profile_id_1', sa.Integer(), nullable=True),
    sa.Column('profile_id_2', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('initiated_chat', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['profile_id_1'], ['profiles.id'], ),
    sa.ForeignKeyConstraint(['profile_id_2'], ['profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create messages table
    op.create_table('messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('match_id', sa.Integer(), nullable=True),
    sa.Column('sender_id', sa.Integer(), nullable=True),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('read', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('messages')
    op.drop_table('matches')
    op.drop_table('interactions')
    op.drop_table('ratings')
    op.drop_table('photos')
    op.drop_table('profiles')
    op.drop_table('users')
