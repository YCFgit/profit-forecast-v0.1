"""SQLAlchemy 数据模型"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


class Store(Base):
    """门店主数据"""
    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    store_name: Mapped[str] = mapped_column(String(128), nullable=False)
    store_type: Mapped[str] = mapped_column(String(32), nullable=False, default="direct")
    channel_code: Mapped[str | None] = mapped_column(String(32))
    region: Mapped[str | None] = mapped_column(String(64), index=True)
    province: Mapped[str | None] = mapped_column(String(32))
    city: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(String(256))
    commercial_tier: Mapped[str] = mapped_column(String(8), nullable=False, default="B")
    store_area: Mapped[float | None] = mapped_column(Numeric(10, 2))
    opening_date: Mapped[date | None] = mapped_column(Date)
    closing_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    manager_name: Mapped[str | None] = mapped_column(String(64))
    staff_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ProductCategory(Base):
    """品类主数据"""
    __tablename__ = "product_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    category_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(32))
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Channel(Base):
    """渠道主数据"""
    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    channel_name: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False)
    commission_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class StoreDailySales(Base):
    """门店日销数据"""
    __tablename__ = "store_daily_sales"
    __table_args__ = (
        UniqueConstraint("store_code", "sale_date", "category_code", "channel_code"),
        Index("idx_daily_sales_store_date", "store_code", "sale_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category_code: Mapped[str | None] = mapped_column(String(32))
    channel_code: Mapped[str | None] = mapped_column(String(32))
    sales_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    sales_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    discount_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=1.0)
    return_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    return_qty: Mapped[int] = mapped_column(Integer, default=0)
    customer_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class StoreMonthlyMetrics(Base):
    """门店月度指标"""
    __tablename__ = "store_monthly_metrics"
    __table_args__ = (UniqueConstraint("store_code", "year_month"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    year_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    sales_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    gross_profit: Mapped[float | None] = mapped_column(Numeric(14, 2))
    gross_margin: Mapped[float | None] = mapped_column(Numeric(5, 4))
    sales_per_sqm: Mapped[float | None] = mapped_column(Numeric(10, 2))
    revenue_per_staff: Mapped[float | None] = mapped_column(Numeric(10, 2))
    avg_ticket: Mapped[float | None] = mapped_column(Numeric(10, 2))
    return_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
    staff_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CostStructure(Base):
    """成本结构"""
    __tablename__ = "cost_structure"
    __table_args__ = (UniqueConstraint("store_code", "year_month"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    procurement_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    labor_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    rent_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    logistics_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    marketing_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    commission_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    other_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class StoreStaff(Base):
    """门店人员数据"""
    __tablename__ = "store_staff"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    staff_name: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="staff")
    base_salary: Mapped[float | None] = mapped_column(Numeric(10, 2))
    commission_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    hire_date: Mapped[date | None] = mapped_column(Date)
    leave_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class StoreTarget(Base):
    """目标数据（日/月）"""
    __tablename__ = "store_targets"
    __table_args__ = (
        UniqueConstraint("store_code", "target_type", "target_date", "target_month", "category_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, index=True)
    target_month: Mapped[str | None] = mapped_column(String(7), index=True)
    category_code: Mapped[str | None] = mapped_column(String(32))
    sales_target: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    profit_target: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class TargetAllocation(Base):
    """分配方案"""
    __tablename__ = "target_allocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_name: Mapped[str | None] = mapped_column(String(128))
    total_target: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    store_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    baseline_profit: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    pressure_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    allocated_target: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    growth_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    weight_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    weight_detail: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class RiskAssessment(Base):
    """风险评估记录"""
    __tablename__ = "risk_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    store_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reachability: Mapped[float | None] = mapped_column(Numeric(8, 4))
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low", index=True)
    risk_factors: Mapped[dict | None] = mapped_column(JSONB)
    scenario_optimistic: Mapped[float | None] = mapped_column(Numeric(14, 2))
    scenario_neutral: Mapped[float | None] = mapped_column(Numeric(14, 2))
    scenario_pessimistic: Mapped[float | None] = mapped_column(Numeric(14, 2))
    recommendations: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
