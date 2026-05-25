# profit-forecast v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a sales-driven profit forecasting system by copying the existing profit-forecast project and adapting all modules to use 3 sales data tables as primary input, with MySQL as metadata store.

**Architecture:** Copy existing project to `profit-forecast-v0.1/`, then modify each module (data, baseline, profit, risk, allocation, agents, API, frontend, Docker) to聚焦销售数据。保留所有模块结构，调整数据来源和业务逻辑。

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, PyMySQL, pandas, scikit-learn, statsmodels, Prophet, React, TypeScript, Ant Design, ECharts, Docker, MySQL, Redis

**Design Spec:** `docs/superpowers/specs/2026-05-25-profit-forecast-v0.1-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/data/collectors/sales_collector.py` | Unified sales data collector for 3 tables |
| `src/forecasting/discount/__init__.py` | Discount prediction module init |
| `src/forecasting/discount/predictor.py` | Discount rate predictor (YoY + brand season) |
| `src/forecasting/discount/brand_season_matrix.py` | Brand season discount decay matrix |
| `scripts/etl_sql/09_unified_sales.sql` | Unified sales wide table SQL |
| `scripts/etl_sql/10_discount_matrix.sql` | Discount matrix build SQL |

### Modified Files (key changes)

| File | Change |
|------|--------|
| `src/db/session.py` | PostgreSQL → MySQL (pymysql) |
| `src/db/models.py` | Adapt to MySQL syntax |
| `src/data/collectors/starrocks_collector.py` | Add 3 table query methods |
| `src/profit/profit_calculator.py` | Read real P&L data from storeloss |
| `src/profit/cost_estimator.py` | Adapt to new data structure |
| `src/risk/risk_assessor.py` | Sales-only risk assessment |
| `src/forecasting/models/arima_model.py` | Remove exogenous variables |
| `src/forecasting/models/prophet_model.py` | Remove regressors |
| `src/forecasting/rules/baseline_engine.py` | Remove customer flow/inventory inputs |
| `src/agents/*.py` | Adjust agent responsibilities |
| `src/api/routes/*.py` | Adapt endpoints |
| `docker-compose.yml` | PostgreSQL → MySQL |
| `docker/init.sql` | PostgreSQL → MySQL syntax |
| `pyproject.toml` | psycopg2 → pymysql |
| `.env.example` | Add table name configs |

---

## Phase 0: Project Setup

### Task 0.1: Copy project and initialize

**Files:**
- Create: `profit-forecast-v0.1/` (entire directory)

- [ ] **Step 1: Copy project excluding dependencies and caches**

```bash
cd /Users/ycf/Documents/Claude_Code/Claude_Priject
cp -r profit-forecast/ profit-forecast-v0.1/
cd profit-forecast-v0.1/
rm -rf node_modules .venv .git __pycache__ .pytest_cache .coverage frontend/dist frontend/node_modules
```

- [ ] **Step 2: Initialize new git repository**

```bash
cd /Users/ycf/Documents/Claude_Code/Claude_Priject/profit-forecast-v0.1
git init
git add .
git commit -m "chore: copy from profit-forecast as v0.1 starting point"
```

- [ ] **Step 3: Create Python virtual environment and install dependencies**

```bash
cd /Users/ycf/Documents/Claude_Code/Claude_Priject/profit-forecast-v0.1
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

- [ ] **Step 4: Verify project structure**

```bash
ls -la src/ agents/ allocation/ api/ baseline/ core/ data/ db/ forecasting/ profit/ risk/
```

Expected: All source directories exist.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: clean up copied project, init venv"
```

---

## Phase 1: Database Layer (PostgreSQL → MySQL)

### Task 1.1: Update database session for MySQL

**Files:**
- Modify: `src/db/session.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write test for MySQL connection**

```python
# tests/unit/test_db_session.py
import pytest
from src.db.session import get_engine, get_session

def test_engine_url_is_mysql():
    engine = get_engine()
    assert "mysql" in str(engine.url)

def test_session_can_be_created():
    session = get_session()
    assert session is not None
    session.close()
```

- [ ] **Step 2: Update pyproject.toml dependencies**

In `pyproject.toml`, replace `psycopg2-binary` with `pymysql`:

```toml
dependencies = [
    # ... other deps ...
    "pymysql>=1.1.0",
    "cryptography>=41.0.0",  # for mysql auth
    # remove: "psycopg2-binary"
]
```

- [ ] **Step 3: Update src/db/session.py**

```python
"""数据库会话管理"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "ycf0312!")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "profit_forecast")

DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
        logger.info(f"MySQL engine created: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def init_db():
    """初始化数据库表"""
    from src.db.models import Base
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables created")
```

- [ ] **Step 4: Run test to verify**

```bash
pytest tests/unit/test_db_session.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/db/session.py pyproject.toml tests/unit/test_db_session.py
git commit -m "feat(db): switch from PostgreSQL to MySQL"
```

### Task 1.2: Update database models for MySQL

**Files:**
- Modify: `src/db/models.py`
- Modify: `docker/init.sql`

- [ ] **Step 1: Update src/db/models.py for MySQL compatibility**

```python
"""SQLAlchemy 模型定义 — MySQL 适配"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class CalculationHistory(Base):
    """测算历史记录"""
    __tablename__ = "calculation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    calc_id = Column(String(64), unique=True, nullable=False, comment="测算ID")
    calc_type = Column(String(32), nullable=False, comment="测算类型: full|quick|profit|risk")
    scope = Column(Text, comment="测算范围 JSON")
    date_range_start = Column(String(10), comment="开始日期")
    date_range_end = Column(String(10), comment="结束日期")
    result_summary = Column(Text, comment="结果摘要 JSON")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_calc_type", "calc_type"),
        Index("idx_created_at", "created_at"),
    )


class ForecastResult(Base):
    """预测结果存储"""
    __tablename__ = "forecast_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    forecast_id = Column(String(64), unique=True, nullable=False)
    entity_type = Column(String(32), nullable=False, comment="store|brand|region")
    entity_id = Column(String(64), nullable=False)
    forecast_date = Column(String(10), nullable=False)
    predicted_value = Column(Float, comment="预测值")
    lower_bound = Column(Float, comment="下界")
    upper_bound = Column(Float, comment="上界")
    model_used = Column(String(32), comment="使用的模型")
    mape = Column(Float, comment="预测精度")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_entity", "entity_type", "entity_id"),
        Index("idx_forecast_date", "forecast_date"),
    )


class RiskAssessment(Base):
    """风险评估结果"""
    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(String(64), unique=True, nullable=False)
    entity_type = Column(String(32), nullable=False)
    entity_id = Column(String(64), nullable=False)
    target_value = Column(Float, comment="目标值")
    baseline_value = Column(Float, comment="基线值")
    reachability_prob = Column(Float, comment="达标概率")
    risk_level = Column(String(16), comment="low|medium|high|critical")
    scenario_optimistic = Column(Float, comment="乐观场景利润")
    scenario_base = Column(Float, comment="基准场景利润")
    scenario_pessimistic = Column(Float, comment="悲观场景利润")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_risk_entity", "entity_type", "entity_id"),
    )


class AllocationPlan(Base):
    """目标分配方案"""
    __tablename__ = "allocation_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), unique=True, nullable=False)
    total_target = Column(Float, comment="总目标")
    store_count = Column(Integer, comment="门店数")
    plan_detail = Column(Text, comment="分配明细 JSON")
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemConfig(Base):
    """系统配置"""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(128), unique=True, nullable=False)
    config_value = Column(Text, comment="配置值")
    description = Column(String(256), comment="配置说明")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Step 2: Update docker/init.sql for MySQL**

