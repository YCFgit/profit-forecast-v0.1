"""存储后端模块

提供统一的存储接口，支持多种后端实现。

使用方式：
    from src.data.storage import create_storage

    # 自动从环境变量读取配置
    storage = create_storage()

    # 显式指定后端
    storage = create_storage("sqlite", db_path="data/test.db")

    # 写入数据
    storage.write_stores(stores_df)
    storage.write_daily_sales(sales_df)

    # 读取数据
    stores = storage.read_stores(store_code="ST0001")
    sales = storage.read_daily_sales(date_range=("2025-01-01", "2025-03-31"))
"""

from src.data.storage.backend import StorageBackend
from src.data.storage.csv_storage import CSVStorage
from src.data.storage.factory import create_storage
from src.data.storage.mysql_storage import MySQLStorage
from src.data.storage.sqlite_storage import SQLiteStorage

__all__ = [
    "StorageBackend",
    "MySQLStorage",
    "SQLiteStorage",
    "CSVStorage",
    "create_storage",
]
