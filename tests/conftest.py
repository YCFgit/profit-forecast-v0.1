"""pytest 全局 fixtures

提供共享的测试数据和工具。
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# 排除旧的脚本式测试文件（已被 tests/unit/ 和 tests/integration/ 替代）
collect_ignore_glob = ["test_*.py"]

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.collectors.factory import create_collector
from src.allocation.weight_calculator import StoreProfile, WeightCalculator
from src.allocation.target_allocator import TargetAllocator


# ============================================================
# Mock 数据 fixtures
# ============================================================

@pytest.fixture
async def mock_collector():
    """Mock 数据采集器"""
    collector = create_collector("mock")
    await collector.connect()
    yield collector
    await collector.disconnect()


@pytest.fixture
async def stores_df(mock_collector):
    """门店 DataFrame"""
    return await mock_collector.fetch_stores()


@pytest.fixture
async def daily_sales_df(mock_collector):
    """日销 DataFrame"""
    return await mock_collector.fetch_daily_sales()


@pytest.fixture
async def monthly_metrics_df(mock_collector):
    """月度指标 DataFrame"""
    return await mock_collector.fetch_monthly_metrics()


# ============================================================
# 业务数据 fixtures
# ============================================================

@pytest.fixture
def store_profiles(stores_df, monthly_metrics_df):
    """门店画像字典"""
    profiles = {}
    for _, row in stores_df.iterrows():
        code = row["store_code"]
        metrics = monthly_metrics_df[monthly_metrics_df["store_code"] == code]
        avg_profit = metrics["gross_profit"].mean() if "gross_profit" in metrics.columns else 0
        avg_sqm = metrics["sales_per_sqm"].mean() if "sales_per_sqm" in metrics.columns else 0

        profiles[code] = StoreProfile(
            store_code=code,
            historical_profit=avg_profit,
            sales_per_sqm=avg_sqm,
            commercial_tier=row.get("commercial_tier", "C"),
            city_level="二线",
            store_area=row.get("store_area", 100),
            growth_rate=0,
            opening_months=365,
            baseline_sales=metrics["sales_amount"].mean() if "sales_amount" in metrics.columns else 0,
        )
    return profiles


@pytest.fixture
def baselines(store_profiles):
    """基线利润字典"""
    return {code: p.historical_profit if p.historical_profit > 0 else 100_000
            for code, p in store_profiles.items()}


@pytest.fixture
def allocation_plan(baselines, store_profiles):
    """承压分配方案"""
    total_target = sum(baselines.values()) * 1.20
    allocator = TargetAllocator()
    return allocator.allocate(total_target, baselines, store_profiles)


@pytest.fixture
def total_target(baselines):
    """总目标（基线增长 20%）"""
    return sum(baselines.values()) * 1.20


# ============================================================
# FastAPI TestClient
# ============================================================

@pytest.fixture
def app():
    """FastAPI 应用实例"""
    from src.api.app import create_app
    return create_app()


@pytest.fixture
def client(app):
    """FastAPI 测试客户端"""
    from fastapi.testclient import TestClient
    return TestClient(app)