```sql
-- profit-forecast v0.1 MySQL 初始化脚本

CREATE DATABASE IF NOT EXISTS profit_forecast
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE profit_forecast;

-- 测算历史
CREATE TABLE IF NOT EXISTS calculation_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    calc_id VARCHAR(64) NOT NULL UNIQUE,
    calc_type VARCHAR(32) NOT NULL,
    scope TEXT,
    date_range_start VARCHAR(10),
    date_range_end VARCHAR(10),
    result_summary TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_calc_type (calc_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 预测结果
CREATE TABLE IF NOT EXISTS forecast_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    forecast_id VARCHAR(64) NOT NULL UNIQUE,
    entity_type VARCHAR(32) NOT NULL,
    entity_id VARCHAR(64) NOT NULL,
    forecast_date VARCHAR(10) NOT NULL,
    predicted_value DOUBLE,
    lower_bound DOUBLE,
    upper_bound DOUBLE,
    model_used VARCHAR(32),
    mape DOUBLE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_entity (entity_type, entity_id),
    INDEX idx_forecast_date (forecast_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 风险评估
CREATE TABLE IF NOT EXISTS risk_assessments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assessment_id VARCHAR(64) NOT NULL UNIQUE,
    entity_type VARCHAR(32) NOT NULL,
    entity_id VARCHAR(64) NOT NULL,
    target_value DOUBLE,
    baseline_value DOUBLE,
    reachability_prob DOUBLE,
    risk_level VARCHAR(16),
    scenario_optimistic DOUBLE,
    scenario_base DOUBLE,
    scenario_pessimistic DOUBLE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_risk_entity (entity_type, entity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 分配方案
CREATE TABLE IF NOT EXISTS allocation_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plan_id VARCHAR(64) NOT NULL UNIQUE,
    total_target DOUBLE,
    store_count INT,
    plan_detail TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 系统配置
CREATE TABLE IF NOT EXISTS system_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(128) NOT NULL UNIQUE,
    config_value TEXT,
    description VARCHAR(256),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 默认配置
INSERT INTO system_config (config_key, config_value, description) VALUES
('default_tax_rate', '0.25', '默认所得税率'),
('default_cogs_ratio', '0.45', '默认采购成本率'),
('monte_carlo_iterations', '1000', '蒙特卡洛模拟次数'),
('default_perspective', 'actual', '默认口径: actual|rebate')
ON DUPLICATE KEY UPDATE config_value=VALUES(config_value);
```

- [ ] **Step 3: Run test**

```bash
pytest tests/unit/test_db_session.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/db/models.py docker/init.sql
git commit -m "feat(db): update models and init SQL for MySQL"
```

### Task 1.3: Update .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Update .env.example**

```bash
# MySQL 元数据库
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=ycf0312!
MYSQL_DATABASE=profit_forecast

# StarRocks 数据源
STARROCKS_HOST=your-starrocks-host
STARROCKS_PORT=9030
STARROCKS_USER=your-user
STARROCKS_PASSWORD=your-password
STARROCKS_DATABASE=spark_catalog

# 表名配置
TABLE_POS_ORD=ads_pub.ads_fact_pos_ord_analysis
TABLE_STORE_LOSS=proj_facana.ads_fin_fact_day_storeloss_pp
TABLE_STORE_LOSS_GJ=proj_facana.ads_fin_fact_day_storeloss_pp_gj

# 口径选择
DEFAULT_PERSPECTIVE=actual

# 数据适配器
DATAWORKS_ADAPTER=mock

# API 配置
API_HOST=0.0.0.0
API_PORT=8000
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: update .env.example with v0.1 configs"
```

---

## Phase 2: Data Layer

### Task 2.1: Create SalesDataCollector

**Files:**
- Create: `src/data/collectors/sales_collector.py`
- Test: `tests/unit/test_sales_collector.py`

- [ ] **Step 1: Write tests for SalesDataCollector**

```python
# tests/unit/test_sales_collector.py
import pytest
import pandas as pd
from unittest.mock import Mock, patch
from src.data.collectors.sales_collector import SalesDataCollector


@pytest.fixture
def mock_store_loss_df():
    """模拟 storeloss 数据"""
    return pd.DataFrame({
        "store_no": ["S001", "S001", "S002"],
        "base_date": ["20260101", "20260102", "20260101"],
        "brand_detail_abbreviation": ["NK", "NK", "AD"],
        "region_top": ["华东", "华东", "华南"],
        "province": ["上海", "上海", "广东"],
        "managing_city": ["上海", "上海", "深圳"],
        "business_city": ["上海", "上海", "深圳"],
        "shop_category": ["正价店", "正价店", "奥莱"],
        "business_attribute": ["自营", "自营", "加盟"],
        "d1_pf_total_sal_amt_pp": [50000.0, 55000.0, 30000.0],
        "d1_pf_total_sal_amt": [48000.0, 52000.0, 28000.0],
        "d1_pf_settlement_amt": [45000.0, 49000.0, 26000.0],
        "d1_pf_hq_notax_gross_profit": [25000.0, 28000.0, 15000.0],
        "d1_pf_hq_notax_gross_net_profit": [24000.0, 27000.0, 14500.0],
        "d1_pf_operating_exp": [15000.0, 16000.0, 10000.0],
        "d1_pf_bmanaging_exp": [3000.0, 3200.0, 2000.0],
        "d1_pf_hq_notax_operating_profit": [6000.0, 7800.0, 2500.0],
        "d1_pf_store_contribution1": [5500.0, 7200.0, 2200.0],
        "d1_pf_salary_fee": [8000.0, 8500.0, 5000.0],
        "d1_pf_social_fee": [2000.0, 2100.0, 1200.0],
        "d1_pf_comprehensive_mall_fee": [2000.0, 2200.0, 1500.0],
        "d1_pf_decorate_fee": [1000.0, 1000.0, 800.0],
        "d1_pf_express": [500.0, 550.0, 400.0],
        "d1_pf_all_other_fee": [1500.0, 1650.0, 1100.0],
        "d1_pf_hq_taxcost": [23000.0, 24000.0, 13000.0],
        "d1_pf_additional_taxes": [500.0, 550.0, 300.0],
        "d1_pf_server_fee": [100.0, 120.0, 80.0],
        "d1_pf_nonoperating_in_out": [200.0, 250.0, 150.0],
        "d1_pf_total_prm_amt": [80000.0, 85000.0, 50000.0],
    })


@pytest.fixture
def mock_pos_df():
    """模拟 POS 订单数据"""
    return pd.DataFrame({
        "org_lno": ["S001", "S001", "S002"],
        "period_sdate": ["20260101", "20260101", "20260101"],
        "order_no": ["O001", "O002", "O003"],
        "sal_amt": [1000.0, 1500.0, 800.0],
        "sal_qty": [2, 3, 1],
        "discount_rate": [0.85, 0.90, 0.75],
        "brd_dtl_no": ["NK01", "NK01", "AD01"],
    })


def test_collect_store_loss_returns_dataframe(mock_store_loss_df):
    """测试采集 storeloss 数据返回 DataFrame"""
    collector = SalesDataCollector(adapter="mock")
    collector._mock_store_loss_df = mock_store_loss_df

    df = collector.collect_store_loss(store_no="S001", date_range=("20260101", "20260102"))

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "d1_pf_total_sal_amt_pp" in df.columns


def test_collect_pos_orders_returns_dataframe(mock_pos_df):
    """测试采集 POS 订单数据返回 DataFrame"""
    collector = SalesDataCollector(adapter="mock")
    collector._mock_pos_df = mock_pos_df

    df = collector.collect_pos_orders(store_no="S001", date_range=("20260101", "20260101"))

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2


def test_collect_unified_sales_merges_data(mock_store_loss_df, mock_pos_df):
    """测试统一宽表正确合并数据"""
    collector = SalesDataCollector(adapter="mock")
    collector._mock_store_loss_df = mock_store_loss_df
    collector._mock_pos_df = mock_pos_df

    df = collector.collect_unified_sales(store_no="S001", date_range=("20260101", "20260102"))

    assert isinstance(df, pd.DataFrame)
    assert "sales_amount" in df.columns
    assert "order_count" in df.columns
    assert "avg_discount" in df.columns
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_sales_collector.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.data.collectors.sales_collector'"

- [ ] **Step 3: Implement SalesDataCollector**

```python
# src/data/collectors/sales_collector.py
"""统一销售数据采集器

从 3 张销售相关表采集数据，生成统一宽表供下游模块使用。
"""

import os
from typing import Optional

import pandas as pd
from loguru import logger

from src.data.collectors.base import BaseCollector


