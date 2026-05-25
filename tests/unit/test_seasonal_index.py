"""季节指数计算单元测试"""

import pandas as pd
import pytest

from src.forecasting.rules.seasonal_index import (
    SeasonalIndex,
    SeasonalIndexTable,
    SeasonalIndexCalculator,
)


@pytest.fixture
def stores_df():
    """测试门店数据"""
    return pd.DataFrame([
        {"store_code": "ST0001", "brand": "品牌A", "region": "华东"},
        {"store_code": "ST0002", "brand": "品牌A", "region": "华东"},
        {"store_code": "ST0003", "brand": "品牌B", "region": "华南"},
    ])


@pytest.fixture
def monthly_metrics_df():
    """测试月度指标数据（24个月）

    品牌A华东：12月高（1.4x）、6月低（0.7x）
    品牌B华南：波动较小
    """
    rows = []
    for year in [2024, 2025]:
        for month in range(1, 13):
            ym = f"{year}-{month:02d}"

            # 品牌A华东 - ST0001
            seasonal_a = 1.0 + 0.4 * (1 if month == 12 else (-0.3 if month == 6 else 0))
            rows.append({"store_code": "ST0001", "year_month": ym,
                         "sales_amount": 100_000 * seasonal_a})

            # 品牌A华东 - ST0002
            rows.append({"store_code": "ST0002", "year_month": ym,
                         "sales_amount": 80_000 * seasonal_a})

            # 品牌B华南 - ST0003（季节性较弱）
            seasonal_b = 1.0 + 0.1 * (1 if month in (10, 11) else 0)
            rows.append({"store_code": "ST0003", "year_month": ym,
                         "sales_amount": 60_000 * seasonal_b})

    return pd.DataFrame(rows)


class TestSeasonalIndex:
    """季节指数数据结构测试"""

    def test_get_factor_damped(self):
        """获取阻尼季节因子"""
        idx = SeasonalIndex(
            brand="品牌A", region="华东",
            raw_indices={12: 1.40, 6: 0.70},
            damped_indices={12: 1.20, 6: 0.85},
        )
        assert idx.get_factor(12, damped=True) == 1.20
        assert idx.get_factor(6, damped=True) == 0.85

    def test_get_factor_raw(self):
        """获取原始季节因子"""
        idx = SeasonalIndex(
            brand="品牌A", region="华东",
            raw_indices={12: 1.40, 6: 0.70},
            damped_indices={12: 1.20, 6: 0.85},
        )
        assert idx.get_factor(12, damped=False) == 1.40
        assert idx.get_factor(6, damped=False) == 0.70

    def test_get_factor_missing_month(self):
        """缺失月份返回 1.0"""
        idx = SeasonalIndex(
            brand="品牌A", region="华东",
            raw_indices={12: 1.40},
            damped_indices={12: 1.20},
        )
        assert idx.get_factor(1) == 1.0


class TestSeasonalIndexTable:
    """季节指数表测试"""

    def test_get_factor_exact_match(self):
        """精确匹配品牌×区域"""
        table = SeasonalIndexTable(indices={
            ("品牌A", "华东"): SeasonalIndex(
                brand="品牌A", region="华东",
                raw_indices={12: 1.40},
                damped_indices={12: 1.20},
            ),
        })
        assert table.get_factor("品牌A", "华东", 12) == 1.20

    def test_get_factor_brand_fallback(self):
        """品牌回退匹配"""
        table = SeasonalIndexTable(indices={
            ("品牌A", "华东"): SeasonalIndex(
                brand="品牌A", region="华东",
                raw_indices={12: 1.40},
                damped_indices={12: 1.20},
            ),
        })
        # 品牌A华南没有数据，回退到品牌A华东
        assert table.get_factor("品牌A", "华南", 12) == 1.20

    def test_get_factor_no_match(self):
        """无匹配返回 1.0"""
        table = SeasonalIndexTable(indices={
            ("品牌A", "华东"): SeasonalIndex(
                brand="品牌A", region="华东",
                raw_indices={12: 1.40},
                damped_indices={12: 1.20},
            ),
        })
        assert table.get_factor("品牌X", "华北", 12) == 1.0

    def test_get_all_brands(self):
        """获取所有品牌"""
        table = SeasonalIndexTable(indices={
            ("品牌A", "华东"): SeasonalIndex(brand="品牌A", region="华东"),
            ("品牌B", "华南"): SeasonalIndex(brand="品牌B", region="华南"),
        })
        brands = table.get_all_brands()
        assert set(brands) == {"品牌A", "品牌B"}

    def test_get_all_regions(self):
        """获取所有区域"""
        table = SeasonalIndexTable(indices={
            ("品牌A", "华东"): SeasonalIndex(brand="品牌A", region="华东"),
            ("品牌B", "华南"): SeasonalIndex(brand="品牌B", region="华南"),
        })
        regions = table.get_all_regions()
        assert set(regions) == {"华东", "华南"}


