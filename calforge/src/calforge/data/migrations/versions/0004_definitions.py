"""Map packs: definition sources, map definitions, matchers; candidate link.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "definition_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_table(
        "map_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("definition_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("offset", sa.Integer(), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("cols", sa.Integer(), nullable=False),
        sa.Column("element_size", sa.Integer(), nullable=False),
        sa.Column("endianness", sa.String(2), nullable=False),
        sa.Column("factor", sa.Float(), nullable=False),
        sa.Column("value_offset", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_map_definitions_source", "map_definitions", ["source_id"])
    op.create_table(
        "definition_matchers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("definition_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_definition_matchers_source", "definition_matchers", ["source_id"])

    with op.batch_alter_table("map_candidates") as batch:
        batch.add_column(sa.Column("definition_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_map_candidates_definition",
            "map_definitions",
            ["definition_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("map_candidates") as batch:
        batch.drop_constraint("fk_map_candidates_definition", type_="foreignkey")
        batch.drop_column("definition_id")
    op.drop_index("ix_definition_matchers_source", table_name="definition_matchers")
    op.drop_table("definition_matchers")
    op.drop_index("ix_map_definitions_source", table_name="map_definitions")
    op.drop_table("map_definitions")
    op.drop_table("definition_sources")
