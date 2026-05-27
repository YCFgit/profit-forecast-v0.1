"""CSV 文件存储后端

适用于数据分析和导出场景。
"""

from pathlib import Path

import pandas as pd
from loguru import logger

from src.data.storage.backend import StorageBackend


class CSVStorage(StorageBackend):
    """CSV 文件存储后端

    使用方式：
        storage = CSVStorage("data/output")
        storage.write_stores(stores_df)
        df = storage.read_stores()
    """

    def __init__(self, output_dir: str = "data/output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _write_csv(self, df: pd.DataFrame, filename: str) -> int:
        """写入 CSV 文件"""
        if df.empty:
            logger.warning(f"[CSV] {filename}: 数据为空，跳过")
            return 0

        filepath = self.output_dir / filename
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        logger.info(f"[CSV] {filename}: {len(df)} 行 → {filepath}")
        return len(df)

    def _read_csv(self, filename: str) -> pd.DataFrame:
        """读取 CSV 文件"""
        filepath = self.output_dir / filename
        if not filepath.exists():
            logger.warning(f"[CSV] 文件不存在: {filepath}")
            return pd.DataFrame()
        return pd.read_csv(filepath)

    def write_stores(self, df: pd.DataFrame) -> int:
        """写入门店主数据"""
        return self._write_csv(df, "stores.csv")

    def write_daily_sales(self, df: pd.DataFrame) -> int:
        """写入日销售/损益数据"""
        return self._write_csv(df, "daily_sales.csv")

    def write_monthly_metrics(self, df: pd.DataFrame) -> int:
        """写入月度指标"""
        return self._write_csv(df, "monthly_metrics.csv")

    def write_cost_structure(self, df: pd.DataFrame) -> int:
        """写入成本结构"""
        return self._write_csv(df, "cost_structure.csv")

    def read_stores(self, store_code: str | None = None) -> pd.DataFrame:
        """读取门店数据"""
        df = self._read_csv("stores.csv")
        if store_code and not df.empty:
            df = df[df["store_code"] == store_code]
        return df

    def read_daily_sales(
        self,
        store_code: str | None = None,
        date_range: tuple[str, str] | None = None,
    ) -> pd.DataFrame:
        """读取日销售数据"""
        df = self._read_csv("daily_sales.csv")
        if df.empty:
            return df

        if store_code:
            df = df[df["store_code"] == store_code]
        if date_range:
            df = df[(df["sale_date"] >= date_range[0]) & (df["sale_date"] <= date_range[1])]
        return df

    def read_monthly_metrics(
        self,
        store_code: str | None = None,
        year_month: str | None = None,
    ) -> pd.DataFrame:
        """读取月度指标"""
        df = self._read_csv("monthly_metrics.csv")
        if df.empty:
            return df

        if store_code:
            df = df[df["store_code"] == store_code]
        if year_month:
            df = df[df["year_month"] == year_month]
        return df