class SalesDataCollector(BaseCollector):
    """统一销售数据采集器

    使用方式：
        collector = SalesDataCollector(adapter="starrocks")
        df = collector.collect_unified_sales(store_no="S001", date_range=("20260101", "20260131"))
    """

    TABLE_POS_ORD = os.getenv("TABLE_POS_ORD", "ads_pub.ads_fact_pos_ord_analysis")
    TABLE_STORE_LOSS = os.getenv("TABLE_STORE_LOSS", "proj_facana.ads_fin_fact_day_storeloss_pp")
    TABLE_STORE_LOSS_GJ = os.getenv("TABLE_STORE_LOSS_GJ", "proj_facana.ads_fin_fact_day_storeloss_pp_gj")

    def __init__(self, adapter: str = "mock"):
        super().__init__(adapter=adapter)
        self._mock_store_loss_df = None
        self._mock_pos_df = None

    def collect_store_loss(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
        perspective: str = "actual",
    ) -> pd.DataFrame:
        """采集门店损益数据

        Args:
            store_no: 门店编码，None 表示全部
            date_range: (start_date, end_date)，格式 YYYYMMDD
            perspective: "actual" 业绩口径 | "rebate" 返利口径

        Returns:
            DataFrame with store loss data
        """
        if self._adapter == "mock":
            return self._mock_collect_store_loss(store_no, date_range)

        prefix = "d1_pf" if perspective == "actual" else "d2"

        where_clauses = []
        if store_no:
            where_clauses.append(f"store_no = '{store_no}'")
        if date_range:
            where_clauses.append(f"base_date >= '{date_range[0]}' AND base_date <= '{date_range[1]}'")
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT
            store_no, base_date, brand_detail_abbreviation, region_top,
            province, managing_city, business_city, shop_category, business_attribute,
            {prefix}_total_sal_amt_pp AS d1_pf_total_sal_amt_pp,
            {prefix}_total_sal_amt AS d1_pf_total_sal_amt,
            {prefix}_settlement_amt AS d1_pf_settlement_amt,
            {prefix}_hq_notax_gross_profit AS d1_pf_hq_notax_gross_profit,
            {prefix}_hq_notax_gross_net_profit AS d1_pf_hq_notax_gross_net_profit,
            {prefix}_operating_exp AS d1_pf_operating_exp,
            {prefix}_bmanaging_exp AS d1_pf_bmanaging_exp,
            {prefix}_hq_notax_operating_profit AS d1_pf_hq_notax_operating_profit,
            {prefix}_store_contribution1 AS d1_pf_store_contribution1,
            {prefix}_salary_fee AS d1_pf_salary_fee,
            {prefix}_social_fee AS d1_pf_social_fee,
            {prefix}_comprehensive_mall_fee AS d1_pf_comprehensive_mall_fee,
            {prefix}_decorate_fee AS d1_pf_decorate_fee,
            {prefix}_express AS d1_pf_express,
            {prefix}_all_other_fee AS d1_pf_all_other_fee,
            {prefix}_hq_taxcost AS d1_pf_hq_taxcost,
            {prefix}_additional_taxes AS d1_pf_additional_taxes,
            {prefix}_server_fee AS d1_pf_server_fee,
            {prefix}_nonoperating_in_out AS d1_pf_nonoperating_in_out,
            {prefix}_total_prm_amt AS d1_pf_total_prm_amt
        FROM {self.TABLE_STORE_LOSS}
        WHERE {where_sql}
        """

        df = self._execute_query(sql)
        logger.info(f"采集 storeloss 数据: {len(df)} 行, perspective={perspective}")
        return df

    def collect_store_loss_gj(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
    ) -> pd.DataFrame:
        """采集门店损益数据（管理口径）"""
        if self._adapter == "mock":
            return self._mock_collect_store_loss(store_no, date_range)

        where_clauses = []
        if store_no:
            where_clauses.append(f"store_no = '{store_no}'")
        if date_range:
            where_clauses.append(f"base_date >= '{date_range[0]}' AND base_date <= '{date_range[1]}'")
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT
            store_no, base_date, brand_detail_abbreviation, region_top,
            d2_total_sal_amt, d2_settlement_amt, d2_hq_taxcost,
            d2_hq_notax_gross_profit, d2_operating_exp, d2_bmanaging_exp,
            d2_hq_notax_operating_profit, d2_store_contribution1
        FROM {self.TABLE_STORE_LOSS_GJ}
        WHERE {where_sql}
        """

        df = self._execute_query(sql)
        logger.info(f"采集 storeloss_gj 数据: {len(df)} 行")
        return df

    def collect_pos_orders(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
    ) -> pd.DataFrame:
        """采集 POS 订单数据"""
        if self._adapter == "mock":
            return self._mock_collect_pos_orders(store_no, date_range)

        where_clauses = []
        if store_no:
            where_clauses.append(f"org_lno = '{store_no}'")
        if date_range:
            where_clauses.append(f"period_sdate >= '{date_range[0]}' AND period_sdate <= '{date_range[1]}'")
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT
            org_lno AS store_no, period_sdate AS base_date,
            order_no, sal_amt, sal_qty, discount_rate, brd_dtl_no,
            sal_amt_sy, sal_qty_sy, is_new_name,
            brd_season_type_name, lsg_mon_qty
        FROM {self.TABLE_POS_ORD}
        WHERE {where_sql}
        """

        df = self._execute_query(sql)
        logger.info(f"采集 POS 订单数据: {len(df)} 行")
        return df

    def collect_unified_sales(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
        perspective: str = "actual",
    ) -> pd.DataFrame:
        """生成统一销售宽表

        合并 storeloss 损益数据 + POS 订单聚合数据
        """
        # 1. 采集 storeloss 数据
        loss_df = self.collect_store_loss(store_no, date_range, perspective)
        if loss_df.empty:
            logger.warning("storeloss 数据为空")
            return pd.DataFrame()

        # 2. 采集 POS 数据并聚合
        pos_df = self.collect_pos_orders(store_no, date_range)

        if not pos_df.empty:
            pos_agg = pos_df.groupby(["store_no", "base_date"]).agg(
                order_count=("order_no", "nunique"),
                qty_sold=("sal_qty", "sum"),
                avg_discount=("discount_rate", "mean"),
            ).reset_index()
        else:
            pos_agg = pd.DataFrame(columns=["store_no", "base_date", "order_count", "qty_sold", "avg_discount"])

        # 3. 合并
        unified = loss_df.merge(pos_agg, on=["store_no", "base_date"], how="left")

        # 4. 重命名字段
        unified = unified.rename(columns={
            "d1_pf_total_sal_amt_pp": "sales_amount",
            "d1_pf_total_sal_amt": "revenue",
            "d1_pf_settlement_amt": "settlement_amt",
            "d1_pf_hq_notax_gross_profit": "gross_profit",
            "d1_pf_hq_notax_gross_net_profit": "gross_net_profit",
            "d1_pf_operating_exp": "operating_expense",
            "d1_pf_bmanaging_exp": "bmanaging_exp",
            "d1_pf_hq_notax_operating_profit": "operating_profit",
            "d1_pf_store_contribution1": "store_contribution",
            "d1_pf_salary_fee": "salary_fee",
            "d1_pf_social_fee": "social_fee",
            "d1_pf_comprehensive_mall_fee": "comprehensive_mall_fee",
            "d1_pf_decorate_fee": "decorate_fee",
            "d1_pf_express": "express",
            "d1_pf_all_other_fee": "all_other_fee",
            "d1_pf_hq_taxcost": "hq_taxcost",
            "d1_pf_additional_taxes": "additional_taxes",
            "d1_pf_server_fee": "server_fee",
            "d1_pf_nonoperating_in_out": "nonoperating_in_out",
            "d1_pf_total_prm_amt": "prm_amt",
            "brand_detail_abbreviation": "brand",
        })

        # 5. 填充 POS 聚合的空值
        unified["order_count"] = unified["order_count"].fillna(0).astype(int)
        unified["qty_sold"] = unified["qty_sold"].fillna(0).astype(int)
        unified["avg_discount"] = unified["avg_discount"].fillna(1.0)

        # 6. 添加口径标识
        unified["perspective"] = perspective

        logger.info(f"统一销售宽表生成: {len(unified)} 行, {unified['store_no'].nunique()} 家门店")
        return unified

    def _mock_collect_store_loss(self, store_no, date_range):
        """Mock 模式采集 storeloss"""
        df = self._mock_store_loss_df.copy()
        if store_no:
            df = df[df["store_no"] == store_no]
        if date_range:
            df = df[(df["base_date"] >= date_range[0]) & (df["base_date"] <= date_range[1])]
        return df

    def _mock_collect_pos_orders(self, store_no, date_range):
        """Mock 模式采集 POS"""
        df = self._mock_pos_df.copy()
        if store_no:
            df = df[df["org_lno"] == store_no]
        if date_range:
            df = df[(df["period_sdate"] >= date_range[0]) & (df["period_sdate"] <= date_range[1])]
        return df
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_sales_collector.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/data/collectors/sales_collector.py tests/unit/test_sales_collector.py
git commit -m "feat(data): add SalesDataCollector for unified sales data"
```

### Task 2.2: Update StarRocksCollector for 3 tables

**Files:**
- Modify: `src/data/collectors/starrocks_collector.py`

- [ ] **Step 1: Add table query methods to StarRocksCollector**

Read the existing file first, then add the following methods:

```python
# Add to StarRocksCollector class

TABLE_POS_ORD = os.getenv("TABLE_POS_ORD", "ads_pub.ads_fact_pos_ord_analysis")
TABLE_STORE_LOSS = os.getenv("TABLE_STORE_LOSS", "proj_facana.ads_fin_fact_day_storeloss_pp")
TABLE_STORE_LOSS_GJ = os.getenv("TABLE_STORE_LOSS_GJ", "proj_facana.ads_fin_fact_day_storeloss_pp_gj")

def query_store_loss(self, store_no=None, date_range=None, perspective="actual"):
    """查询门店损益数据"""
    prefix = "d1_pf" if perspective == "actual" else "d2"
    where = self._build_where(store_no, date_range, date_col="base_date")
    sql = f"SELECT * FROM {self.TABLE_STORE_LOSS} WHERE {where}"
    return self.execute(sql)

def query_pos_orders(self, store_no=None, date_range=None):
    """查询 POS 订单数据"""
    where = self._build_where(store_no, date_range, date_col="period_sdate")
    sql = f"SELECT * FROM {self.TABLE_POS_ORD} WHERE {where}"
    return self.execute(sql)

def _build_where(self, store_no, date_range, date_col="base_date"):
    """构建 WHERE 条件"""
    clauses = []
    store_col = "store_no" if date_col == "base_date" else "org_lno"
    if store_no:
        clauses.append(f"{store_col} = '{store_no}'")
    if date_range:
        clauses.append(f"{date_col} >= '{date_range[0]}' AND {date_col} <= '{date_range[1]}'")
    return " AND ".join(clauses) if clauses else "1=1"
```

- [ ] **Step 2: Commit**

```bash
git add src/data/collectors/starrocks_collector.py
git commit -m "feat(data): add 3-table query methods to StarRocksCollector"
```

### Task 2.3: Create ETL SQL scripts

**Files:**
- Create: `scripts/etl_sql/09_unified_sales.sql`
- Create: `scripts/etl_sql/10_discount_matrix.sql`

- [ ] **Step 1: Create unified sales SQL**

```sql
-- scripts/etl_sql/09_unified_sales.sql
-- 统一销售宽表：从 storeloss + POS 聚合

-- 门店损益基础数据（业绩口径）
CREATE TABLE IF NOT EXISTS unified_sales_daily AS
SELECT
    store_no,
    base_date,
    brand_detail_abbreviation AS brand,
    region_top AS region,
    province,
    managing_city,
    business_city,
    shop_category,
    business_attribute,
    -- 业绩额
    d1_pf_total_sal_amt_pp AS sales_amount,
    -- 损益收入
    d1_pf_total_sal_amt AS revenue,
    -- 结款额
    d1_pf_settlement_amt AS settlement_amt,
    -- 牌价收入
    d1_pf_total_prm_amt AS prm_amt,
    -- 总部含税成本
    d1_pf_hq_taxcost AS hq_taxcost,
    -- 总部无税毛利
    d1_pf_hq_notax_gross_profit AS gross_profit,
    -- 总部无税毛利净额
    d1_pf_hq_notax_gross_net_profit AS gross_net_profit,
    -- 附加税金
    d1_pf_additional_taxes AS additional_taxes,
    -- 经营费用
    d1_pf_operating_exp AS operating_expense,
    -- B管理费用
    d1_pf_bmanaging_exp AS bmanaging_exp,
    -- 服务收支
    d1_pf_server_fee AS server_fee,
    -- 营业外收支
    d1_pf_nonoperating_in_out AS nonoperating_in_out,
    -- 总部无税营业利润
    d1_pf_hq_notax_operating_profit AS operating_profit,
    -- 店铺贡献
    d1_pf_store_contribution1 AS store_contribution,
    -- 工资
    d1_pf_salary_fee AS salary_fee,
    -- 社保公积金
    d1_pf_social_fee AS social_fee,
    -- 商场综合收费
    d1_pf_comprehensive_mall_fee AS comprehensive_mall_fee,
    -- 装修费
    d1_pf_decorate_fee AS decorate_fee,
    -- 快递费
    d1_pf_express AS express,
    -- 其他费用
    d1_pf_all_other_fee AS all_other_fee
FROM proj_facana.ads_fin_fact_day_storeloss_pp;
```

- [ ] **Step 2: Create discount matrix SQL**

```sql
-- scripts/etl_sql/10_discount_matrix.sql
-- 品牌季节折扣矩阵

-- 按品牌、品牌季节、上市月数聚合平均折扣率
CREATE TABLE IF NOT EXISTS brand_season_discount_matrix AS
SELECT
    brd_dtl_no AS brand_code,
    brd_dtl_abbr AS brand_name,
    brd_season_type_name AS season_type,
    lsg_mon_qty AS months_since_launch,
    COUNT(DISTINCT order_no) AS order_count,
    SUM(sal_amt) AS total_sales,
    SUM(sal_qty) AS total_qty,
    AVG(discount_rate) AS avg_discount_rate,
    STDDEV(discount_rate) AS discount_stddev
FROM ads_pub.ads_fact_pos_ord_analysis
WHERE discount_rate > 0 AND discount_rate <= 1
GROUP BY brd_dtl_no, brd_dtl_abbr, brd_season_type_name, lsg_mon_qty;

-- 按品牌、月份聚合同比折扣趋势
CREATE TABLE IF NOT EXISTS brand_monthly_discount_trend AS
SELECT
    brd_dtl_no AS brand_code,
    brd_dtl_abbr AS brand_name,
    SUBSTR(period_sdate, 1, 6) AS year_month,
    AVG(discount_rate) AS avg_discount_rate,
    COUNT(DISTINCT order_no) AS order_count
FROM ads_pub.ads_fact_pos_ord_analysis
WHERE discount_rate > 0 AND discount_rate <= 1
GROUP BY brd_dtl_no, brd_dtl_abbr, SUBSTR(period_sdate, 1, 6);
```

- [ ] **Step 3: Commit**

```bash
git add scripts/etl_sql/09_unified_sales.sql scripts/etl_sql/10_discount_matrix.sql
git commit -m "feat(etl): add unified sales and discount matrix SQL"
```

---

## Phase 3: Discount Prediction Module

### Task 3.1: Create discount predictor

**Files:**
- Create: `src/forecasting/discount/__init__.py`
- Create: `src/forecasting/discount/brand_season_matrix.py`
- Create: `src/forecasting/discount/predictor.py`
- Test: `tests/unit/test_discount_predictor.py`

- [ ] **Step 1: Write tests**

```python
# tests/unit/test_discount_predictor.py
import pytest
import pandas as pd
from src.forecasting.discount.brand_season_matrix import BrandSeasonMatrix
from src.forecasting.discount.predictor import DiscountPredictor


@pytest.fixture
def sample_pos_data():
    """模拟 POS 数据"""
    records = []
    for month in range(1, 13):
        for brand in ["NK", "AD"]:
            for season in ["当季", "上季", "旧款"]:
                for i in range(10):
                    discount = {"当季": 0.95, "上季": 0.75, "旧款": 0.50}[season]
                    records.append({
                        "brand_code": brand,
                        "brand_name": brand,
                        "season_type": season,
                        "months_since_launch": month,
                        "year_month": f"2025{month:02d}",
                        "discount_rate": discount + (i - 5) * 0.01,
                    })
    return pd.DataFrame(records)


def test_brand_season_matrix_builds_correctly(sample_pos_data):
    """测试品牌季节折扣矩阵构建"""
    matrix = BrandSeasonMatrix(sample_pos_data)
    result = matrix.get_matrix()

    assert not result.empty
    assert "avg_discount_rate" in result.columns
    # 当季折扣应高于旧款
    current_season = result[result["season_type"] == "当季"]["avg_discount_rate"].mean()
    old_season = result[result["season_type"] == "旧款"]["avg_discount_rate"].mean()
    assert current_season > old_season


def test_predictor_returns_forecast(sample_pos_data):
    """测试折扣预测器返回预测结果"""
    predictor = DiscountPredictor(sample_pos_data)
    forecast = predictor.predict(brand_code="NK", months_ahead=3)

    assert len(forecast) == 3
    assert "month" in forecast.columns
    assert "forecast_discount_rate" in forecast.columns
    assert all(0 < r <= 1 for r in forecast["forecast_discount_rate"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_discount_predictor.py -v
```

- [ ] **Step 3: Implement BrandSeasonMatrix**

```python
# src/forecasting/discount/brand_season_matrix.py
"""品牌季节折扣矩阵

