"""Add durable guest leases without changing existing account rows."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "guest_leases",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("actions", sa.Integer(), nullable=False),
    )
    op.create_index("ix_guest_leases_expires_at", "guest_leases", ["expires_at"])


def downgrade():
    op.drop_table("guest_leases")