class TestSeasonalIndexCalculator:
    """季节指数计算器测试"""

    def test_calculate_basic(self, monthly_metrics_df, stores_df):
        """基本计算"""
        calc = SeasonalIndexCalculator()
        table = calc.calculate(monthly_metrics_df, stores_df)

        assert isinstance(table, SeasonalIndexTable)
        assert len(table.indices) > 0

    def test_calculate_brand_region_keys(self, monthly_metrics_df, stores_df):
        """品牌×区域键"""
        calc = SeasonalIndexCalculator()
        table = calc.calculate(monthly_metrics_df, stores_df)

        keys = set(table.indices.keys())
        assert ("品牌A", "华东") in keys
        assert ("品牌B", "华南") in keys

    def test_damping_effect(self, monthly_metrics_df, stores_df):
        """阻尼效果：阻尼指数比原始指数更接近 1.0"""
        calc = SeasonalIndexCalculator(damping_factor=0.50)
        table = calc.calculate(monthly_metrics_df, stores_df)

        for idx in table.indices.values():
            for month in idx.raw_indices:
                raw = idx.raw_indices[month]
                damped = idx.damped_indices[month]
                # 阻尼后更接近 1.0
                assert abs(damped - 1.0) < abs(raw - 1.0) + 0.001

    def test_damping_formula(self, monthly_metrics_df, stores_df):
        """阻尼公式验证：damped = 1 + (raw - 1) × 0.50"""
        calc = SeasonalIndexCalculator(damping_factor=0.50)
        table = calc.calculate(monthly_metrics_df, stores_df)

        for idx in table.indices.values():
            for month in idx.raw_indices:
                raw = idx.raw_indices[month]
                expected_damped = round(1.0 + (raw - 1.0) * 0.50, 4)
                assert idx.damped_indices[month] == pytest.approx(expected_damped, abs=0.001)

    def test_exclude_spring_festival(self, stores_df):
        """排除春节月"""
        # 构造包含 2025年1月（春节月）的数据
        rows = []
        for month in range(1, 13):
            rows.append({"store_code": "ST0001", "year_month": f"2025-{month:02d}",
                         "sales_amount": 100_000})
        df = pd.DataFrame(rows)

        calc = SeasonalIndexCalculator()
        table = calc.calculate(df, stores_df)

        # 品牌A华东应该有数据（排除了1月春节月后还有11个月）
        key = ("品牌A", "华东")
        if key in table.indices:
            idx = table.indices[key]
            # 1月不应该有季节指数（被排除了）
            assert 1 not in idx.raw_indices

    def test_empty_data(self, stores_df):
        """空数据"""
        calc = SeasonalIndexCalculator()
        table = calc.calculate(pd.DataFrame(), stores_df)
        assert len(table.indices) == 0

    def test_empty_stores(self, monthly_metrics_df):
        """空门店数据"""
        calc = SeasonalIndexCalculator()
        table = calc.calculate(monthly_metrics_df, pd.DataFrame())
        assert len(table.indices) == 0

    def test_indices_sum_approximately_12(self, monthly_metrics_df, stores_df):
        """原始指数之和约等于 12（因为是月均/总均的比值，12个月加起来约12）"""
        calc = SeasonalIndexCalculator()
        table = calc.calculate(monthly_metrics_df, stores_df)

        for idx in table.indices.values():
            if len(idx.raw_indices) == 12:
                total = sum(idx.raw_indices.values())
                assert total == pytest.approx(12.0, abs=0.5)
