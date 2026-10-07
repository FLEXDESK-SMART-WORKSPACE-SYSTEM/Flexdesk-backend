from alembic import op
import sqlalchemy as sa

revision = "20261007_0002"
down_revision = "20261007_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), server_default="employee", nullable=False),
    )
    op.execute("UPDATE users SET role = 'admin' WHERE username = 'admin'")


def downgrade() -> None:
    op.drop_column("users", "role")
