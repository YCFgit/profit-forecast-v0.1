"""ETL Pipeline 集成测试

用 Mock 数据模拟完整 ETL 流程：
SalesDataCollector → ETLPipeline 模拟 → CSVWriter → 验证输出
"""

import os
import tempfile

import pandas as pd
import pytest

from src.data.collectors.sales_collector import SalesDataCollector
from src.data.etl.writer import CSVWriter
from src.data.etl.pipeline import ETLResult


@pytest.fixture
def collector():
    return SalesDataCollector(adapter="mock")


@pytest.fixture
def loss_df(collector):
    """Mock 损益数据"""
    return collector.collect_store_loss()


@pytest.fixture
def pos_df(collector):
    """Mock POS 数据"""
    return collector.collect_pos_orders()


@pytest.fixture
def unified_df(collector):
    """Mock 统一宽表"""
    return collector.collect_unified_sales()


@pytest.fixture
def tmp_output(tmp_path):
    return str(tmp_path / "etl_output")


class TestETLPipelineIntegration:
    """ETL Pipeline 集成测试"""

    def test_full_csv_output(self, loss_df, tmp_output):
        """完整 CSV 输出流程"""
        writer = CSVWriter(tmp_output)
        path = writer.write_daily_sales(loss_df)

        assert os.path.exists(path)
        loaded = pd.read_csv(path)
        assert len(loaded) == len(loss_df)
        assert "store_no" in loaded.columns
        assert "d1_pf_total_sal_amt" in loaded.columns

    def test_unified_sales_output(self, unified_df, tmp_output):
        """统一宽表 CSV 输出"""
        writer = CSVWriter(tmp_output)
        path = writer.write_unified_sales(unified_df)

        assert os.path.exists(path)
        loaded = pd.read_csv(path)
        assert len(loaded) > 0
        assert "store_no" in loaded.columns
        assert "revenue" in loaded.columns or "sales_amount" in loaded.columns

    def test_multiple_files(self, loss_df, pos_df, tmp_output):
        """多文件输出"""
        writer = CSVWriter(tmp_output)
        writer.write_daily_sales(loss_df)
        writer.write(pos_df, "pos_orders.csv")

        files = os.listdir(tmp_output)
        assert "daily_sales.csv" in files
        assert "pos_orders.csv" in files

    def test_etl_result_success(self):
        """ETLResult 成功状态"""
        result = ETLResult(stores_count=20, loss_rows=1800, pos_rows=30000)
        assert result.success is True
        assert result.errors == []

    def test_etl_result_failure(self):
        """ETLResult 失败状态"""
        result = ETLResult(stores_count=0, errors=["连接失败"])
        assert result.success is False

    def test_etl_result_partial(self):
        """ETLResult 部分成功（有门店但有错误）"""
        result = ETLResult(stores_count=20, errors=["POS 数据加载超时"])
        assert result.success is False  # 有错误就算失败

    def test_data_roundtrip(self, loss_df, tmp_output):
        """写入再读出，数据一致"""
        writer = CSVWriter(tmp_output)
        path = writer.write_daily_sales(loss_df)
        loaded = pd.read_csv(path)

        assert loaded.shape == loss_df.shape
        assert list(loaded.columns) == list(loss_df.columns)
        # 数值列精度
        assert loaded["d1_pf_total_sal_amt"].sum() == pytest.approx(
            loss_df["d1_pf_total_sal_amt"].sum(), rel=1e-6
        )

    def test_pos_agg_consistency(self, pos_df):
        """POS 聚合数据一致性（数据已在 SQL/mock 层聚合）"""
        if pos_df.empty:
            pytest.skip("POS 数据为空")

        # POS 数据已经是 store×date 聚合级别
        assert "store_no" in pos_df.columns
        assert "base_date" in pos_df.columns
        assert "order_count" in pos_df.columns
        assert "qty_sold" in pos_df.columns
        assert "avg_discount" in pos_df.columns

        assert len(pos_df) > 0
        assert pos_df["order_count"].min() >= 1
        assert pos_df["qty_sold"].min() >= 0

    def test_perspective_consistency(self, loss_df):
        """两种口径的数据量一致"""
        # Mock 数据的 d1_pf_ 和 d2_ 应有相同行数
        d1_notnull = loss_df["d1_pf_total_sal_amt"].notna().sum()
        d2_notnull = loss_df["d2_total_sal_amt"].notna().sum()
        assert d1_notnull == d2_notnull