从 POS 数据构建按品牌、品牌季节、上市月数的折扣衰减曲线。
"""

import pandas as pd
from loguru import logger


class BrandSeasonMatrix:
    """品牌季节折扣矩阵

    使用方式：
        matrix = BrandSeasonMatrix(pos_df)
        result = matrix.get_matrix()
        decay_curve = matrix.get_decay_curve(brand_code="NK", season_type="当季")
    """

    def __init__(self, pos_df: pd.DataFrame):
        """初始化

        Args:
            pos_df: POS 数据，需包含 brand_code, season_type, months_since_launch, discount_rate
        """
        self.pos_df = pos_df
        self._matrix = None

    def get_matrix(self) -> pd.DataFrame:
        """获取完整矩阵"""
        if self._matrix is None:
            self._build_matrix()
        return self._matrix

    def get_decay_curve(self, brand_code: str, season_type: str) -> pd.DataFrame:
        """获取某品牌某季节的折扣衰减曲线

        Returns:
            DataFrame with columns: months_since_launch, avg_discount_rate
        """
        matrix = self.get_matrix()
        curve = matrix[
            (matrix["brand_code"] == brand_code) &
            (matrix["season_type"] == season_type)
        ][["months_since_launch", "avg_discount_rate"]].sort_values("months_since_launch")
        return curve

    def get_season_correction(self, brand_code: str, season_type: str,
                               current_month: int, last_year_month: int) -> float:
        """计算品牌季节修正系数

        Args:
            brand_code: 品牌编码
            season_type: 品牌季节类型
            current_month: 当前上市月数
            last_year_month: 去年同月上市月数

        Returns:
            修正系数 (current / last_year)
        """
        curve = self.get_decay_curve(brand_code, season_type)
        if curve.empty:
            return 1.0

        current_rate = curve[curve["months_since_launch"] == current_month]["avg_discount_rate"]
        last_year_rate = curve[curve["months_since_launch"] == last_year_month]["avg_discount_rate"]

        if current_rate.empty or last_year_rate.empty:
            return 1.0

        return float(current_rate.iloc[0] / last_year_rate.iloc[0])

    def _build_matrix(self):
        """构建矩阵"""
        df = self.pos_df.copy()

        # 确保 discount_rate 在合理范围
        df = df[(df["discount_rate"] > 0) & (df["discount_rate"] <= 1)]

        self._matrix = df.groupby(
            ["brand_code", "brand_name", "season_type", "months_since_launch"]
        ).agg(
            avg_discount_rate=("discount_rate", "mean"),
            discount_std=("discount_rate", "std"),
            sample_count=("discount_rate", "count"),
        ).reset_index()

        self._matrix["discount_std"] = self._matrix["discount_std"].fillna(0)

        logger.info(f"品牌季节折扣矩阵构建完成: {len(self._matrix)} 条记录")
```

- [ ] **Step 4: Implement DiscountPredictor**

```python
# src/forecasting/discount/predictor.py
"""折扣率预测器

