"""存储后端单元测试

测试 SQLite 后端的读写功能。
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.data.storage import SQLiteStorage, CSVStorage, create_storage


@pytest.fixture
def stores_df():
    """测试门店数据"""
    return pd.DataFrame({
        "store_code": ["ST0001", "ST0002", "ST0003"],
        "store_name": ["上海旗舰店", "北京店", "广州店"],
        "store_type": ["direct", "direct", "direct"],
        "region": ["华东", "华北", "华南"],
        "commercial_tier": ["A", "B", "C"],
        "store_area": [300.0, 200.0, 150.0],
        "status": ["active", "active", "active"],
    })


@pytest.fixture
def daily_sales_df():
    """测试日销售数据"""
    return pd.DataFrame({
        "store_code": ["ST0001", "ST0001", "ST0002"],
        "sale_date": ["2025-01-01", "2025-01-02", "2025-01-01"],
        "sales_amount": [50000.0, 55000.0, 30000.0],
        "gross_profit": [25000.0, 28000.0, 15000.0],
        "operating_profit": [6000.0, 7800.0, 2500.0],
        "perspective": ["actual", "actual", "actual"],
    })


@pytest.fixture
def monthly_metrics_df():
    """测试月度指标数据"""
    return pd.DataFrame({
        "store_code": ["ST0001", "ST0002"],
        "year_month": ["2025-01", "2025-01"],
        "sales_amount": [1500000.0, 900000.0],
        "gross_margin": [0.50, 0.45],
        "operating_margin": [0.12, 0.08],
    })


class TestSQLiteStorage:
    """SQLite 存储后端测试"""

    def test_write_and_read_stores(self, tmp_path, stores_df):
        """测试写入和读取门店数据"""
        db_path = str(tmp_path / "test.db")
        storage = SQLiteStorage(db_path)

        # 写入
        count = storage.write_stores(stores_df)
        assert count == 3

        # 读取全部
        result = storage.read_stores()
        assert len(result) == 3
        assert list(result["store_code"]) == ["ST0001", "ST0002", "ST0003"]

        # 按门店读取
        result = storage.read_stores(store_code="ST0001")
        assert len(result) == 1
        assert result.iloc[0]["store_name"] == "上海旗舰店"

    def test_write_and_read_daily_sales(self, tmp_path, daily_sales_df):
        """测试写入和读取日销售数据"""
        db_path = str(tmp_path / "test.db")
        storage = SQLiteStorage(db_path)

        # 写入
        count = storage.write_daily_sales(daily_sales_df)
        assert count == 3

        # 读取全部
        result = storage.read_daily_sales()
        assert len(result) == 3

        # 按门店读取
        result = storage.read_daily_sales(store_code="ST0001")
        assert len(result) == 2

        # 按日期范围读取
        result = storage.read_daily_sales(date_range=("2025-01-01", "2025-01-01"))
        assert len(result) == 2

    def test_write_and_read_monthly_metrics(self, tmp_path, monthly_metrics_df):
        """测试写入和读取月度指标"""
        db_path = str(tmp_path / "test.db")
        storage = SQLiteStorage(db_path)

        # 写入
        count = storage.write_monthly_metrics(monthly_metrics_df)
        assert count == 2

        # 读取全部
        result = storage.read_monthly_metrics()
        assert len(result) == 2

        # 按月份读取
        result = storage.read_monthly_metrics(year_month="2025-01")
        assert len(result) == 2

    def test_upsert_updates_existing(self, tmp_path, stores_df):
        """测试 upsert 更新已有记录"""
        db_path = str(tmp_path / "test.db")
        storage = SQLiteStorage(db_path)

        # 首次写入
        storage.write_stores(stores_df)

        # 更新一条记录
        updated_df = pd.DataFrame({
            "store_code": ["ST0001"],
            "store_name": ["上海旗舰店（已更新）"],
            "store_type": ["direct"],
            "region": ["华东"],
            "commercial_tier": ["A"],
            "store_area": [350.0],
            "status": ["active"],
        })
        storage.write_stores(updated_df)

        # 验证更新
        result = storage.read_stores(store_code="ST0001")
        assert result.iloc[0]["store_name"] == "上海旗舰店（已更新）"
        assert result.iloc[0]["store_area"] == 350.0

        # 其他记录不受影响
        result = storage.read_stores(store_code="ST0002")
        assert result.iloc[0]["store_name"] == "北京店"

    def test_empty_dataframe(self, tmp_path):
        """测试空 DataFrame 写入"""
        db_path = str(tmp_path / "test.db")
        storage = SQLiteStorage(db_path)

        empty_df = pd.DataFrame(columns=["store_code", "store_name"])
        count = storage.write_stores(empty_df)
        assert count == 0


class TestCSVStorage:
    """CSV 存储后端测试"""

    def test_write_and_read_stores(self, tmp_path, stores_df):
        """测试写入和读取门店数据"""
        output_dir = str(tmp_path / "output")
        storage = CSVStorage(output_dir)

        # 写入
        count = storage.write_stores(stores_df)
        assert count == 3

        # 读取
        result = storage.read_stores()
        assert len(result) == 3

        # 按门店读取
        result = storage.read_stores(store_code="ST0001")
        assert len(result) == 1

    def test_write_and_read_daily_sales(self, tmp_path, daily_sales_df):
        """测试写入和读取日销售数据"""
        output_dir = str(tmp_path / "output")
        storage = CSVStorage(output_dir)

        # 写入
        count = storage.write_daily_sales(daily_sales_df)
        assert count == 3

        # 读取
        result = storage.read_daily_sales()
        assert len(result) == 3

        # 按日期范围读取
        result = storage.read_daily_sales(date_range=("2025-01-01", "2025-01-01"))
        assert len(result) == 2


class TestStorageFactory:
    """存储工厂测试"""

    def test_create_sqlite_storage(self, tmp_path):
        """测试创建 SQLite 存储"""
        db_path = str(tmp_path / "test.db")
        storage = create_storage("sqlite", db_path=db_path)
        assert isinstance(storage, SQLiteStorage)

    def test_create_csv_storage(self, tmp_path):
        """测试创建 CSV 存储"""
        output_dir = str(tmp_path / "output")
        storage = create_storage("csv", output_dir=output_dir)
        assert isinstance(storage, CSVStorage)

    def test_default_backend(self, monkeypatch):
        """测试默认后端"""
        monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
        monkeypatch.setenv("SQLITE_DB_PATH", ":memory:")
        storage = create_storage()
        assert isinstance(storage, SQLiteStorage)

    def test_invalid_backend(self):
        """测试无效后端"""
        with pytest.raises(ValueError, match="不支持的存储后端"):
            create_storage("invalid_backend")
