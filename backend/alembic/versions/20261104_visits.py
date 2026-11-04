"""Patient-owned visits in independent doctor workspaces; preserve earlier records."""

import sqlalchemy as sa

from alembic import op
from app.store.db import Visit, VisitReference

revision = "20261104_visits"
down_revision = "20261104_prescriptions"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Visit.__table__.create(bind, checkfirst=True)
    if "visit_id" not in {c["name"] for c in sa.inspect(bind).get_columns("runrow")}:
        with op.batch_alter_table("runrow") as batch:
            batch.add_column(sa.Column("visit_id", sa.String(), nullable=True))
            batch.create_foreign_key("fk_runrow_visit", "visit", ["visit_id"], ["id"])
            batch.create_index("ix_runrow_visit_id", ["visit_id"])
    VisitReference.__table__.create(bind, checkfirst=True)


def downgrade():
    raise RuntimeError("Visit history must be preserved. Restore a backup for rollback.")