结合同比折扣趋势 + 品牌季节修正系数，预测未来月度折扣率。
"""

import pandas as pd
from loguru import logger

from src.forecasting.discount.brand_season_matrix import BrandSeasonMatrix


class DiscountPredictor:
    """折扣率预测器

    使用方式：
        predictor = DiscountPredictor(pos_df)
        forecast = predictor.predict(brand_code="NK", months_ahead=3)
    """

    def __init__(self, pos_df: pd.DataFrame):
        """初始化

        Args:
            pos_df: POS 数据，需包含 brand_code, year_month, discount_rate,
                     season_type, months_since_launch
        """
        self.pos_df = pos_df
        self.matrix = BrandSeasonMatrix(pos_df)
        self._monthly_trend = None

    def predict(self, brand_code: str, months_ahead: int = 3) -> pd.DataFrame:
        """预测未来月度折扣率

        Args:
            brand_code: 品牌编码
            months_ahead: 预测月数

        Returns:
            DataFrame with columns: month, forecast_discount_rate, method, confidence
        """
        # 1. 获取同比折扣趋势
        yoy_trend = self._get_yoy_trend(brand_code)

        # 2. 获取品牌季节修正系数
        season_correction = self._get_season_correction(brand_code)

        # 3. 合并预测
        forecasts = []
        for i in range(1, months_ahead + 1):
            # 同比基线
            yoy_base = yoy_trend.get(i, 0.80)

            # 品牌季节修正
            correction = season_correction.get(i, 1.0)

            # 最终预测
            forecast_rate = yoy_base * correction
            forecast_rate = max(0.10, min(1.0, forecast_rate))  # 限制在合理范围

            forecasts.append({
                "month_offset": i,
                "forecast_discount_rate": round(forecast_rate, 4),
                "yoy_base": round(yoy_base, 4),
                "season_correction": round(correction, 4),
                "method": "yoy_season_blend",
                "confidence": round(0.8 - i * 0.05, 2),  # 越远越不确定
            })

        result = pd.DataFrame(forecasts)
        logger.info(f"折扣预测完成: brand={brand_code}, {months_ahead} 个月")
        return result

    def _get_yoy_trend(self, brand_code: str) -> dict:
        """获取同比折扣趋势

        Returns:
            {month_offset: discount_rate}
        """
        df = self.pos_df[self.pos_df["brand_code"] == brand_code]
        if df.empty:
            return {}

        monthly = df.groupby("year_month")["discount_rate"].mean()

        # 简单取最近 12 个月的平均值作为趋势
        trend = {}
        for i, rate in enumerate(monthly.tail(12).values, 1):
            trend[i] = rate

        return trend

    def _get_season_correction(self, brand_code: str) -> dict:
        """获取品牌季节修正系数

        Returns:
            {month_offset: correction_factor}
        """
        matrix_df = self.matrix.get_matrix()
        brand_matrix = matrix_df[matrix_df["brand_code"] == brand_code]

        if brand_matrix.empty:
            return {}

        # 按上市月数的平均折扣率变化作为修正
        correction = {}
        rates = brand_matrix.groupby("months_since_launch")["avg_discount_rate"].mean()

        if len(rates) >= 2:
            first_rate = rates.iloc[0]
            for month_offset, rate in rates.items():
                correction[month_offset] = rate / first_rate if first_rate > 0 else 1.0

        return correction
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_discount_predictor.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/forecasting/discount/ tests/unit/test_discount_predictor.py
git commit -m "feat(forecast): add discount prediction module"
```

---

## Phase 4: Profit Calculator Update

### Task 4.1: Update ProfitCalculator to use storeloss data

**Files:**
- Modify: `src/profit/profit_calculator.py`
- Modify: `src/profit/cost_estimator.py`
- Test: `tests/unit/test_profit_v01.py`

- [ ] **Step 1: Write tests for updated profit calculator**

```python
# tests/unit/test_profit_v01.py
import pytest
import pandas as pd
from src.profit.profit_calculator import ProfitCalculator, StoreProfit, ProfitSummary


@pytest.fixture
def unified_sales_df():
    """模拟统一销售宽表数据"""
    return pd.DataFrame({
        "store_no": ["S001", "S002"],
        "base_date": ["20260101", "20260101"],
        "brand": ["NK", "AD"],
        "region": ["华东", "华南"],
        "sales_amount": [50000.0, 30000.0],
        "revenue": [48000.0, 28000.0],
        "settlement_amt": [45000.0, 26000.0],
        "prm_amt": [80000.0, 50000.0],
        "gross_profit": [25000.0, 15000.0],
        "gross_net_profit": [24000.0, 14500.0],
        "operating_expense": [15000.0, 10000.0],
        "bmanaging_exp": [3000.0, 2000.0],
        "operating_profit": [6000.0, 2500.0],
        "store_contribution": [5500.0, 2200.0],
        "salary_fee": [8000.0, 5000.0],
        "social_fee": [2000.0, 1200.0],
        "comprehensive_mall_fee": [2000.0, 1500.0],
        "decorate_fee": [1000.0, 800.0],
        "express": [500.0, 400.0],
        "all_other_fee": [1500.0, 1100.0],
        "hq_taxcost": [23000.0, 13000.0],
        "additional_taxes": [500.0, 300.0],
        "server_fee": [100.0, 80.0],
        "nonoperating_in_out": [200.0, 150.0],
        "order_count": [50, 30],
        "qty_sold": [120, 60],
        "avg_discount": [0.85, 0.75],
        "perspective": ["actual", "actual"],
    })


def test_calculate_from_unified_sales(unified_sales_df):
    """测试从统一宽表计算利润"""
    calc = ProfitCalculator()
    summary = calc.calculate_from_sales(unified_sales_df)

    assert isinstance(summary, ProfitSummary)
    assert summary.store_count == 2
    assert summary.total_revenue == 76000.0
    assert summary.total_cogs == 36000.0
    assert summary.total_gross_profit == 40000.0


def test_store_profit_has_all_layers(unified_sales_df):
    """测试单店利润包含四层"""
    calc = ProfitCalculator()
    summary = calc.calculate_from_sales(unified_sales_df)

    store = summary.store_profits["S001"]
    assert store.gross_profit == 25000.0
    assert store.operating_profit == 6000.0
    assert store.store_contribution == 5500.0


def test_dual_perspective(unified_sales_df):
    """测试双口径对比"""
    calc = ProfitCalculator()

    # 业绩口径
    summary_actual = calc.calculate_from_sales(unified_sales_df)

    # 修改为返利口径数据
    rebate_df = unified_sales_df.copy()
    rebate_df["perspective"] = "rebate"
    rebate_df["revenue"] = rebate_df["revenue"] * 0.95  # 返利口径通常略低

    summary_rebate = calc.calculate_from_sales(rebate_df)

    assert summary_actual.total_revenue > summary_rebate.total_revenue
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_profit_v01.py -v
```

- [ ] **Step 3: Update ProfitCalculator**

Read the existing `src/profit/profit_calculator.py` first, then add the new method:

```python
# Add to ProfitCalculator class

def calculate_from_sales(self, sales_df: pd.DataFrame) -> ProfitSummary:
    """从统一销售宽表计算利润

    Args:
        sales_df: SalesDataCollector.collect_unified_sales() 返回的 DataFrame

    Returns:
        ProfitSummary
    """
    store_profits = {}

    for _, row in sales_df.iterrows():
        store_code = row["store_no"]
        revenue = row.get("revenue", 0)

        # 从宽表直接取值
        cogs = row.get("hq_taxcost", revenue * self.avg_cogs_ratio)
        gross_profit = row.get("gross_profit", revenue - cogs)
        gross_margin = gross_profit / revenue if revenue > 0 else 0

        gross_net_profit = row.get("gross_net_profit", gross_profit)

        # 经营费用明细
        salary = row.get("salary_fee", 0)
        social_fee = row.get("social_fee", 0)
        comprehensive_mall_fee = row.get("comprehensive_mall_fee", 0)
        decorate_fee = row.get("decorate_fee", 0)
        express_fee = row.get("express", 0)
        all_other_fee = row.get("all_other_fee", 0)
        operating_expense = row.get("operating_expense", 0)
        bmanaging_exp = row.get("bmanaging_exp", 0)

        operating_profit = row.get("operating_profit", gross_net_profit - operating_expense - bmanaging_exp)
        operating_margin = operating_profit / revenue if revenue > 0 else 0

        store_contribution = row.get("store_contribution", operating_profit)

        # v0.1: 税费置零
        tax = 0.0
        net_profit = store_contribution
        net_margin = net_profit / revenue if revenue > 0 else 0

        store_profits[store_code] = StoreProfit(
            store_code=store_code,
            revenue=revenue,
            cost_of_goods=cogs,
            gross_profit=gross_profit,
            gross_margin=gross_margin,
            operating_expense=operating_expense,
            salary=salary + social_fee,
            rent=0.0,  # v0.2 填充
            property_fee=0.0,
            marketing=comprehensive_mall_fee,
            logistics=express_fee,
            depreciation=decorate_fee,
            other_expense=all_other_fee,
            total_expense=cogs + operating_expense + bmanaging_exp,
            operating_profit=operating_profit,
            operating_margin=operating_margin,
            tax=tax,
            net_profit=net_profit,
            net_margin=net_margin,
            social_fee=social_fee,
            mall_fee=comprehensive_mall_fee,
            warehousing=0.0,
            b_manage_expense=bmanaging_exp,
            data_source="real",
            revenue_perspective=row.get("perspective", "actual"),
        )

    # 汇总
    profitable = sum(1 for p in store_profits.values() if p.net_profit > 0)
    loss = sum(1 for p in store_profits.values() if p.net_profit < 0)
    total_revenue = sum(p.revenue for p in store_profits.values())

    summary = ProfitSummary(
        total_revenue=total_revenue,
        total_cogs=sum(p.cost_of_goods for p in store_profits.values()),
        total_gross_profit=sum(p.gross_profit for p in store_profits.values()),
        avg_gross_margin=sum(p.gross_profit for p in store_profits.values()) / total_revenue if total_revenue > 0 else 0,
        total_operating_expense=sum(p.operating_expense for p in store_profits.values()),
        total_operating_profit=sum(p.operating_profit for p in store_profits.values()),
        avg_operating_margin=sum(p.operating_profit for p in store_profits.values()) / total_revenue if total_revenue > 0 else 0,
        total_tax=0.0,
        total_net_profit=sum(p.net_profit for p in store_profits.values()),
        avg_net_margin=sum(p.net_profit for p in store_profits.values()) / total_revenue if total_revenue > 0 else 0,
        store_count=len(store_profits),
        profitable_count=profitable,
        loss_count=loss,
        store_profits=store_profits,
    )

    logger.info(
        f"利润测算完成(销售驱动): {summary.store_count} 家门店, "
        f"总收入={summary.total_revenue:,.0f}, "
        f"净利润={summary.total_net_profit:,.0f}({summary.avg_net_margin:.1%})"
    )

    return summary
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_profit_v01.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/profit/profit_calculator.py tests/unit/test_profit_v01.py
git commit -m "feat(profit): add calculate_from_sales for sales-driven profit"
```

---

## Phase 5: Risk Assessment Update

### Task 5.1: Update risk assessor for sales-only

**Files:**
- Modify: `src/risk/risk_assessor.py`
- Test: `tests/unit/test_risk_v01.py`

- [ ] **Step 1: Write tests**

```python
# tests/unit/test_risk_v01.py
import pytest
import pandas as pd
from src.risk.risk_assessor import RiskAssessor


@pytest.fixture
def sales_history():
    """模拟历史销售数据"""
    dates = pd.date_range("2025-01-01", periods=365, freq="D")
    import numpy as np
    np.random.seed(42)
    values = 50000 + np.random.normal(0, 5000, 365)
    return pd.DataFrame({
        "store_no": "S001",
        "base_date": dates.strftime("%Y%m%d"),
        "revenue": values,
    })


def test_assess_risk_returns_probability(sales_history):
    """测试风险评估返回达标概率"""
    assessor = RiskAssessor()
    result = assessor.assess_store_risk(
        store_no="S001",
        target=1500000,  # 月目标
        sales_history=sales_history,
    )

    assert "reachability_prob" in result
    assert "risk_level" in result
    assert 0 <= result["reachability_prob"] <= 1


def test_risk_level_classification(sales_history):
    """测试风险等级分类"""
    assessor = RiskAssessor()

    # 低目标 → 低风险
    low_result = assessor.assess_store_risk(
        store_no="S001", target=100000, sales_history=sales_history,
    )
    assert low_result["risk_level"] in ["low", "medium"]

    # 高目标 → 高风险
    high_result = assessor.assess_store_risk(
        store_no="S001", target=5000000, sales_history=sales_history,
    )
    assert high_result["risk_level"] in ["high", "critical"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_risk_v01.py -v
```

- [ ] **Step 3: Update RiskAssessor**

Read existing `src/risk/risk_assessor.py` first, then add the sales-only method:

```python
# Add to RiskAssessor class

def assess_store_risk(
    self,
    store_no: str,
    target: float,
    sales_history: pd.DataFrame,
    monte_carlo_n: int = 1000,
) -> dict:
    """评估单店销售达标风险

    Args:
        store_no: 门店编码
        target: 月度销售目标
        sales_history: 历史日销售数据（需包含 revenue 列）
        monte_carlo_n: 蒙特卡洛模拟次数

    Returns:
        {reachability_prob, risk_level, pressure_score, scenarios}
    """
    import numpy as np

    store_data = sales_history[sales_history["store_no"] == store_no]["revenue"]

    if store_data.empty:
        return {
            "reachability_prob": 0.5,
            "risk_level": "medium",
            "pressure_score": 1.0,
            "scenarios": {},
        }

    # 计算日均和标准差
    mu = store_data.mean()
    sigma = store_data.std()

    # 月度汇总（假设 30 天）
    monthly_mu = mu * 30
    monthly_sigma = sigma * np.sqrt(30)

    # 蒙特卡洛模拟
    np.random.seed(42)
    simulations = np.random.normal(monthly_mu, monthly_sigma, monte_carlo_n)

    # 达标概率
    reach_count = np.sum(simulations >= target)
    reachability_prob = reach_count / monte_carlo_n

    # 风险等级
    if reachability_prob >= 0.8:
        risk_level = "low"
    elif reachability_prob >= 0.6:
        risk_level = "medium"
    elif reachability_prob >= 0.4:
        risk_level = "high"
    else:
        risk_level = "critical"

    # 压力分数
    pressure_score = target / monthly_mu if monthly_mu > 0 else 999

    # 情景模拟
    scenarios = {
        "optimistic": {
            "revenue": monthly_mu * 1.1,
            "profit": monthly_mu * 1.1 * 0.3,  # 假设 30% 利润率
        },
        "base": {
            "revenue": monthly_mu,
            "profit": monthly_mu * 0.3,
        },
        "pessimistic": {
            "revenue": monthly_mu * 0.9,
            "profit": monthly_mu * 0.9 * 0.3,
        },
    }

    return {
        "store_no": store_no,
        "target": target,
        "baseline": monthly_mu,
        "reachability_prob": round(reachability_prob, 4),
        "risk_level": risk_level,
        "pressure_score": round(pressure_score, 4),
        "scenarios": scenarios,
    }
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_risk_v01.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/risk/risk_assessor.py tests/unit/test_risk_v01.py
git commit -m "feat(risk): add sales-only risk assessment"
```

---

## Phase 6: Agent Updates

### Task 6.1: Update DataAgent

**Files:**
- Modify: `src/agents/data_agent.py`

- [ ] **Step 1: Update DataAgent to use SalesDataCollector**

```python
# src/agents/data_agent.py
"""数据采集 Agent

