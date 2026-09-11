"""Initial schema: vehicles, projects, ecu_files.

Revision ID: 0001
Revises:
Create Date: 2026-07-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("make", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("vin", sa.String(17), nullable=True, unique=True),
        sa.Column("license_plate", sa.String(20), nullable=True),
        sa.Column("engine_code", sa.String(50), nullable=True),
        sa.Column("ecu_type", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "vehicle_id",
            sa.Integer(),
            sa.ForeignKey("vehicles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_table(
        "ecu_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "vehicle_id",
            sa.Integer(),
            sa.ForeignKey("vehicles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("format_name", sa.String(100), nullable=True),
        sa.Column("identified_facts", sa.JSON(), nullable=False),
        sa.Column("hypotheses", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_ecu_files_sha256", "ecu_files", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_ecu_files_sha256", table_name="ecu_files")
    op.drop_table("ecu_files")
    op.drop_table("projects")
    op.drop_table("vehicles")
