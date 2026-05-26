"""数据写入器

将加工后的数据写入本地 MySQL 或 CSV 文件。
"""

import os
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text

from src.core.config import get_settings


class MySQLWriter:
    """将 DataFrame 写入本地 MySQL（upsert 模式）

    使用方式：
        writer = MySQLWriter()
        writer.write_stores(stores_df)
        writer.write_daily_sales(sales_df)
    """

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            settings = get_settings()
            url = (
                f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
                f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}"
            )
            self._engine = create_engine(url, pool_pre_ping=True)
        return self._engine

    def _upsert(self, table: str, df: pd.DataFrame, key_columns: list[str]):
        """通用 upsert：INSERT ... ON DUPLICATE KEY UPDATE"""
        if df.empty:
            logger.warning(f"[MySQLWriter] {table}: 数据为空，跳过")
            return 0

        engine = self._get_engine()
        columns = list(df.columns)
        placeholders = ", ".join([f":{c}" for c in columns])
        col_str = ", ".join(columns)

        update_parts = [f"{c} = VALUES({c})" for c in columns if c not in key_columns]
        update_str = ", ".join(update_parts) if update_parts else f"{columns[0]} = VALUES({columns[0]})"

        sql = f"""
        INSERT INTO {table} ({col_str})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_str}
        """

        records = df.where(pd.notnull(df), None).to_dict("records")

        batch_size = 500
        total = 0
        with engine.begin() as conn:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                conn.execute(text(sql), batch)
                total += len(batch)

        logger.info(f"[MySQLWriter] {table}: upsert {total} 条")
        return total

    def write_stores(self, df: pd.DataFrame) -> int:
        """写入门店主数据"""
        return self._upsert("stores", df, ["store_code"])

    def write_daily_sales(self, df: pd.DataFrame) -> int:
        """写入日销售/损益数据"""
        return self._upsert("store_daily_sales", df, ["store_code", "sale_date"])

    def write_monthly_metrics(self, df: pd.DataFrame) -> int:
        """写入月度指标"""
        return self._upsert("store_monthly_metrics", df, ["store_code", "year_month"])

    def write_cost_structure(self, df: pd.DataFrame) -> int:
        """写入成本结构"""
        return self._upsert("cost_structure", df, ["store_code", "year_month"])


class CSVWriter:
    """将 DataFrame 写入 CSV 文件

    使用方式：
        writer = CSVWriter("data/etl_output")
        writer.write(stores_df, "stores.csv")
    """

    def __init__(self, output_dir: str = "data/etl_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, df: pd.DataFrame, filename: str) -> str:
        """写入 CSV 文件"""
        if df.empty:
            logger.warning(f"[CSVWriter] {filename}: 数据为空，跳过")
            return ""

        filepath = self.output_dir / filename
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        logger.info(f"[CSVWriter] {filename}: {len(df)} 行 → {filepath}")
        return str(filepath)

    def write_stores(self, df: pd.DataFrame) -> str:
        return self.write(df, "stores.csv")

    def write_daily_sales(self, df: pd.DataFrame) -> str:
        return self.write(df, "daily_sales.csv")

    def write_monthly_metrics(self, df: pd.DataFrame) -> str:
        return self.write(df, "monthly_metrics.csv")

    def write_unified_sales(self, df: pd.DataFrame) -> str:
        return self.write(df, "unified_sales.csv")
