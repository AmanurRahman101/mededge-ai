"""Structured doctor-authored prescriptions, including voice-only input."""

import sqlalchemy as sa

from alembic import op

revision = "20261104_prescriptions"
down_revision = "20261104_medicines"
branch_labels = None
depends_on = None


def upgrade():
    for table, column, default in [
        ("runrow", "input_mode", "image"),
        ("clinicalsummary", "prescription_json", ""),
    ]:
        columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
        if column not in columns:
            op.add_column(
                table, sa.Column(column, sa.String(), nullable=False, server_default=default)
            )


def downgrade():
    op.drop_column("clinicalsummary", "prescription_json")
    op.drop_column("runrow", "input_mode")