职责：从 3 张销售表采集数据，生成统一宽表。
"""

import pandas as pd
from loguru import logger

from src.data.collectors.sales_collector import SalesDataCollector


class DataAgent:
    """数据采集 Agent"""

    def __init__(self, adapter: str = "mock"):
        self.collector = SalesDataCollector(adapter=adapter)
        self.name = "DataAgent"

    def collect(
        self,
        store_no: str = None,
        date_range: tuple = None,
        perspective: str = "actual",
    ) -> pd.DataFrame:
        """采集数据并生成统一宽表

        Args:
            store_no: 门店编码，None 表示全部
            date_range: (start_date, end_date)
            perspective: "actual" | "rebate"

        Returns:
            统一销售宽表 DataFrame
        """
        logger.info(f"[{self.name}] 开始采集数据: store={store_no}, range={date_range}")

        df = self.collector.collect_unified_sales(
            store_no=store_no,
            date_range=date_range,
            perspective=perspective,
        )

        logger.info(f"[{self.name}] 数据采集完成: {len(df)} 行, {df['store_no'].nunique()} 家门店")
        return df
```

- [ ] **Step 2: Commit**

```bash
git add src/agents/data_agent.py
git commit -m "feat(agent): update DataAgent to use SalesDataCollector"
```

### Task 6.2: Update BaselineAgent

**Files:**
- Modify: `src/agents/baseline_agent.py`

- [ ] **Step 1: Update BaselineAgent**

```python
# src/agents/baseline_agent.py
"""基线预估 Agent

