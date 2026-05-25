"""数据 Schema 校验 — 使用 pandera"""

import pandera as pa
from pandera import Check, Column, DataFrameSchema
from loguru import logger


# ============================================================
# 门店主数据 Schema
# ============================================================
STORES_SCHEMA = DataFrameSchema({
    "store_code": Column(str, Check.str_length(1, 32), nullable=False),
    "store_name": Column(str, Check.str_length(1, 128), nullable=False),
    "store_type": Column(str, Check.isin(["direct", "franchise", "counter"])),
    "region": Column(str, nullable=True),
    "commercial_tier": Column(str, Check.isin(["A", "B", "C", "D"])),
    "store_area": Column(float, Check.greater_than(0), nullable=True),
    "status": Column(str, Check.isin(["active", "closed", "renovating"])),
})


# ============================================================
# 日销数据 Schema
# ============================================================
DAILY_SALES_SCHEMA = DataFrameSchema({
    "store_code": Column(str, nullable=False),
    "sale_date": Column(pa.DateTime, nullable=False),
    "category_code": Column(str, nullable=True),
    "sales_amount": Column(float, Check.greater_than_or_equal_to(0)),
    "sales_qty": Column(int, Check.greater_than_or_equal_to(0)),
    "avg_price": Column(float, Check.greater_than_or_equal_to(0), nullable=True),
    "return_amount": Column(float, Check.greater_than_or_equal_to(0)),
    "return_qty": Column(int, Check.greater_than_or_equal_to(0)),
})


# ============================================================
# 月度指标 Schema
# ============================================================
MONTHLY_METRICS_SCHEMA = DataFrameSchema({
    "store_code": Column(str, nullable=False),
    "year_month": Column(str, Check.str_matches(r"^\d{4}-\d{2}$"), nullable=False),
    "sales_amount": Column(float, Check.greater_than(0), nullable=True),
    "gross_margin": Column(float, Check.in_range(0, 1), nullable=True),
    "sales_per_sqm": Column(float, Check.greater_than(0), nullable=True),
})


def validate_stores(df):
    """校验门店数据"""
    try:
        validated = STORES_SCHEMA.validate(df, lazy=True)
        logger.info(f"[校验] 门店数据校验通过: {len(validated)} 条")
        return validated
    except pa.errors.SchemaErrors as e:
        logger.error(f"[校验] 门店数据校验失败:\n{e.failure_cases}")
        raise


def validate_daily_sales(df):
    """校验日销数据"""
    try:
        validated = DAILY_SALES_SCHEMA.validate(df, lazy=True)
        logger.info(f"[校验] 日销数据校验通过: {len(validated)} 条")
        return validated
    except pa.errors.SchemaErrors as e:
        logger.error(f"[校验] 日销数据校验失败:\n{e.failure_cases}")
        raise


def validate_monthly_metrics(df):
    """校验月度指标"""
    try:
        validated = MONTHLY_METRICS_SCHEMA.validate(df, lazy=True)
        logger.info(f"[校验] 月度指标校验通过: {len(validated)} 条")
        return validated
    except pa.errors.SchemaErrors as e:
        logger.error(f"[校验] 月度指标校验失败:\n{e.failure_cases}")
        raise
