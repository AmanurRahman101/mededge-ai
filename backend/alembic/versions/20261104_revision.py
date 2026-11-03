"""Add optimistic revisions to clinical note drafts."""

import sqlalchemy as sa

from alembic import op

revision = "20261104_revision"
down_revision = "20261103_digest"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("clinicalsummary")}
    if "revision" not in columns:
        op.add_column(
            "clinicalsummary",
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade():
    op.drop_column("clinicalsummary", "revision")
