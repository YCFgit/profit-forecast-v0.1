"""其他预估器单元测试（小店、新店、虚拟店、临时特卖店、关店、春节月）"""

import pandas as pd
import pytest

from src.forecasting.rules.seasonal_index import SeasonalIndex, SeasonalIndexTable
from src.forecasting.rules.small_store_estimator import SmallStoreEstimator, SmallStoreEstimate
from src.forecasting.rules.new_store_estimator import NewStoreEstimator, NewStoreEstimate
from src.forecasting.rules.virtual_store_estimator import VirtualStoreEstimator, VirtualStoreEstimate
from src.forecasting.rules.temp_store_estimator import TempStoreEstimator, TempStoreEstimate
from src.forecasting.rules.closing_store_estimator import ClosingStoreEstimator, ClosingStoreEstimate
from src.forecasting.rules.spring_festival import SpringFestivalEstimator, SpringFestivalEstimate


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
    for code, base in [("ST0001", 100_000), ("ST0002", 50_000)]:
        for month_offset in range(28):
            year = 2024 + month_offset // 12
            month = month_offset % 12 + 1
            rows.append({
                "store_code": code,
                "year_month": f"{year}-{month:02d}",
                "sales_amount": base * (1 + month_offset * 0.02),
            })
    return pd.DataFrame(rows)


@pytest.fixture
def stores_df():
    """测试门店数据"""
    return pd.DataFrame([
        {"store_code": "ST0001", "brand": "品牌A", "region": "华东",
         "opening_date": "2020-01-01"},
        {"store_code": "ST0002", "brand": "品牌A", "region": "华东",
         "opening_date": "2020-06-01"},
        {"store_code": "ST0003", "brand": "品牌A", "region": "华东",
         "opening_date": "2025-06-01"},
    ])


# ============================================================
# 小店预估器
# ============================================================

class TestSmallStoreEstimator:
    """小店预估器测试"""

    def test_estimate_basic(self, seasonal_table, monthly_metrics_df):
        """基本预估"""
        estimator = SmallStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", monthly_metrics_df, 2026, 5, "品牌A", "华东",
        )

        assert isinstance(result, SmallStoreEstimate)
        assert result.estimated_sales > 0
        assert result.data_months > 0

    def test_estimate_empty_data(self, seasonal_table):
        """空数据"""
        estimator = SmallStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", pd.DataFrame(), 2026, 5, "品牌A", "华东",
        )

        assert result.estimated_sales == 0.0
        assert result.data_months == 0

    def test_estimate_spring_festival_excluded(self, seasonal_table):
        """春节月排除"""
        rows = []
        for month in range(1, 13):
            rows.append({
                "store_code": "ST0001",
                "year_month": f"2025-{month:02d}",
                "sales_amount": 100_000,
            })
        df = pd.DataFrame(rows)

        estimator = SmallStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", df, 2026, 1, "品牌A", "华东",
        )

        # 2025-01是春节月，应被排除
        assert result.data_months <= 3


# ============================================================
# 新店预估器
# ============================================================

class TestNewStoreEstimator:
    """新店预估器测试"""

    def test_estimate_basic(self, seasonal_table, stores_df, monthly_metrics_df):
        """基本预估"""
        estimator = NewStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0003", stores_df, monthly_metrics_df,
            2026, 5, "品牌A", "华东", "2025-06-01",
        )

        assert isinstance(result, NewStoreEstimate)
        assert result.estimated_sales >= 0
        assert result.ramp_coefficient > 0
        assert result.opening_months > 0

    def test_ramp_coefficients(self, seasonal_table, stores_df, monthly_metrics_df):
        """爬坡系数测试"""
        estimator = NewStoreEstimator(seasonal_table)

        # 0-3个月：0.40
        result = estimator.estimate(
            "ST0003", stores_df, monthly_metrics_df,
            2026, 1, "品牌A", "华东", "2025-12-01",
        )
        assert result.ramp_coefficient == 0.40

        # 4-6个月：0.60
        result = estimator.estimate(
            "ST0003", stores_df, monthly_metrics_df,
            2026, 5, "品牌A", "华东", "2025-12-01",
        )
        assert result.ramp_coefficient == 0.60

        # 7-12个月：0.80
        result = estimator.estimate(
            "ST0003", stores_df, monthly_metrics_df,
            2026, 10, "品牌A", "华东", "2025-12-01",
        )
        assert result.ramp_coefficient == 0.80

    def test_no_opening_date(self, seasonal_table, stores_df, monthly_metrics_df):
        """无开业日期"""
        estimator = NewStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0003", stores_df, monthly_metrics_df,
            2026, 5, "品牌A", "华东", None,
        )

        # 无开业日期默认24个月，爬坡系数0.90（<=24月）
        assert result.ramp_coefficient == 0.90
        assert result.opening_months == 24


# ============================================================
# 虚拟店预估器
# ============================================================

