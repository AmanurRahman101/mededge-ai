"""Link clinical summary amendments to their published version."""

import sqlalchemy as sa

from alembic import op

revision = "20261030_amendment"
down_revision = "20261030_chart"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {item["name"] for item in sa.inspect(bind).get_columns("clinicalsummary")}
    if "amends_id" not in columns:
        op.add_column("clinicalsummary", sa.Column("amends_id", sa.String(), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Restore a backup to roll back clinical summary amendments.")
