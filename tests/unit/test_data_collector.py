"""数据采集模块单元测试"""

import pandas as pd
import pytest
from src.data.collectors.factory import create_collector
from src.data.validators.quality_checker import run_quality_check


class TestMockCollector:
    """Mock 采集器测试"""

    @pytest.mark.asyncio
    async def test_fetch_stores(self, mock_collector):
        """测试采集门店数据"""
        df = await mock_collector.fetch_stores()
        assert not df.empty
        assert "store_code" in df.columns
        assert "store_name" in df.columns
        assert len(df) > 0

    @pytest.mark.asyncio
    async def test_fetch_daily_sales(self, mock_collector):
        """测试采集日销数据"""
        df = await mock_collector.fetch_daily_sales()
        assert not df.empty
        assert "store_code" in df.columns
        assert "sale_date" in df.columns
        assert "sales_amount" in df.columns
        assert (df["sales_amount"] >= 0).all()

    @pytest.mark.asyncio
    async def test_fetch_monthly_metrics(self, mock_collector):
        """测试采集月度指标"""
        df = await mock_collector.fetch_monthly_metrics()
        assert not df.empty
        assert "store_code" in df.columns
        assert "year_month" in df.columns

    @pytest.mark.asyncio
    async def test_fetch_targets(self, mock_collector):
        """测试采集目标数据"""
        df = await mock_collector.fetch_targets()
        assert not df.empty
        assert "store_code" in df.columns
        assert "sales_target" in df.columns

    @pytest.mark.asyncio
    async def test_fetch_staff(self, mock_collector):
        """测试采集人员数据"""
        df = await mock_collector.fetch_staff()
        assert not df.empty
        assert "store_code" in df.columns

    @pytest.mark.asyncio
    async def test_fetch_cost_structure(self, mock_collector):
        """测试采集成本结构"""
        df = await mock_collector.fetch_cost_structure()
        assert not df.empty
        assert "store_code" in df.columns


class TestCollectorFactory:
    """采集器工厂测试"""

    def test_create_mock_collector(self):
        """测试创建 Mock 采集器"""
        collector = create_collector("mock")
        assert collector is not None

    def test_create_default_collector(self):
        """测试创建默认采集器"""
        collector = create_collector()
        assert collector is not None


class TestQualityChecker:
    """数据质量检查测试"""

    @pytest.mark.asyncio
    async def test_quality_check_stores(self, stores_df):
        """测试门店数据质量检查"""
        result = run_quality_check(
            stores_df, name="测试门店",
            critical_cols=["store_code", "store_name"],
            duplicate_subset=["store_code"],
        )
        assert result.is_clean
        assert result.total_rows == len(stores_df)

    @pytest.mark.asyncio
    async def test_quality_check_sales(self, daily_sales_df):
        """测试日销数据质量检查"""
        result = run_quality_check(
            daily_sales_df, name="测试日销",
            critical_cols=["store_code", "sale_date", "sales_amount"],
        )
        assert result.is_clean

    def test_quality_check_empty_df(self):
        """测试空 DataFrame 质量检查"""
        df = pd.DataFrame()
        result = run_quality_check(df, name="空数据", critical_cols=["store_code"])
        assert result.total_rows == 0
        assert result.is_clean  # 空数据没有空值和重复，质量检查通过
