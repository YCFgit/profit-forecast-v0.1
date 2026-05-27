"""存储后端工厂

根据配置创建不同的存储后端实例。
"""

import os

from loguru import logger

from src.data.storage.backend import StorageBackend
from src.data.storage.csv_storage import CSVStorage
from src.data.storage.mysql_storage import MySQLStorage
from src.data.storage.sqlite_storage import SQLiteStorage


def create_storage(backend: str | None = None, **kwargs) -> StorageBackend:
    """创建存储后端实例

    Args:
        backend: 后端类型 ("mysql", "sqlite", "csv")，默认从环境变量读取
        **kwargs: 传递给具体后端的参数

    Returns:
        StorageBackend 实例

    Examples:
        # 使用环境变量配置
        storage = create_storage()

        # 显式指定后端
        storage = create_storage("sqlite", db_path="data/test.db")
        storage = create_storage("csv", output_dir="data/output")
        storage = create_storage("mysql")
    """
    if backend is None:
        backend = os.getenv("STORAGE_BACKEND", "sqlite").lower()

    if backend == "mysql":
        logger.info("[工厂] 创建 MySQL 存储后端")
        return MySQLStorage(**kwargs)
    elif backend == "sqlite":
        db_path = kwargs.get("db_path", os.getenv("SQLITE_DB_PATH", "data/profit_forecast.db"))
        logger.info(f"[工厂] 创建 SQLite 存储后端: {db_path}")
        return SQLiteStorage(db_path=db_path, **{k: v for k, v in kwargs.items() if k != "db_path"})
    elif backend == "csv":
        output_dir = kwargs.get("output_dir", os.getenv("CSV_OUTPUT_DIR", "data/output"))
        logger.info(f"[工厂] 创建 CSV 存储后端: {output_dir}")
        return CSVStorage(output_dir=output_dir, **{k: v for k, v in kwargs.items() if k != "output_dir"})
    else:
        raise ValueError(f"不支持的存储后端: {backend}，可选: mysql, sqlite, csv")
