"""Add persistent charts and explicit doctor connections."""

import sqlalchemy as sa

from alembic import op
from app.store.db import (
    ChartActivity,
    ChartConnection,
    ClinicalSummary,
    ConnectionCode,
    ConsentEvent,
)

revision = "20261030_chart"
down_revision = "20261028_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {item["name"] for item in sa.inspect(bind).get_columns("runrow")}
    if "title" not in columns:
        op.add_column(
            "runrow", sa.Column("title", sa.String(), nullable=False, server_default="Report")
        )
    if "submitted_by" not in columns:
        op.add_column("runrow", sa.Column("submitted_by", sa.String(), nullable=True))
        op.create_index("ix_runrow_submitted_by", "runrow", ["submitted_by"])
    if "archived" not in columns:
        op.add_column(
            "runrow", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    if "submission_key" not in columns:
        op.add_column("runrow", sa.Column("submission_key", sa.String(), nullable=True))
    if "submission_digest" not in columns:
        op.add_column("runrow", sa.Column("submission_digest", sa.String(), nullable=True))
    uniques = {
        constraint["name"] for constraint in sa.inspect(bind).get_unique_constraints("runrow")
    }
    if "uq_run_submission" not in uniques:
        with op.batch_alter_table("runrow") as batch:
            batch.create_unique_constraint("uq_run_submission", ["submitted_by", "submission_key"])
    for table in (ChartConnection, ConnectionCode, ChartActivity, ClinicalSummary, ConsentEvent):
        table.__table__.create(bind, checkfirst=True)
    connection_columns = {item["name"] for item in sa.inspect(bind).get_columns("chartconnection")}
    if "request_id" not in connection_columns:
        op.add_column("chartconnection", sa.Column("request_id", sa.String(), nullable=True))
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("chartconnection")}
    if "ix_chartconnection_request_id" not in indexes:
        op.create_index(
            "ix_chartconnection_request_id", "chartconnection", ["request_id"], unique=True
        )
    consent_columns = {item["name"] for item in sa.inspect(bind).get_columns("consentevent")}
    if "consent_text" not in consent_columns:
        op.add_column(
            "consentevent",
            sa.Column("consent_text", sa.String(), nullable=False, server_default=""),
        )
    bind.execute(sa.text("UPDATE runrow SET share_code = NULL, share_expires = NULL"))
    bind.execute(sa.text("DELETE FROM rungrant"))


def downgrade() -> None:
    raise RuntimeError("Restore a backup to roll back chart data.")
