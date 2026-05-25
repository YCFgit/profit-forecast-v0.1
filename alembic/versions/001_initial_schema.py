"""初始 Schema — 8 张业务表

Revision ID: 001_initial
Revises:
Create Date: 2026-05-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── stores ──────────────────────────────────────────────────
    op.create_table(
        "stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_code", sa.String(32), unique=True, nullable=False, index=True),
        sa.Column("store_name", sa.String(128), nullable=False),
        sa.Column("store_type", sa.String(32), nullable=False, server_default="direct"),
        sa.Column("channel_code", sa.String(32)),
        sa.Column("region", sa.String(64), index=True),
        sa.Column("province", sa.String(32)),
        sa.Column("city", sa.String(32)),
        sa.Column("address", sa.String(256)),
        sa.Column("commercial_tier", sa.String(8), nullable=False, server_default="B"),
        sa.Column("store_area", sa.Numeric(10, 2)),
        sa.Column("opening_date", sa.Date),
        sa.Column("closing_date", sa.Date),
        sa.Column("status", sa.String(16), nullable=False, server_default="active", index=True),
        sa.Column("manager_name", sa.String(64)),
        sa.Column("staff_count", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── product_categories ──────────────────────────────────────
    op.create_table(
        "product_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category_code", sa.String(32), unique=True, nullable=False),
        sa.Column("category_name", sa.String(64), nullable=False),
        sa.Column("parent_code", sa.String(32)),
        sa.Column("level", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── channels ────────────────────────────────────────────────
    op.create_table(
        "channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("channel_code", sa.String(32), unique=True, nullable=False),
        sa.Column("channel_name", sa.String(64), nullable=False),
        sa.Column("channel_type", sa.String(32), nullable=False),
        sa.Column("commission_rate", sa.Numeric(5, 4), server_default="0"),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── store_daily_sales ───────────────────────────────────────
    op.create_table(
        "store_daily_sales",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_code", sa.String(32), nullable=False, index=True),
        sa.Column("sale_date", sa.Date, nullable=False, index=True),
        sa.Column("category_code", sa.String(32)),
        sa.Column("channel_code", sa.String(32)),
        sa.Column("sales_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("sales_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_price", sa.Numeric(10, 2)),
        sa.Column("discount_rate", sa.Numeric(5, 4), server_default="1.0"),
        sa.Column("return_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("return_qty", sa.Integer, server_default="0"),
        sa.Column("customer_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("store_code", "sale_date", "category_code", "channel_code"),
    )
    op.create_index("idx_daily_sales_store_date", "store_daily_sales", ["store_code", "sale_date"])

    # ── store_monthly_metrics ───────────────────────────────────
    op.create_table(
        "store_monthly_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_code", sa.String(32), nullable=False, index=True),
        sa.Column("year_month", sa.String(7), nullable=False, index=True),
        sa.Column("sales_amount", sa.Numeric(14, 2)),
        sa.Column("gross_profit", sa.Numeric(14, 2)),
        sa.Column("gross_margin", sa.Numeric(5, 4)),
        sa.Column("sales_per_sqm", sa.Numeric(10, 2)),
        sa.Column("revenue_per_staff", sa.Numeric(10, 2)),
        sa.Column("avg_ticket", sa.Numeric(10, 2)),
        sa.Column("return_rate", sa.Numeric(5, 4)),
        sa.Column("staff_count", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("store_code", "year_month"),
    )

    # ── cost_structure ──────────────────────────────────────────
    op.create_table(
        "cost_structure",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_code", sa.String(32), nullable=False, index=True),
        sa.Column("year_month", sa.String(7), nullable=False),
        sa.Column("procurement_cost", sa.Numeric(14, 2), server_default="0"),
        sa.Column("labor_cost", sa.Numeric(14, 2), server_default="0"),
        sa.Column("rent_cost", sa.Numeric(14, 2), server_default="0"),
        sa.Column("logistics_cost", sa.Numeric(14, 2), server_default="0"),
        sa.Column("marketing_cost", sa.Numeric(14, 2), server_default="0"),
        sa.Column("commission_cost", sa.Numeric(14, 2), server_default="0"),
        sa.Column("other_cost", sa.Numeric(14, 2), server_default="0"),
        sa.Column("total_cost", sa.Numeric(14, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("store_code", "year_month"),
    )

    # ── store_staff ─────────────────────────────────────────────
    op.create_table(
        "store_staff",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_code", sa.String(32), nullable=False, index=True),
        sa.Column("staff_name", sa.String(64), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="staff"),
        sa.Column("base_salary", sa.Numeric(10, 2)),
        sa.Column("commission_rate", sa.Numeric(5, 4), server_default="0"),
        sa.Column("hire_date", sa.Date),
        sa.Column("leave_date", sa.Date),
        sa.Column("status", sa.String(16), nullable=False, server_default="active", index=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── store_targets ───────────────────────────────────────────
    op.create_table(
        "store_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_code", sa.String(32), nullable=False, index=True),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_date", sa.Date, index=True),
        sa.Column("target_month", sa.String(7), index=True),
        sa.Column("category_code", sa.String(32)),
        sa.Column("sales_target", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("profit_target", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "store_code", "target_type", "target_date", "target_month", "category_code",
        ),
    )

    # ── target_allocations ──────────────────────────────────────
    op.create_table(
        "target_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", sa.String(64), nullable=False, index=True),
        sa.Column("plan_name", sa.String(128)),
        sa.Column("total_target", sa.Numeric(14, 2), nullable=False),
        sa.Column("store_code", sa.String(32), nullable=False, index=True),
        sa.Column("baseline_profit", sa.Numeric(14, 2), nullable=False),
        sa.Column("pressure_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("allocated_target", sa.Numeric(14, 2), nullable=False),
        sa.Column("growth_rate", sa.Numeric(8, 4)),
        sa.Column("weight_score", sa.Numeric(8, 4)),
        sa.Column("weight_detail", postgresql.JSONB),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # ── risk_assessments ────────────────────────────────────────
    op.create_table(
        "risk_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", sa.String(64), nullable=False, index=True),
        sa.Column("store_code", sa.String(32), nullable=False, index=True),
        sa.Column("reachability", sa.Numeric(8, 4)),
        sa.Column("risk_level", sa.String(16), nullable=False, server_default="low", index=True),
        sa.Column("risk_factors", postgresql.JSONB),
        sa.Column("scenario_optimistic", sa.Numeric(14, 2)),
        sa.Column("scenario_neutral", sa.Numeric(14, 2)),
        sa.Column("scenario_pessimistic", sa.Numeric(14, 2)),
        sa.Column("recommendations", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("risk_assessments")
    op.drop_table("target_allocations")
    op.drop_table("store_targets")
    op.drop_table("store_staff")
    op.drop_table("cost_structure")
    op.drop_table("store_monthly_metrics")
    op.drop_index("idx_daily_sales_store_date", table_name="store_daily_sales")
    op.drop_table("store_daily_sales")
    op.drop_table("channels")
    op.drop_table("product_categories")
    op.drop_table("stores")
