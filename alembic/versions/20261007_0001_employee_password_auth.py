from alembic import op
import sqlalchemy as sa

revision = "20261007_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for constraint in inspector.get_unique_constraints("users"):
        if constraint.get("column_names") == ["email"] and constraint.get("name"):
            op.drop_constraint(constraint["name"], "users", type_="unique")

    for index in inspector.get_indexes("users"):
        if index.get("unique") and index.get("column_names") == ["email"]:
            if not index.get("duplicates_constraint"):
                op.drop_index(index["name"], table_name="users")

    inspector = sa.inspect(bind)
    unique_constraints = inspector.get_unique_constraints("users")
    unique_indexes = inspector.get_indexes("users")
    employee_id_unique = any(
        item.get("column_names") == ["username"]
        for item in [*unique_constraints, *unique_indexes]
        if item.get("unique", True)
    )
    if not employee_id_unique:
        op.create_index("uq_users_employee_id", "users", ["username"], unique=True)

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("users", recreate="always") as batch:
            batch.alter_column(
                "email",
                existing_type=sa.String(length=255),
                nullable=True,
            )
    else:
        op.alter_column(
            "users",
            "email",
            existing_type=sa.String(length=255),
            nullable=True,
        )


def downgrade() -> None:
    raise RuntimeError(
        "Employee-only accounts have no email to restore; this migration cannot be downgraded safely."
    )
