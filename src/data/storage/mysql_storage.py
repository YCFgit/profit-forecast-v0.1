"""MySQL 存储后端

生产环境使用，支持 upsert 操作。
"""

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text

from src.core.config import get_settings
from src.data.storage.backend import StorageBackend


class MySQLStorage(StorageBackend):
    """MySQL 存储后端

    使用方式：
        storage = MySQLStorage()
        storage.write_stores(stores_df)
        df = storage.read_stores(store_code="ST0001")
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

    def _upsert(self, table: str, df: pd.DataFrame, key_columns: list[str]) -> int:
        """通用 upsert：INSERT ... ON DUPLICATE KEY UPDATE"""
        if df.empty:
            logger.warning(f"[MySQL] {table}: 数据为空，跳过")
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

        logger.info(f"[MySQL] {table}: upsert {total} 条")
        return total

    def write_stores(self, df: pd.DataFrame) -> int:
        """写入门店主数据"""
        return self._upsert("stores", df, ["store_code"])

    def write_daily_sales(self, df: pd.DataFrame) -> int:
        """写入日销售/损益数据"""
        return self._upsert("store_daily_sales", df, ["store_code", "sale_date", "perspective"])

    def write_monthly_metrics(self, df: pd.DataFrame) -> int:
        """写入月度指标"""
        return self._upsert("store_monthly_metrics", df, ["store_code", "year_month"])

    def write_cost_structure(self, df: pd.DataFrame) -> int:
        """写入成本结构"""
        return self._upsert("cost_structure", df, ["store_code", "year_month"])

    def read_stores(self, store_code: str | None = None) -> pd.DataFrame:
        """读取门店数据"""
        engine = self._get_engine()
        if store_code:
            sql = "SELECT * FROM stores WHERE store_code = :store_code"
            return pd.read_sql(text(sql), engine, params={"store_code": store_code})
        else:
            sql = "SELECT * FROM stores ORDER BY store_code"
            return pd.read_sql(text(sql), engine)

    def read_daily_sales(
        self,
        store_code: str | None = None,
        date_range: tuple[str, str] | None = None,
    ) -> pd.DataFrame:
        """读取日销售数据"""
        engine = self._get_engine()
        conditions = ["1=1"]
        params = {}

        if store_code:
            conditions.append("store_code = :store_code")
            params["store_code"] = store_code
        if date_range:
            conditions.append("sale_date >= :date_start AND sale_date <= :date_end")
            params["date_start"] = date_range[0]
            params["date_end"] = date_range[1]

        where_str = " AND ".join(conditions)
        sql = f"SELECT * FROM store_daily_sales WHERE {where_str} ORDER BY store_code, sale_date"
        return pd.read_sql(text(sql), engine, params=params)

    def read_monthly_metrics(
        self,
        store_code: str | None = None,
        year_month: str | None = None,
    ) -> pd.DataFrame:
        """读取月度指标"""
        engine = self._get_engine()
        conditions = ["1=1"]
        params = {}

        if store_code:
            conditions.append("store_code = :store_code")
            params["store_code"] = store_code
        if year_month:
            conditions.append("year_month = :year_month")
            params["year_month"] = year_month

        where_str = " AND ".join(conditions)
        sql = f"SELECT * FROM store_monthly_metrics WHERE {where_str} ORDER BY store_code, year_month"
        return pd.read_sql(text(sql), engine, params=params)
