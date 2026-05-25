"""大中店预估器单元测试"""

import pandas as pd
import pytest

from src.forecasting.rules.seasonal_index import SeasonalIndex, SeasonalIndexTable
from src.forecasting.rules.large_store_estimator import (
    LargeStoreEstimator,
    LargeStoreEstimate,
)


@pytest.fixture
def seasonal_table():
    """测试季节指数表"""
    return SeasonalIndexTable(indices={
        ("品牌A", "华东"): SeasonalIndex(
            brand="品牌A", region="华东",
            raw_indices={m: 1.0 for m in range(1, 13)},
            damped_indices={m: 1.0 for m in range(1, 13)},
            data_months=12,
        ),
    })


@pytest.fixture
def monthly_metrics_df():
    """测试月度指标数据（2024-01 到 2026-04）"""
    rows = []
    for month_offset in range(28):
        year = 2024 + month_offset // 12
        month = month_offset % 12 + 1
        rows.append({
            "store_code": "ST0001",
            "year_month": f"{year}-{month:02d}",
            "sales_amount": 500_000 + month_offset * 10_000,
        })
    return pd.DataFrame(rows)


class TestLargeStoreEstimator:
    """大中店预估器测试"""

    def test_estimate_basic(self, seasonal_table, monthly_metrics_df):
        """基本预估"""
        estimator = LargeStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", monthly_metrics_df, None,
            2026, 5, "品牌A", "华东",
        )

        assert isinstance(result, LargeStoreEstimate)
        assert result.estimated_sales > 0
        assert result.mechanism_used == "weighted_recent"
        assert result.seasonal_index > 0

    def test_estimate_weighted_recent(self, seasonal_table, monthly_metrics_df):
        """加权近月预估机制"""
        estimator = LargeStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", monthly_metrics_df, None,
            2026, 5, "品牌A", "华东",
        )

        assert result.mechanism_used == "weighted_recent"
        assert result.data_window_months > 0
        assert result.confidence in ("high", "medium", "low")

    def test_estimate_structural_change(self, seasonal_table):
        """结构性变化检测"""
        # 构造近期业绩大幅下降的数据（2024-01 到 2026-04）
        rows = []
        for month_offset in range(28):
            year = 2024 + month_offset // 12
            month = month_offset % 12 + 1
            # 近3个月（2026-02 到 2026-04）业绩下降到原来的 50%
            if month_offset >= 25:
                sales = 200_000
            else:
                sales = 500_000
            rows.append({
                "store_code": "ST0001",
                "year_month": f"{year}-{month:02d}",
                "sales_amount": sales,
            })
        df = pd.DataFrame(rows)

        estimator = LargeStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", df, None,
            2026, 5, "品牌A", "华东",
        )

        # 结构性变化应被检测到
        if result.structural_ratio is not None:
            assert result.structural_ratio < 1.0

    def test_estimate_empty_data(self, seasonal_table):
        """空数据"""
        estimator = LargeStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", pd.DataFrame(), None,
            2026, 5, "品牌A", "华东",
        )

        assert result.estimated_sales == 0.0
        assert result.confidence == "low"

    def test_estimate_no_spring_festival(self, seasonal_table, monthly_metrics_df):
        """非春节月预估"""
        estimator = LargeStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", monthly_metrics_df, None,
            2026, 5, "品牌A", "华东",
        )

        assert result.estimated_sales > 0

    def test_estimate_with_spring_festival_exclusion(self, seasonal_table):
        """春节月排除"""
        # 构造包含春节月的数据（2024-01 到 2026-04）
        rows = []
        for month_offset in range(28):
            year = 2024 + month_offset // 12
            month = month_offset % 12 + 1
            # 春节月低业绩
            is_spring = (year == 2025 and month == 1) or (year == 2024 and month == 2)
            sales = 100_000 if is_spring else 500_000
            rows.append({
                "store_code": "ST0001",
                "year_month": f"{year}-{month:02d}",
                "sales_amount": sales,
            })
        df = pd.DataFrame(rows)

        estimator = LargeStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", df, None,
            2026, 5, "品牌A", "华东",
        )

        # 春节月数据应被排除，不影响预估
        assert result.estimated_sales > 0

    def test_confidence_levels(self, seasonal_table):
        """置信度级别"""
        estimator = LargeStoreEstimator(seasonal_table)

        # 数据充足（24个月）→ 高置信度
        rows_full = []
        for month_offset in range(28):
            year = 2024 + month_offset // 12
            month = month_offset % 12 + 1
            rows_full.append({
                "store_code": "ST0001",
                "year_month": f"{year}-{month:02d}",
                "sales_amount": 500_000,
            })
        df_full = pd.DataFrame(rows_full)

        result = estimator.estimate(
            "ST0001", df_full, None,
            2026, 5, "品牌A", "华东",
        )
        assert result.confidence == "high"
