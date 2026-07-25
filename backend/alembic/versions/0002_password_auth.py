"""password auth: nullable google_sub, unique email, token tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-25

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text("SELECT email FROM users GROUP BY email HAVING count(*) > 1")
    ).fetchall()
    if duplicates:
        emails = ", ".join(row[0] for row in duplicates)
        raise RuntimeError(
            "Cannot add a UNIQUE constraint on users.email — duplicates exist: "
            f"{emails}. Merge or remove these rows, then re-run the migration."
        )

    op.alter_column("users", "google_sub", existing_type=sa.String(), nullable=True)
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_check_constraint(
        "ck_users_has_credential",
        "users",
        "google_sub IS NOT NULL OR password_hash IS NOT NULL",
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])


def downgrade():
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_constraint("ck_users_has_credential", "users", type_="check")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "password_hash")
    op.alter_column("users", "google_sub", existing_type=sa.String(), nullable=False)
