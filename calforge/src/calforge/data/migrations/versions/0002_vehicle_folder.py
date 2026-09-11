"""Vehicle folder: attachments, history timeline, ECU file versioning.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "vehicle_id",
            sa.Integer(),
            sa.ForeignKey("vehicles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"])
    op.create_index("ix_attachments_vehicle", "attachments", ["vehicle_id"])

    op.create_table(
        "history_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "vehicle_id",
            sa.Integer(),
            sa.ForeignKey("vehicles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
    )
    op.create_index(
        "ix_history_vehicle_occurred", "history_entries", ["vehicle_id", "occurred_at"]
    )

    with op.batch_alter_table("ecu_files") as batch:
        batch.add_column(sa.Column("parent_file_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_ecu_files_parent", "ecu_files", ["parent_file_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("ecu_files") as batch:
        batch.drop_constraint("fk_ecu_files_parent", type_="foreignkey")
        batch.drop_column("parent_file_id")
    op.drop_index("ix_history_vehicle_occurred", table_name="history_entries")
    op.drop_table("history_entries")
    op.drop_index("ix_attachments_vehicle", table_name="attachments")
    op.drop_index("ix_attachments_sha256", table_name="attachments")
    op.drop_table("attachments")