class TestVirtualStoreEstimator:
    """虚拟店预估器测试"""

    def test_estimate_basic(self, seasonal_table, monthly_metrics_df):
        """基本预估"""
        estimator = VirtualStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", monthly_metrics_df, 2026, 5, "品牌A", "华东",
        )

        assert isinstance(result, VirtualStoreEstimate)
        assert result.estimated_sales > 0
        assert result.data_months > 0

    def test_estimate_empty(self, seasonal_table):
        """空数据"""
        estimator = VirtualStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", pd.DataFrame(), 2026, 5, "品牌A", "华东",
        )

        assert result.estimated_sales == 0.0


# ============================================================
# 临时特卖店预估器
# ============================================================

class TestTempStoreEstimator:
    """临时特卖店预估器测试"""

    def test_estimate_basic(self, monthly_metrics_df):
        """基本预估"""
        estimator = TempStoreEstimator()
        result = estimator.estimate("ST0001", monthly_metrics_df, 2026, 5)

        assert isinstance(result, TempStoreEstimate)
        assert result.estimated_sales > 0
        assert result.participates_allocation is False

    def test_estimate_empty(self):
        """空数据"""
        estimator = TempStoreEstimator()
        result = estimator.estimate("ST0001", pd.DataFrame(), 2026, 5)

        assert result.estimated_sales == 0.0


# ============================================================
# 关店预估器
# ============================================================

class TestClosingStoreEstimator:
    """关店预估器测试"""

    def test_estimate_with_closing_date(self, seasonal_table, monthly_metrics_df):
        """有明确关店日期"""
        estimator = ClosingStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", monthly_metrics_df, 2026, 5,
            closing_date="2026-05-15", brand="品牌A", region="华东",
        )

        assert isinstance(result, ClosingStoreEstimate)
        assert result.estimated_sales > 0
        assert result.operating_days == 15
        assert result.total_days == 31  # 5月31天
        assert result.day_ratio == pytest.approx(15 / 31, abs=0.01)

    def test_estimate_no_closing_date(self, seasonal_table, monthly_metrics_df):
        """无关店日期（全月营业）"""
        estimator = ClosingStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", monthly_metrics_df, 2026, 5,
            brand="品牌A", region="华东",
        )

        assert result.operating_days == 31
        assert result.day_ratio == 1.0

    def test_estimate_already_closed(self, seasonal_table, monthly_metrics_df):
        """已关店（关店日在目标月之前）"""
        estimator = ClosingStoreEstimator(seasonal_table)
        result = estimator.estimate(
            "ST0001", monthly_metrics_df, 2026, 5,
            closing_date="2026-04-01", brand="品牌A", region="华东",
        )

        assert result.operating_days == 0
        assert result.estimated_sales == 0.0

    def test_closing_ratio_effect(self, seasonal_table, monthly_metrics_df):
        """经验系数效果"""
        estimator = ClosingStoreEstimator(seasonal_table)

        # 关店日=月中，业绩应约为全月的一半 × 0.9
        result_mid = estimator.estimate(
            "ST0001", monthly_metrics_df, 2026, 5,
            closing_date="2026-05-16", brand="品牌A", region="华东",
        )
        # 关店日=月底，业绩应接近全月
        result_end = estimator.estimate(
            "ST0001", monthly_metrics_df, 2026, 5,
            closing_date="2026-05-31", brand="品牌A", region="华东",
        )

        assert result_end.estimated_sales > result_mid.estimated_sales


# ============================================================
# 春节月预估器
# ============================================================

class TestSpringFestivalEstimator:
    """春节月预估器测试"""

    def test_estimate_with_history(self, monthly_metrics_df):
        """有历史春节月数据"""
        # 构造包含历史春节月的数据
        rows = []
        for year in [2024, 2025]:
            for month in range(1, 13):
                rows.append({
                    "store_code": "ST0001",
                    "year_month": f"{year}-{month:02d}",
                    "sales_amount": 100_000 if month not in (1, 2) else 80_000,
                })
        df = pd.DataFrame(rows)

        estimator = SpringFestivalEstimator()
        result = estimator.estimate("ST0001", df, 2026, 2)

        assert isinstance(result, SpringFestivalEstimate)
        assert result.estimated_sales > 0

    def test_estimate_fallback(self):
        """历史数据不足，使用回退方法"""
        # 只有近几个月数据，没有历史春节月
        rows = []
        for month in range(8, 13):
            rows.append({
                "store_code": "ST0001",
                "year_month": f"2025-{month:02d}",
                "sales_amount": 100_000,
            })
        df = pd.DataFrame(rows)

        estimator = SpringFestivalEstimator()
        result = estimator.estimate("ST0001", df, 2026, 2)

        assert result.method == "recent_mean_fallback"
        assert result.estimated_sales > 0

    def test_estimate_empty(self):
        """空数据"""
        estimator = SpringFestivalEstimator()
        result = estimator.estimate("ST0001", pd.DataFrame(), 2026, 2)

        assert result.estimated_sales == 0.0

    def test_estimate_batch(self, monthly_metrics_df):
        """批量预估"""
        estimator = SpringFestivalEstimator()
        results = estimator.estimate_batch(
            ["ST0001", "ST0002"], monthly_metrics_df, 2026, 2,
        )

        assert len(results) == 2
        assert "ST0001" in results
        assert "ST0002" in results
