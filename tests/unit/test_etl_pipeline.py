"""ETL Pipeline 单元测试

测试 CSVWriter、MySQLWriter 逻辑（不依赖真实数据库连接）。
"""

import os
import tempfile

import pandas as pd
import pytest

from src.data.etl.writer import CSVWriter
from src.data.etl.pipeline import ETLResult


@pytest.fixture
def sample_stores_df():
    return pd.DataFrame([
        {"store_code": "ST0001", "store_name": "测试店1", "brand": "品牌A", "region": "华东"},
        {"store_code": "ST0002", "store_name": "测试店2", "brand": "品牌B", "region": "华南"},
    ])


@pytest.fixture
def sample_loss_df():
    return pd.DataFrame([
        {
            "store_no": "ST0001", "base_date": "2026-01-01", "brand": "品牌A",
            "region": "华东", "sales_amount": 100000.0, "gross_profit": 40000.0,
            "operating_expense": 15000.0, "perspective": "actual",
        },
        {
            "store_no": "ST0001", "base_date": "2026-01-02", "brand": "品牌A",
            "region": "华东", "sales_amount": 95000.0, "gross_profit": 38000.0,
            "operating_expense": 14500.0, "perspective": "actual",
        },
    ])


@pytest.fixture
def tmp_output_dir(tmp_path):
    return str(tmp_path / "etl_output")


# ============================================================
# CSVWriter
# ============================================================

class TestCSVWriter:
    def test_write_stores(self, sample_stores_df, tmp_output_dir):
        writer = CSVWriter(tmp_output_dir)
        path = writer.write_stores(sample_stores_df)

        assert path != ""
        assert os.path.exists(path)

        loaded = pd.read_csv(path)
        assert len(loaded) == 2
        assert "store_code" in loaded.columns

    def test_write_empty_df(self, tmp_output_dir):
        writer = CSVWriter(tmp_output_dir)
        path = writer.write(pd.DataFrame(), "empty.csv")

        assert path == ""
        assert not os.path.exists(os.path.join(tmp_output_dir, "empty.csv"))

    def test_write_daily_sales(self, sample_loss_df, tmp_output_dir):
        writer = CSVWriter(tmp_output_dir)
        path = writer.write_daily_sales(sample_loss_df)

        assert path != ""
        loaded = pd.read_csv(path)
        assert len(loaded) == 2
        assert "sales_amount" in loaded.columns

    def test_output_dir_created(self, tmp_output_dir):
        nested = os.path.join(tmp_output_dir, "sub", "dir")
        writer = CSVWriter(nested)
        assert os.path.isdir(nested)


# ============================================================
# ETLResult
# ============================================================

class TestETLResult:
    def test_success(self):
        result = ETLResult(stores_count=10, loss_rows=100)
        assert result.success is True

    def test_failure_with_errors(self):
        result = ETLResult(stores_count=10, errors=["some error"])
        assert result.success is False

    def test_failure_no_stores(self):
        result = ETLResult(stores_count=0)
        assert result.success is False

    def test_default_values(self):
        result = ETLResult()
        assert result.stores_count == 0
        assert result.loss_rows == 0
        assert result.pos_rows == 0
        assert result.output_files == []
        assert result.errors == []
