"""Introduce account and access tables while preserving legacy ownerless runs."""

import sqlalchemy as sa
from sqlmodel import SQLModel

from alembic import op
from app.store import db  # noqa: F401 - register SQLModel tables

revision = "20261028_auth"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("runrow") and "owner_id" not in {
        c["name"] for c in inspector.get_columns("runrow")
    }:
        op.add_column("runrow", sa.Column("owner_id", sa.String(), nullable=True))
    SQLModel.metadata.create_all(bind=bind, checkfirst=True)
    if "ix_runrow_owner_id" not in {idx["name"] for idx in sa.inspect(bind).get_indexes("runrow")}:
        op.create_index("ix_runrow_owner_id", "runrow", ["owner_id"])
    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("runrow")}
    if "ix_runrow_share_code" not in indexes:
        # Legacy ownerless records are inaccessible; old share codes must not
        # block creation of a globally unique index.
        bind.execute(
            sa.text(
                "UPDATE runrow SET share_code = NULL, share_expires = NULL WHERE owner_id IS NULL"
            )
        )
        op.create_index("ix_runrow_share_code", "runrow", ["share_code"], unique=True)


def downgrade() -> None:
    raise RuntimeError(
        "Downgrading authentication would discard account data; restore a backup instead."
    )
