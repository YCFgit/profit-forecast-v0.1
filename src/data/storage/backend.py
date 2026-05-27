"""存储后端抽象层

定义统一的存储接口，支持多种后端实现：
- MySQLStorage: 生产环境 MySQL
- SQLiteStorage: 本地开发/测试 SQLite
- CSVStorage: 文件输出
"""

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
from loguru import logger


class StorageBackend(ABC):
    """存储后端抽象基类"""

    @abstractmethod
    def write_stores(self, df: pd.DataFrame) -> int:
        """写入门店主数据

        Args:
            df: 门店数据 DataFrame

        Returns:
            写入行数
        """
        ...

    @abstractmethod
    def write_daily_sales(self, df: pd.DataFrame) -> int:
        """写入日销售/损益数据

        Args:
            df: 日销售数据 DataFrame

        Returns:
            写入行数
        """
        ...

    @abstractmethod
    def write_monthly_metrics(self, df: pd.DataFrame) -> int:
        """写入月度指标

        Args:
            df: 月度指标 DataFrame

        Returns:
            写入行数
        """
        ...

    @abstractmethod
    def write_cost_structure(self, df: pd.DataFrame) -> int:
        """写入成本结构

        Args:
            df: 成本结构 DataFrame

        Returns:
            写入行数
        """
        ...

    @abstractmethod
    def read_stores(self, store_code: str | None = None) -> pd.DataFrame:
        """读取门店数据

        Args:
            store_code: 可选，指定门店编码

        Returns:
            门店数据 DataFrame
        """
        ...

    @abstractmethod
    def read_daily_sales(
        self,
        store_code: str | None = None,
        date_range: tuple[str, str] | None = None,
    ) -> pd.DataFrame:
        """读取日销售数据

        Args:
            store_code: 可选，指定门店编码
            date_range: 可选，日期范围 (start, end)

        Returns:
            日销售数据 DataFrame
        """
        ...

    @abstractmethod
    def read_monthly_metrics(
        self,
        store_code: str | None = None,
        year_month: str | None = None,
    ) -> pd.DataFrame:
        """读取月度指标

        Args:
            store_code: 可选，指定门店编码
            year_month: 可选，指定月份 (YYYY-MM)

        Returns:
            月度指标 DataFrame
        """
        ...
