"""SQLite 存储后端

适用于本地开发和测试，无需 MySQL 依赖。
"""

from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text

from src.data.storage.backend import StorageBackend


class SQLiteStorage(StorageBackend):
    """SQLite 存储后端

    使用方式：
        storage = SQLiteStorage("data/profit_forecast.db")
        storage.write_stores(stores_df)
        df = storage.read_stores(store_code="ST0001")
    """

    def __init__(self, db_path: str = "data/profit_forecast.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = None
        self._init_tables()

    def _get_engine(self):
        if self._engine is None:
            self._engine = create_engine(f"sqlite:///{self.db_path}")
        return self._engine

    def _init_tables(self):
        """初始化表结构"""
        engine = self._get_engine()

        create_stores = """
        CREATE TABLE IF NOT EXISTS stores (
            store_code TEXT PRIMARY KEY,
            store_name TEXT NOT NULL,
            store_type TEXT DEFAULT 'direct',
            region TEXT,
            province TEXT,
            city TEXT,
            commercial_tier TEXT DEFAULT 'B',
            store_area REAL,
            opening_date TEXT,
            status TEXT DEFAULT 'active',
            staff_count INTEGER,
            is_virtual INTEGER DEFAULT 0,
            is_temporary INTEGER DEFAULT 0,
            planned_closing_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        create_daily_sales = """
        CREATE TABLE IF NOT EXISTS store_daily_sales (
            store_code TEXT NOT NULL,
            sale_date TEXT NOT NULL,
            brand TEXT,
            region TEXT,
            province TEXT,
            managing_city TEXT,
            business_city TEXT,
            shop_category TEXT,
            business_attribute TEXT,
            sales_amount_pp REAL,
            sales_amount REAL,
            settlement_amt REAL,
            gross_profit REAL,
            gross_net_profit REAL,
            operating_expense REAL,
            bmanaging_exp REAL,
            operating_profit REAL,
            store_contribution REAL,
            salary_fee REAL,
            social_fee REAL,
            comprehensive_mall_fee REAL,
            decorate_fee REAL,
            express REAL,
            all_other_fee REAL,
            hq_taxcost REAL,
            additional_taxes REAL,
            server_fee REAL,
            nonoperating_in_out REAL,
            prm_amt REAL,
            order_count INTEGER DEFAULT 0,
            qty_sold INTEGER DEFAULT 0,
            avg_discount REAL DEFAULT 1.0,
            perspective TEXT DEFAULT 'actual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (store_code, sale_date, perspective)
        )
        """

        create_monthly_metrics = """
        CREATE TABLE IF NOT EXISTS store_monthly_metrics (
            store_code TEXT NOT NULL,
            year_month TEXT NOT NULL,
            brand TEXT,
            sales_amount REAL,
            tag_price_amount REAL,
            hq_tax_cost REAL,
            hq_notax_gross_profit REAL,
            operating_expense REAL,
            b_managing_expense REAL,
            hq_notax_operating_profit REAL,
            salary_fee REAL,
            social_fee REAL,
            gross_margin REAL,
            operating_margin REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (store_code, year_month)
        )
        """

        create_cost_structure = """
        CREATE TABLE IF NOT EXISTS cost_structure (
            store_code TEXT NOT NULL,
            year_month TEXT NOT NULL,
            procurement_cost REAL,
            labor_cost REAL,
            rent_cost REAL,
            logistics_cost REAL,
            marketing_cost REAL,
            commission_cost REAL,
            other_cost REAL,
            total_cost REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (store_code, year_month)
        )
        """

        with engine.begin() as conn:
            conn.execute(text(create_stores))
            conn.execute(text(create_daily_sales))
            conn.execute(text(create_monthly_metrics))
            conn.execute(text(create_cost_structure))

        logger.info(f"[SQLite] 数据库初始化完成: {self.db_path}")

    def _upsert(self, table: str, df: pd.DataFrame, key_columns: list[str]) -> int:
        """通用 upsert 操作"""
        if df.empty:
            logger.warning(f"[SQLite] {table}: 数据为空，跳过")
            return 0

        engine = self._get_engine()
        columns = list(df.columns)

        # SQLite 使用 INSERT OR REPLACE
        placeholders = ", ".join([f":{c}" for c in columns])
        col_str = ", ".join(columns)

        sql = f"INSERT OR REPLACE INTO {table} ({col_str}) VALUES ({placeholders})"

        records = df.where(pd.notnull(df), None).to_dict("records")

        batch_size = 500
        total = 0
        with engine.begin() as conn:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                conn.execute(text(sql), batch)
                total += len(batch)

        logger.info(f"[SQLite] {table}: upsert {total} 条")
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
