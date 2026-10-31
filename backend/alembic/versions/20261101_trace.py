"""Persist the pipeline trace so a finished record can show how it was made."""

import sqlalchemy as sa

from alembic import op

revision = "20261101_trace"
down_revision = "20261030_amendment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {item["name"] for item in sa.inspect(bind).get_columns("runrow")}
    if "trace_json" not in columns:
        op.add_column("runrow", sa.Column("trace_json", sa.Text(), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Restore a backup to roll back the persisted trace.")