职责：从销售数据推算基线收入和折扣预测。
"""

import pandas as pd
from loguru import logger

from src.forecasting.rules.baseline_engine import BaselineEngine
from src.forecasting.discount.predictor import DiscountPredictor


class BaselineAgent:
    """基线预估 Agent"""

    def __init__(self):
        self.name = "BaselineAgent"
        self.engine = BaselineEngine()

    def estimate(
        self,
        sales_df: pd.DataFrame,
        date_range: tuple = None,
    ) -> dict:
        """估算基线收入

        Args:
            sales_df: 统一销售宽表
            date_range: 预测目标日期范围

        Returns:
            {store_baselines: {store_no: baseline_revenue}, discount_forecasts: {...}}
        """
        logger.info(f"[{self.name}] 开始基线预估: {sales_df['store_no'].nunique()} 家门店")

        # 1. 基线收入估算
        store_baselines = {}
        for store_no in sales_df["store_no"].unique():
            store_data = sales_df[sales_df["store_no"] == store_no]
            baseline = self._estimate_store_baseline(store_no, store_data)
            store_baselines[store_no] = baseline

        # 2. 折扣预测
        discount_forecasts = {}
        try:
            # 需要 POS 数据来做折扣预测
            # 从宽表的 avg_discount 字段做简单预测
            for brand in sales_df["brand"].unique():
                brand_data = sales_df[sales_df["brand"] == brand]
                avg_discount = brand_data["avg_discount"].mean()
                discount_forecasts[brand] = {
                    "current_avg_discount": round(avg_discount, 4),
                    "forecast_next_month": round(avg_discount * 0.98, 4),  # 简单趋势
                }
        except Exception as e:
            logger.warning(f"折扣预测失败: {e}")

        logger.info(f"[{self.name}] 基线预估完成: {len(store_baselines)} 家门店")
        return {
            "store_baselines": store_baselines,
            "discount_forecasts": discount_forecasts,
        }

    def _estimate_store_baseline(self, store_no: str, store_data: pd.DataFrame) -> float:
        """估算单店基线收入"""
        # 简单取最近 N 天的平均值 × 30
        recent = store_data.sort_values("base_date").tail(30)
        if recent.empty:
            return 0.0
        daily_avg = recent["revenue"].mean()
        return round(daily_avg * 30, 2)
```

- [ ] **Step 2: Commit**

```bash
git add src/agents/baseline_agent.py
git commit -m "feat(agent): update BaselineAgent for sales-driven estimation"
```

### Task 6.3: Update ProfitAgent

**Files:**
- Modify: `src/agents/profit_agent.py`

- [ ] **Step 1: Update ProfitAgent**

```python
# src/agents/profit_agent.py
"""利润测算 Agent

职责：从统一宽表计算四层利润，支持双口径对比。
"""

import pandas as pd
from loguru import logger

from src.profit.profit_calculator import ProfitCalculator, ProfitSummary


class ProfitAgent:
    """利润测算 Agent"""

    def __init__(self):
        self.name = "ProfitAgent"
        self.calculator = ProfitCalculator()

    def calculate(self, sales_df: pd.DataFrame) -> ProfitSummary:
        """计算利润

        Args:
            sales_df: 统一销售宽表

        Returns:
            ProfitSummary
        """
        logger.info(f"[{self.name}] 开始利润测算: {sales_df['store_no'].nunique()} 家门店")

        summary = self.calculator.calculate_from_sales(sales_df)

        logger.info(
            f"[{self.name}] 利润测算完成: "
            f"总收入={summary.total_revenue:,.0f}, "
            f"净利润={summary.total_net_profit:,.0f}"
        )
        return summary
```

- [ ] **Step 2: Commit**

```bash
git add src/agents/profit_agent.py
git commit -m "feat(agent): update ProfitAgent to use calculate_from_sales"
```

### Task 6.4: Update RiskAgent

**Files:**
- Modify: `src/agents/risk_agent.py`

- [ ] **Step 1: Update RiskAgent**

```python
# src/agents/risk_agent.py
"""风险评估 Agent

职责：基于销售数据评估达标风险。
"""

import pandas as pd
from loguru import logger

from src.risk.risk_assessor import RiskAssessor


class RiskAgent:
    """风险评估 Agent"""

    def __init__(self):
        self.name = "RiskAgent"
        self.assessor = RiskAssessor()

    def assess(
        self,
        sales_df: pd.DataFrame,
        targets: dict = None,
    ) -> dict:
        """评估风险

        Args:
            sales_df: 统一销售宽表
            targets: {store_no: target_value}，可选

        Returns:
            {store_risks: {store_no: risk_result}, summary: {...}}
        """
        logger.info(f"[{self.name}] 开始风险评估")

        store_risks = {}
        for store_no in sales_df["store_no"].unique():
            store_data = sales_df[sales_df["store_no"] == store_no]
            target = (targets or {}).get(store_no, store_data["revenue"].mean() * 30)

            result = self.assessor.assess_store_risk(
                store_no=store_no,
                target=target,
                sales_history=store_data,
            )
            store_risks[store_no] = result

        # 汇总
        risk_levels = [r["risk_level"] for r in store_risks.values()]
        summary = {
            "total_stores": len(store_risks),
            "low_risk": risk_levels.count("low"),
            "medium_risk": risk_levels.count("medium"),
            "high_risk": risk_levels.count("high"),
            "critical_risk": risk_levels.count("critical"),
        }

        logger.info(f"[{self.name}] 风险评估完成: {summary}")
        return {"store_risks": store_risks, "summary": summary}
```

- [ ] **Step 2: Commit**

```bash
git add src/agents/risk_agent.py
git commit -m "feat(agent): update RiskAgent for sales-only assessment"
```

### Task 6.5: Update Orchestrator

**Files:**
- Modify: `src/agents/orchestrator.py`

- [ ] **Step 1: Update Orchestrator**

```python
# src/agents/orchestrator.py
"""编排器

