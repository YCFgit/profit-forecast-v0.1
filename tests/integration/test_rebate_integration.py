"""返利口径集成测试

用 Mock 数据跑完整的返利口径对比流程：
SalesDataCollector → 提取 d1_pf_ / d2_ → compare_perspectives → summarize_rebate_impact
"""

import pandas as pd
import pytest

from src.data.collectors.sales_collector import SalesDataCollector
from src.data.etl.rebate import compare_perspectives, summarize_rebate_impact


@pytest.fixture
def collector():
    return SalesDataCollector(adapter="mock")


@pytest.fixture
def raw_loss_df(collector):
    """原始 Mock 损益数据（含 d1_pf_ 和 d2_ 全部字段）"""
    return collector._mock_store_loss_df


@pytest.fixture
def actual_df(raw_loss_df):
    """业绩口径：从 d1_pf_ 字段提取并重命名"""
    df = raw_loss_df[["store_no", "base_date"]].copy()
    df["sales_amount"] = raw_loss_df["d1_pf_total_sal_amt"]
    df["gross_profit"] = raw_loss_df["d1_pf_hq_notax_gross_profit"]
    df["operating_profit"] = raw_loss_df["d1_pf_hq_notax_operating_profit"]
    return df


@pytest.fixture
def rebate_df(raw_loss_df):
    """返利口径：从 d2_ 字段提取并重命名"""
    df = raw_loss_df[["store_no", "base_date"]].copy()
    df["sales_amount"] = raw_loss_df["d2_total_sal_amt"]
    df["gross_profit"] = raw_loss_df["d2_hq_notax_gross_profit"]
    df["operating_profit"] = raw_loss_df["d2_hq_notax_operating_profit"]
    return df


class TestRebateIntegration:
    """返利口径集成测试"""

    def test_full_compare_flow(self, actual_df, rebate_df):
        """完整对比流程：actual + rebate → compare → summary"""
        comparison = compare_perspectives(actual_df, rebate_df)
        assert not comparison.empty

        summary = summarize_rebate_impact(comparison)
        assert summary["store_count"] > 0
        assert "total_sales_diff" in summary

    def test_rebate_not_equal_actual(self, actual_df, rebate_df):
        """返利口径 ≠ 业绩口径"""
        comparison = compare_perspectives(actual_df, rebate_df)
        # 不应所有记录的差异都为 0
        assert not (comparison["sales_diff"] == 0).all()

    def test_diff_pct_reasonable(self, actual_df, rebate_df):
        """差异率在合理范围内（返利系数 0.93-1.05 → 差异率 ±15%）"""
        comparison = compare_perspectives(actual_df, rebate_df)
        pct = comparison["sales_diff_pct"].dropna()
        assert pct.min() > -0.20
        assert pct.max() < 0.20

    def test_summary_has_positive_and_negative(self, actual_df, rebate_df):
        """应有正向和负向门店（返利系数随机，部分高于、部分低于业绩）"""
        comparison = compare_perspectives(actual_df, rebate_df)
        summary = summarize_rebate_impact(comparison)
        # 20 家门店，返利系数 0.93-1.05，大概率有正有负
        assert summary["stores_positive"] + summary["stores_negative"] == summary["store_count"]

    def test_single_store_compare(self, raw_loss_df):
        """单店对比"""
        store = raw_loss_df[raw_loss_df["store_no"] == "ST0001"]
        actual = pd.DataFrame({
            "store_no": store["store_no"],
            "base_date": store["base_date"],
            "sales_amount": store["d1_pf_total_sal_amt"],
            "gross_profit": store["d1_pf_hq_notax_gross_profit"],
            "operating_profit": store["d1_pf_hq_notax_operating_profit"],
        })
        rebate = pd.DataFrame({
            "store_no": store["store_no"],
            "base_date": store["base_date"],
            "sales_amount": store["d2_total_sal_amt"],
            "gross_profit": store["d2_hq_notax_gross_profit"],
            "operating_profit": store["d2_hq_notax_operating_profit"],
        })
        comparison = compare_perspectives(actual, rebate)
        summary = summarize_rebate_impact(comparison)

        assert summary["store_count"] == 1
        assert len(comparison) == len(store)

    def test_date_range_filter(self, collector, raw_loss_df):
        """按日期范围过滤后对比"""
        df = raw_loss_df
        # 只取 1 月数据
        jan = df[df["base_date"].str.startswith("2025-01")]
        actual = pd.DataFrame({
            "store_no": jan["store_no"],
            "base_date": jan["base_date"],
            "sales_amount": jan["d1_pf_total_sal_amt"],
            "gross_profit": jan["d1_pf_hq_notax_gross_profit"],
            "operating_profit": jan["d1_pf_hq_notax_operating_profit"],
        })
        rebate = pd.DataFrame({
            "store_no": jan["store_no"],
            "base_date": jan["base_date"],
            "sales_amount": jan["d2_total_sal_amt"],
            "gross_profit": jan["d2_hq_notax_gross_profit"],
            "operating_profit": jan["d2_hq_notax_operating_profit"],
        })
        comparison = compare_perspectives(actual, rebate)
        summary = summarize_rebate_impact(comparison)

        assert summary["store_count"] == 20
        # 1月数据量应比全量少
        assert len(comparison) < len(raw_loss_df)
