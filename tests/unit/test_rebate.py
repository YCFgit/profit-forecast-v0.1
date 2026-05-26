"""返利口径处理单元测试"""

import pandas as pd
import pytest

from src.data.etl.rebate import compare_perspectives, summarize_rebate_impact


@pytest.fixture
def actual_df():
    """业绩口径数据"""
    return pd.DataFrame([
        {"store_no": "ST0001", "base_date": "2026-01-01", "sales_amount": 100000.0,
         "gross_profit": 40000.0, "operating_profit": 15000.0},
        {"store_no": "ST0001", "base_date": "2026-01-02", "sales_amount": 95000.0,
         "gross_profit": 38000.0, "operating_profit": 14000.0},
        {"store_no": "ST0002", "base_date": "2026-01-01", "sales_amount": 80000.0,
         "gross_profit": 32000.0, "operating_profit": 12000.0},
    ])


@pytest.fixture
def rebate_df():
    """返利口径数据（略低于业绩口径）"""
    return pd.DataFrame([
        {"store_no": "ST0001", "base_date": "2026-01-01", "sales_amount": 96000.0,
         "gross_profit": 37000.0, "operating_profit": 13500.0},
        {"store_no": "ST0001", "base_date": "2026-01-02", "sales_amount": 92000.0,
         "gross_profit": 36000.0, "operating_profit": 13000.0},
        {"store_no": "ST0002", "base_date": "2026-01-01", "sales_amount": 76000.0,
         "gross_profit": 30000.0, "operating_profit": 11000.0},
    ])


# ============================================================
# compare_perspectives
# ============================================================

class TestComparePerspectives:
    def test_basic_comparison(self, actual_df, rebate_df):
        """基本对比"""
        result = compare_perspectives(actual_df, rebate_df)

        assert len(result) == 3
        assert "sales_diff" in result.columns
        assert "gross_profit_diff" in result.columns
        assert "operating_profit_diff" in result.columns
        assert "sales_diff_pct" in result.columns

    def test_sales_diff_sign(self, actual_df, rebate_df):
        """返利 < 业绩 → 差异为负"""
        result = compare_perspectives(actual_df, rebate_df)

        # ST0001 01-01: 96000 - 100000 = -4000
        row = result[(result["store_no"] == "ST0001") & (result["base_date"] == "2026-01-01")]
        assert row["sales_diff"].values[0] == pytest.approx(-4000.0)

    def test_positive_diff(self, actual_df):
        """返利 > 业绩 → 差异为正"""
        rebate_higher = actual_df.copy()
        rebate_higher["sales_amount"] = rebate_higher["sales_amount"] * 1.05
        rebate_higher["gross_profit"] = rebate_higher["gross_profit"] * 1.05
        rebate_higher["operating_profit"] = rebate_higher["operating_profit"] * 1.05

        result = compare_perspectives(actual_df, rebate_higher)
        assert (result["sales_diff"] > 0).all()

    def test_empty_actual(self, rebate_df):
        """业绩数据为空"""
        result = compare_perspectives(pd.DataFrame(), rebate_df)
        assert result.empty

    def test_empty_rebate(self, actual_df):
        """返利数据为空"""
        result = compare_perspectives(actual_df, pd.DataFrame())
        assert result.empty

    def test_mismatched_stores(self):
        """不同门店的数据"""
        actual = pd.DataFrame([
            {"store_no": "ST0001", "base_date": "2026-01-01", "sales_amount": 100.0,
             "gross_profit": 40.0, "operating_profit": 15.0},
        ])
        rebate = pd.DataFrame([
            {"store_no": "ST9999", "base_date": "2026-01-01", "sales_amount": 90.0,
             "gross_profit": 35.0, "operating_profit": 12.0},
        ])
        result = compare_perspectives(actual, rebate)
        assert len(result) == 0  # inner join, no match


# ============================================================
# summarize_rebate_impact
# ============================================================

class TestSummarizeRebateImpact:
    def test_basic_summary(self, actual_df, rebate_df):
        """基本汇总"""
        comparison = compare_perspectives(actual_df, rebate_df)
        summary = summarize_rebate_impact(comparison)

        assert "total_sales_diff" in summary
        assert "total_gp_diff" in summary
        assert "total_op_diff" in summary
        assert "avg_sales_diff_pct" in summary
        assert "store_count" in summary
        assert "stores_positive" in summary
        assert "stores_negative" in summary

    def test_store_count(self, actual_df, rebate_df):
        """门店数正确"""
        comparison = compare_perspectives(actual_df, rebate_df)
        summary = summarize_rebate_impact(comparison)
        assert summary["store_count"] == 2

    def test_negative_impact(self, actual_df, rebate_df):
        """返利低于业绩 → 总差异为负"""
        comparison = compare_perspectives(actual_df, rebate_df)
        summary = summarize_rebate_impact(comparison)
        assert summary["total_sales_diff"] < 0
        assert summary["stores_negative"] == 2
        assert summary["stores_positive"] == 0

    def test_empty_comparison(self):
        """空对比结果"""
        summary = summarize_rebate_impact(pd.DataFrame())
        assert summary == {}

    def test_mixed_impact(self):
        """部分门店正向、部分负向"""
        actual = pd.DataFrame([
            {"store_no": "ST0001", "base_date": "2026-01-01", "sales_amount": 100.0,
             "gross_profit": 40.0, "operating_profit": 15.0},
            {"store_no": "ST0002", "base_date": "2026-01-01", "sales_amount": 100.0,
             "gross_profit": 40.0, "operating_profit": 15.0},
        ])
        rebate = pd.DataFrame([
            {"store_no": "ST0001", "base_date": "2026-01-01", "sales_amount": 90.0,
             "gross_profit": 35.0, "operating_profit": 12.0},
            {"store_no": "ST0002", "base_date": "2026-01-01", "sales_amount": 110.0,
             "gross_profit": 45.0, "operating_profit": 18.0},
        ])
        comparison = compare_perspectives(actual, rebate)
        summary = summarize_rebate_impact(comparison)

        assert summary["stores_negative"] == 1
        assert summary["stores_positive"] == 1
