import pytest
import pandas as pd
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
    """模拟 POS 聚合数据（门店×日期）"""
    return pd.DataFrame({
        "store_no": ["S001", "S001", "S002"],
        "base_date": ["20260101", "20260102", "20260101"],
        "order_count": [15, 18, 10],
        "qty_sold": [25, 30, 15],
        "sales_amount": [2500.0, 3000.0, 800.0],
        "avg_discount": [0.85, 0.90, 0.75],
        "avg_ticket": [166.67, 166.67, 80.0],
        "foot_traffic": [35, 42, 22],
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
    """测试采集 POS 聚合数据返回 DataFrame"""
    collector = SalesDataCollector(adapter="mock")
    collector._mock_pos_df = mock_pos_df

    df = collector.collect_pos_orders(store_no="S001", date_range=("20260101", "20260102"))

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "order_count" in df.columns
    assert "sales_amount" in df.columns


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
