"""Cache source-linked summaries of doctor-published patient history."""

from alembic import op
from app.store.db import ChartDigest

revision = "20261103_digest"
down_revision = "20261101_trace"
branch_labels = None
depends_on = None


def upgrade():
    ChartDigest.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("Restore a backup to roll back patient summaries.")