职责：协调各 Agent 执行完整的利润测算流程。
"""

import pandas as pd
from loguru import logger

from src.agents.data_agent import DataAgent
from src.agents.baseline_agent import BaselineAgent
from src.agents.profit_agent import ProfitAgent
from src.agents.risk_agent import RiskAgent
from src.agents.allocation_agent import AllocationAgent


class Orchestrator:
    """编排器"""

    def __init__(self, adapter: str = "mock"):
        self.name = "Orchestrator"
        self.data_agent = DataAgent(adapter=adapter)
        self.baseline_agent = BaselineAgent()
        self.profit_agent = ProfitAgent()
        self.risk_agent = RiskAgent()
        self.allocation_agent = AllocationAgent()

    def run_full(
        self,
        store_no: str = None,
        date_range: tuple = None,
        total_target: float = None,
        perspective: str = "actual",
    ) -> dict:
        """执行完整流程

        Args:
            store_no: 门店编码
            date_range: 日期范围
            total_target: 总目标（可选）
            perspective: 口径

        Returns:
            {baseline, allocation, profit, risk, summary}
        """
        logger.info(f"[{self.name}] 开始完整流程")

        result = {}

        # Step 1: 数据采集
        logger.info(f"[{self.name}] Step 1/5: 数据采集")
        sales_df = self.data_agent.collect(store_no, date_range, perspective)
        result["data"] = {"rows": len(sales_df), "stores": sales_df["store_no"].nunique()}

        # Step 2: 基线预估
        logger.info(f"[{self.name}] Step 2/5: 基线预估")
        baseline = self.baseline_agent.estimate(sales_df, date_range)
        result["baseline"] = baseline

        # Step 3: 目标分配（如果有总目标）
        if total_target:
            logger.info(f"[{self.name}] Step 3/5: 目标分配")
            allocation = self.allocation_agent.allocate(
                total_target=total_target,
                baselines=baseline["store_baselines"],
            )
            result["allocation"] = allocation
            targets = {s["store_no"]: s["target"] for s in allocation["store_targets"]}
        else:
            result["allocation"] = None
            targets = None

        # Step 4: 利润测算
        logger.info(f"[{self.name}] Step 4/5: 利润测算")
        profit = self.profit_agent.calculate(sales_df)
        result["profit"] = {
            "total_revenue": profit.total_revenue,
            "total_gross_profit": profit.total_gross_profit,
            "total_operating_profit": profit.total_operating_profit,
            "total_net_profit": profit.total_net_profit,
            "avg_gross_margin": profit.avg_gross_margin,
            "avg_operating_margin": profit.avg_operating_margin,
            "store_count": profit.store_count,
            "profitable_count": profit.profitable_count,
            "loss_count": profit.loss_count,
        }

        # Step 5: 风险评估
        logger.info(f"[{self.name}] Step 5/5: 风险评估")
        risk = self.risk_agent.assess(sales_df, targets)
        result["risk"] = risk

        logger.info(f"[{self.name}] 完整流程完成")
        return result

    def run_quick(self, store_no: str, date_range: tuple) -> dict:
        """快速测算（单店）"""
        return self.run_full(store_no=store_no, date_range=date_range)
```

- [ ] **Step 2: Commit**

```bash
git add src/agents/orchestrator.py
git commit -m "feat(agent): update Orchestrator for sales-driven workflow"
```

---

## Phase 7: API Routes Update

### Task 7.1: Update API routes

**Files:**
- Modify: `src/api/routes/profit.py`
- Modify: `src/api/routes/forecast.py`
- Modify: `src/api/routes/risk.py`
- Modify: `src/api/routes/orchestrate.py`

- [ ] **Step 1: Update profit routes**

```python
# src/api/routes/profit.py
"""利润测算 API 路由"""

from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/profit", tags=["profit"])


@router.post("/calculate")
async def calculate_profit(
    store_no: Optional[str] = Query(None, description="门店编码"),
    region: Optional[str] = Query(None, description="区域"),
    brand: Optional[str] = Query(None, description="品牌"),
    date_start: str = Query(..., description="开始日期 YYYYMMDD"),
    date_end: str = Query(..., description="结束日期 YYYYMMDD"),
    perspective: str = Query("actual", description="口径: actual|rebate"),
):
    """计算利润"""
    from src.agents.data_agent import DataAgent
    from src.profit.profit_calculator import ProfitCalculator

    agent = DataAgent()
    df = agent.collect(store_no=store_no, date_range=(date_start, date_end), perspective=perspective)

    if region:
        df = df[df["region"] == region]
    if brand:
        df = df[df["brand"] == brand]

    calc = ProfitCalculator()
    summary = calc.calculate_from_sales(df)

    return {
        "total_revenue": summary.total_revenue,
        "total_gross_profit": summary.total_gross_profit,
        "total_operating_profit": summary.total_operating_profit,
        "total_net_profit": summary.total_net_profit,
        "avg_gross_margin": summary.avg_gross_margin,
        "store_count": summary.store_count,
        "profitable_count": summary.profitable_count,
        "loss_count": summary.loss_count,
    }


@router.get("/drill-down")
async def drill_down(
    dimension: str = Query(..., description="维度: region|brand|store"),
    date_start: str = Query(..., description="开始日期"),
    date_end: str = Query(..., description="结束日期"),
    perspective: str = Query("actual", description="口径"),
):
    """按维度下钻"""
    from src.agents.data_agent import DataAgent
    from src.profit.profit_calculator import ProfitCalculator

    agent = DataAgent()
    df = agent.collect(date_range=(date_start, date_end), perspective=perspective)

    calc = ProfitCalculator()

    if dimension == "store":
        summary = calc.calculate_from_sales(df)
        rows = []
        for code, sp in summary.store_profits.items():
            rows.append({
                "store_no": code,
                "revenue": sp.revenue,
                "gross_profit": sp.gross_profit,
                "operating_profit": sp.operating_profit,
                "net_profit": sp.net_profit,
            })
        return {"dimension": "store", "data": rows}
    else:
        col = "region" if dimension == "region" else "brand"
        results = []
        for group_name, group_df in df.groupby(col):
            summary = calc.calculate_from_sales(group_df)
            results.append({
                "name": group_name,
                "revenue": summary.total_revenue,
                "gross_profit": summary.total_gross_profit,
                "operating_profit": summary.total_operating_profit,
                "net_profit": summary.total_net_profit,
                "store_count": summary.store_count,
            })
        return {"dimension": dimension, "data": results}
```

- [ ] **Step 2: Update orchestrate routes**

```python
# src/api/routes/orchestrate.py
"""编排 API 路由"""

from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/orchestrate", tags=["orchestrate"])


@router.post("/full")
async def run_full(
    store_no: Optional[str] = Query(None),
    date_start: str = Query(...),
    date_end: str = Query(...),
    total_target: Optional[float] = Query(None),
    perspective: str = Query("actual"),
):
    """执行完整流程"""
    from src.agents.orchestrator import Orchestrator

    orch = Orchestrator()
    result = orch.run_full(
        store_no=store_no,
        date_range=(date_start, date_end),
        total_target=total_target,
        perspective=perspective,
    )
    return result


@router.post("/quick")
async def run_quick(
    store_no: str = Query(...),
    date_start: str = Query(...),
    date_end: str = Query(...),
):
    """快速测算"""
    from src.agents.orchestrator import Orchestrator

    orch = Orchestrator()
    result = orch.run_quick(store_no=store_no, date_range=(date_start, date_end))
    return result
```

- [ ] **Step 3: Commit**

```bash
git add src/api/routes/profit.py src/api/routes/orchestrate.py
git commit -m "feat(api): update profit and orchestrate routes for v0.1"
```

---

## Phase 8: Docker Update

### Task 8.1: Update Docker configuration

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker/docker-compose.prod.yml`

- [ ] **Step 1: Update docker-compose.yml**

```yaml
# docker-compose.yml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - .:/app
    command: python run.py

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    depends_on:
      - app

  mysql:
    image: mysql:8.0
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: ycf0312!
      MYSQL_DATABASE: profit_forecast
    volumes:
      - mysql_data:/var/lib/mysql
      - ./docker/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  mysql_data:
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml docker/docker-compose.prod.yml
git commit -m "feat(docker): switch from PostgreSQL to MySQL"
```

---

## Phase 9: Final Cleanup

### Task 9.1: Update pyproject.toml and run full test suite

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update pyproject.toml dependencies**

```toml
[project]
name = "profit-forecast-v01"
version = "0.1.0"
description = "销售驱动利润测算系统 v0.1"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "sqlalchemy>=2.0.0",
    "pymysql>=1.1.0",
    "cryptography>=41.0.0",
    "pandas>=2.1.0",
    "numpy>=1.24.0",
    "scikit-learn>=1.3.0",
    "statsmodels>=0.14.0",
    "prophet>=1.1.0",
    "loguru>=0.7.0",
    "pydantic>=2.5.0",
    "redis>=5.0.0",
    "alembic>=1.13.0",
]
```

- [ ] **Step 2: Run full test suite**

```bash
cd /Users/ycf/Documents/Claude_Code/Claude_Priject/profit-forecast-v0.1
source .venv/bin/activate
pytest tests/ -v --tb=short 2>&1 | tail -50
```

- [ ] **Step 3: Fix any failing tests**

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: v0.1 final cleanup and test fixes"
```

### Task 9.2: Verify project runs

- [ ] **Step 1: Start the application**

```bash
cd /Users/ycf/Documents/Claude_Code/Claude_Priject/profit-forecast-v0.1
source .venv/bin/activate
python run.py
```

- [ ] **Step 2: Test API endpoint**

```bash
curl http://localhost:8000/docs
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: verify v0.1 runs successfully"
```

---

## Execution Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 0 | 1 | 项目复制和初始化 |
| 1 | 3 | 数据库层（MySQL） |
| 2 | 3 | 数据层（SalesDataCollector + ETL） |
| 3 | 1 | 折扣预测模块 |
| 4 | 1 | 利润测算更新 |
| 5 | 1 | 风险评估更新 |
| 6 | 5 | Agent 更新 |
| 7 | 1 | API 路由更新 |
| 8 | 1 | Docker 更新 |
| 9 | 2 | 最终清理和验证 |
| **Total** | **19** | |
