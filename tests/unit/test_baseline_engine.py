"""基线预估引擎单元测试"""

import pandas as pd
import pytest

from src.forecasting.rules.baseline_engine import (
    BaselineEngine,
    BaselineEngineResult,
    StoreEstimateDetail,
)
from src.forecasting.rules.store_classifier import StoreCategory


@pytest.fixture
def stores_df():
    """测试门店数据（覆盖 6 种分类）"""
    return pd.DataFrame([
        {"store_code": "ST0001", "store_name": "大中店A", "brand": "品牌A", "region": "华东",
         "is_virtual": False, "is_temporary": False, "opening_date": "2020-01-01",
         "planned_closing_date": None},
        {"store_code": "ST0002", "store_name": "小店B", "brand": "品牌A", "region": "华东",
         "is_virtual": False, "is_temporary": False, "opening_date": "2020-06-01",
         "planned_closing_date": None},
        {"store_code": "ST0003", "store_name": "新店C", "brand": "品牌B", "region": "华南",
         "is_virtual": False, "is_temporary": False, "opening_date": "2025-06-01",
         "planned_closing_date": None},
        {"store_code": "ST0004", "store_name": "虚拟店D", "brand": "品牌B", "region": "华南",
         "is_virtual": True, "is_temporary": False, "opening_date": "2020-01-01",
         "planned_closing_date": None},
        {"store_code": "ST0005", "store_name": "临时店E", "brand": "品牌C", "region": "华北",
         "is_virtual": False, "is_temporary": True, "opening_date": "2024-01-01",
         "planned_closing_date": None},
        {"store_code": "ST0006", "store_name": "关店F", "brand": "品牌C", "region": "华北",
         "is_virtual": False, "is_temporary": False, "opening_date": "2020-01-01",
         "planned_closing_date": "2026-03-01"},
    ])


@pytest.fixture
def monthly_metrics_df():
    """测试月度指标数据（2024-01 到 2026-04）"""
    rows = []
    for code, base_sales in [
        ("ST0001", 500_000),
        ("ST0002", 15_000),
        ("ST0003", 200_000),
        ("ST0004", 100_000),
        ("ST0005", 80_000),
        ("ST0006", 300_000),
    ]:
        for month_offset in range(28):
            year = 2024 + month_offset // 12
            month = month_offset % 12 + 1
            sales = base_sales * (1 + (month_offset % 3 - 1) * 0.1)
            rows.append({
                "store_code": code,
                "year_month": f"{year}-{month:02d}",
                "sales_amount": sales,
            })
    return pd.DataFrame(rows)


class TestBaselineEngine:
    """基线预估引擎测试"""

    def test_run_basic(self, stores_df, monthly_metrics_df):
        """基本运行"""
        engine = BaselineEngine()
        result = engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics_df,
            target_year=2026,
            target_month=5,
        )

        assert isinstance(result, BaselineEngineResult)
        assert result.store_count == 6
        assert len(result.baselines) == 6

    def test_baselines_format(self, stores_df, monthly_metrics_df):
        """baselines 格式兼容性"""
        engine = BaselineEngine()
        result = engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics_df,
            target_year=2026,
            target_month=5,
        )

        # baselines 必须是 dict[str, float]
        assert isinstance(result.baselines, dict)
        for code, value in result.baselines.items():
            assert isinstance(code, str)
            assert isinstance(value, (int, float))

    def test_model_info_structure(self, stores_df, monthly_metrics_df):
        """model_info 结构"""
        engine = BaselineEngine()
        result = engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics_df,
            target_year=2026,
            target_month=5,
        )

        for code, info in result.model_info.items():
            assert "category" in info
            assert "mechanism" in info
            assert "brand" in info
            assert "region" in info

    def test_category_distribution(self, stores_df, monthly_metrics_df):
        """分类分布"""
        engine = BaselineEngine()
        result = engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics_df,
            target_year=2026,
            target_month=5,
        )

        assert "large_medium" in result.category_summary
        assert "small" in result.category_summary
        assert "new" in result.category_summary
        assert "virtual" in result.category_summary
        assert "temporary" in result.category_summary
        assert "closing" in result.category_summary

    def test_temp_store_no_allocation(self, stores_df, monthly_metrics_df):
        """临时特卖店不参与承压分配"""
        engine = BaselineEngine()
        result = engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics_df,
            target_year=2026,
            target_month=5,
        )

        temp_info = result.model_info.get("ST0005", {})
        assert temp_info.get("participates_allocation") is False

    def test_closing_store_zero_sales(self, stores_df, monthly_metrics_df):
        """已关店门店业绩为 0"""
        engine = BaselineEngine()
        result = engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics_df,
            target_year=2026,
            target_month=5,
        )

        # ST0006 关店日期 2026-03-01，在 2026-05 之前
        assert result.baselines.get("ST0006", 0) == 0.0

    def test_seasonal_table_generated(self, stores_df, monthly_metrics_df):
        """季节指数表生成"""
        engine = BaselineEngine()
        result = engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics_df,
            target_year=2026,
            target_month=5,
        )

        assert result.seasonal_table is not None
        assert len(result.seasonal_table.indices) > 0

    def test_empty_data(self, stores_df):
        """空月度指标"""
        engine = BaselineEngine()
        result = engine.run(
            stores_df=stores_df,
            monthly_metrics_df=pd.DataFrame(),
            target_year=2026,
            target_month=5,
        )

        # 应该能运行，但大部分门店基线为 0
        assert result.store_count == 6

    def test_with_switch_status(self, stores_df, monthly_metrics_df):
        """带开关状态矩阵"""
        switch_df = pd.DataFrame([
            {"store_code": "ST0001", "year_month": "2026-05", "status": "off"},
        ])

        engine = BaselineEngine()
        result = engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics_df,
            switch_status_df=switch_df,
            target_year=2026,
            target_month=5,
        )

        # ST0001 被标记为关店
        st0001_info = result.model_info.get("ST0001", {})
        assert st0001_info.get("category") == "closing"

    def test_spring_festival_month(self, stores_df, monthly_metrics_df):
        """春节月预估"""
        engine = BaselineEngine()
        result = engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics_df,
            target_year=2026,
            target_month=2,  # 2026年2月是春节月
        )

        # 所有非临时/非关店门店应使用春节月预估
        for code, info in result.model_info.items():
            if info.get("category") not in ("temporary", "closing"):
                assert info.get("mechanism") in (
                    "spring_festival_mean", "recent_mean_fallback"
                )
