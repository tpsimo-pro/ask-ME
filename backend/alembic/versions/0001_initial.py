"""initial tables

Revision ID: 0001
Revises:
Create Date: 2026-07-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("google_sub", sa.String(), nullable=False, unique=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("code_snippet", sa.Text(), nullable=False),
        sa.Column("suggestions", sa.JSON(), nullable=False),
        sa.Column("generated_tests", sa.Text(), nullable=False),
        sa.Column("security_risks", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_analyses_user_created", "analyses", ["user_id", "created_at"])


def downgrade():
    op.drop_index("ix_analyses_user_created", table_name="analyses")
    op.drop_table("analyses")
    op.drop_table("users")
