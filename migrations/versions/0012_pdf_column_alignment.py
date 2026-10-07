"""Align marketing columns with the physical names from Creator DB.pdf."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_pdf_column_alignment"
down_revision: str | None = "0011_core_schema_lengths"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def columns(table_name: str) -> set[str]:
        inspector.clear_cache()
        return {column["name"] for column in inspector.get_columns(table_name)}

    def add_column_if_missing(table_name: str, name: str, column_type: sa.types.TypeEngine) -> None:
        if name not in columns(table_name):
            op.add_column(table_name, sa.Column(name, column_type, nullable=True))

    def rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
        current = columns(table_name)
        if old_name in current and new_name not in current:
            op.alter_column(table_name, old_name, new_column_name=new_name)

    for name, column_type in (
        ("persona_name", sa.String(length=30)),
        ("persona_age", sa.Integer()),
        ("persona_gender", sa.String(length=10)),
        ("persona_main_goal", sa.String(length=60)),
        ("persona_challenge", sa.String(length=50)),
        ("persona_interest", sa.String(length=200)),
        ("persona_routine", sa.String(length=300)),
        ("persona_journey", sa.String(length=250)),
        ("persona_trigger", sa.String(length=200)),
    ):
        add_column_if_missing("planning", name, column_type)

    for old_name, new_name in (
        ("info", "planning_info"),
        ("static_amount", "planning_static_amount"),
        ("carousel_amount", "planning_carousel_amount"),
        ("stories_amount", "planning_stories_amount"),
        ("special_dates", "planning_special_dates"),
        ("start_period", "planning_start_period"),
        ("end_period", "planning_end_period"),
    ):
        rename_column_if_needed("planning", old_name, new_name)

    for old_name, new_name in (
        ("title", "post_title"),
        ("objective", "post_objective"),
        ("big_idea", "post_big_idea"),
        ("main_message", "post_main_message"),
        ("headline", "post_headline"),
        ("status", "post_status"),
        ("format", "content_format"),
        ("ratio", "art_ratio"),
        ("resolution", "art_resolution"),
    ):
        rename_column_if_needed("post_structure", old_name, new_name)

    for name, column_type in (
        ("brand_segment", sa.String(length=30)),
        ("brand_promise", sa.String(length=250)),
        ("brand_values", sa.String(length=100)),
        ("brand_main_hashtags", sa.String(length=200)),
        ("brand_goals", sa.String(length=1800)),
        ("brand_indicators", sa.String(length=250)),
        ("brand_inspirations", sa.String(length=1500)),
        ("brand_restrictions", sa.String(length=200)),
    ):
        add_column_if_missing("brand_colors", name, column_type)

    rename_column_if_needed("generated_image", "status", "image_status")


def downgrade() -> None:
    op.alter_column("generated_image", "image_status", new_column_name="status")
    for name in (
        "brand_restrictions",
        "brand_inspirations",
        "brand_indicators",
        "brand_goals",
        "brand_main_hashtags",
        "brand_values",
        "brand_promise",
        "brand_segment",
    ):
        op.drop_column("brand_colors", name)

    for name in (
        "persona_trigger",
        "persona_journey",
        "persona_routine",
        "persona_interest",
        "persona_challenge",
        "persona_main_goal",
        "persona_gender",
        "persona_age",
        "persona_name",
    ):
        op.drop_column("planning", name)

    for old_name, new_name in (
        ("post_title", "title"),
        ("post_objective", "objective"),
        ("post_big_idea", "big_idea"),
        ("post_main_message", "main_message"),
        ("post_headline", "headline"),
        ("post_status", "status"),
        ("content_format", "format"),
        ("art_ratio", "ratio"),
        ("art_resolution", "resolution"),
    ):
        op.alter_column("post_structure", old_name, new_column_name=new_name)

    for old_name, new_name in (
        ("planning_info", "info"),
        ("planning_static_amount", "static_amount"),
        ("planning_carousel_amount", "carousel_amount"),
        ("planning_stories_amount", "stories_amount"),
        ("planning_special_dates", "special_dates"),
        ("planning_start_period", "start_period"),
        ("planning_end_period", "end_period"),
    ):
        op.alter_column("planning", old_name, new_column_name=new_name)
