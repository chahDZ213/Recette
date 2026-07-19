"""Advanced analysis: annotations and map candidates.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "annotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ecu_file_id",
            sa.Integer(),
            sa.ForeignKey("ecu_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("offset", sa.Integer(), nullable=False),
        sa.Column("length", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_annotations_file", "annotations", ["ecu_file_id", "offset"])

    op.create_table(
        "map_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ecu_file_id",
            sa.Integer(),
            sa.ForeignKey("ecu_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("offset", sa.Integer(), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("cols", sa.Integer(), nullable=False),
        sa.Column("element_size", sa.Integer(), nullable=False),
        sa.Column("endianness", sa.String(2), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_map_candidates_file", "map_candidates", ["ecu_file_id", "offset"])


def downgrade() -> None:
    op.drop_index("ix_map_candidates_file", table_name="map_candidates")
    op.drop_table("map_candidates")
    op.drop_index("ix_annotations_file", table_name="annotations")
    op.drop_table("annotations")
