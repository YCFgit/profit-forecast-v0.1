"""Task 4.1: ProfitCalculator.calculate_from_sales 单元测试

测试从统一销售宽表（SalesDataCollector.collect_unified_sales 输出）计算利润。
"""

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
