"""Patient-reported current medicines; preserve all existing chart data."""

from alembic import op
from app.store.db import CurrentMedicine

revision = "20261104_medicines"
down_revision = "20261104_revision"
branch_labels = None
depends_on = None


def upgrade():
    CurrentMedicine.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    CurrentMedicine.__table__.drop(op.get_bind(), checkfirst=True)
