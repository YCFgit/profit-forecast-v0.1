"""MySQL 数据采集器

从本地 MySQL 数据库读取已加载的 CSV 数据，
生成统一销售宽表供下游 Agent 使用。

表结构：
- stores: 门店主数据
- store_monthly_metrics: 月度指标 (store_code, year_month, sales_amount, gross_profit, gross_margin)
- cost_structure: 成本结构 (store_code, year_month, total_cost)
- store_targets: 目标数据 (store_code, target_type, target_month, sales_target)
- store_daily_sales: 日销数据 (store_code, sale_date, sales_amount)
"""

import os
from typing import Optional

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text

from src.core.config import get_settings


class MySQLCollector:
    """从本地 MySQL 读取数据并生成统一销售宽表"""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            settings = get_settings()
            # 从 .env 读取 MySQL 配置
            host = os.getenv("MYSQL_HOST", "localhost")
            port = os.getenv("MYSQL_PORT", "3307")
            user = os.getenv("MYSQL_USER", "root")
            password = os.getenv("MYSQL_PASSWORD", "profit123")
            database = os.getenv("MYSQL_DATABASE", "profit_forecast")
            url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
            self._engine = create_engine(url, pool_pre_ping=True)
        return self._engine

    def _query(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        engine = self._get_engine()
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})

    def collect_stores(self) -> pd.DataFrame:
        """获取门店列表"""
        sql = """SELECT store_code, store_name, store_short_name, brand, store_type,
                        channel_l1, channel_l2, channel_l3,
                        region, sub_region, province, city, city_level,
                        business_attribute, business_category,
                        commercial_tier, store_area, total_area,
                        opening_date, closing_date, actual_open_date,
                        status, is_new_store, cooperation_mode, commercial_circle
                 FROM stores"""
        df = self._query(sql)
        logger.info(f"[MySQL] 门店数据: {len(df)} 条")
        return df

    def collect_monthly_metrics(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
        only_valid_stores: bool = True,
        active_only: bool = False,
    ) -> pd.DataFrame:
        """获取月度指标

        Args:
            only_valid_stores: 只返回在 stores 表中存在的门店数据
            active_only: 只返回营业中(status='active')的门店数据
        """
        conditions = ["1=1"]
        params = {}
        if store_codes:
            placeholders = ", ".join(f":sc{i}" for i in range(len(store_codes)))
            conditions.append(f"m.store_code IN ({placeholders})")
            for i, sc in enumerate(store_codes):
                params[f"sc{i}"] = sc
        if start_month:
            conditions.append("m.`year_month` >= :start_month")
            params["start_month"] = start_month
        if end_month:
            conditions.append("m.`year_month` <= :end_month")
            params["end_month"] = end_month

        join_clause = ""
        if only_valid_stores and not store_codes:
            if active_only:
                join_clause = "INNER JOIN stores s ON m.store_code = s.store_code AND s.status = 'active'"
            else:
                join_clause = "INNER JOIN stores s ON m.store_code = s.store_code"

        where = " AND ".join(conditions)
        sql = f"""
        SELECT m.store_code, m.`year_month`, m.sales_amount, m.gross_profit, m.gross_margin
        FROM store_monthly_metrics m
        {join_clause}
        WHERE {where}
        ORDER BY m.store_code, m.`year_month`
        """
        df = self._query(sql, params)
        logger.info(f"[MySQL] 月度指标: {len(df)} 条, {df['store_code'].nunique() if not df.empty else 0} 家门店")
        return df

    def collect_cost_structure(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
        only_valid_stores: bool = True,
        active_only: bool = False,
    ) -> pd.DataFrame:
        """获取成本结构"""
        conditions = ["1=1"]
        params = {}
        if store_codes:
            placeholders = ", ".join(f":sc{i}" for i in range(len(store_codes)))
            conditions.append(f"c.store_code IN ({placeholders})")
            for i, sc in enumerate(store_codes):
                params[f"sc{i}"] = sc
        if start_month:
            conditions.append("c.`year_month` >= :start_month")
            params["start_month"] = start_month
        if end_month:
            conditions.append("c.`year_month` <= :end_month")
            params["end_month"] = end_month

        join_clause = ""
        if only_valid_stores and not store_codes:
            if active_only:
                join_clause = "INNER JOIN stores s ON c.store_code = s.store_code AND s.status = 'active'"
            else:
                join_clause = "INNER JOIN stores s ON c.store_code = s.store_code"

        where = " AND ".join(conditions)
        sql = f"""
        SELECT c.store_code, c.`year_month`, c.total_cost
        FROM cost_structure c
        {join_clause}
        WHERE {where}
        ORDER BY c.store_code, c.`year_month`
        """
        df = self._query(sql, params)
        logger.info(f"[MySQL] 成本结构: {len(df)} 条")
        return df

    def collect_targets(
        self,
        store_codes: list[str] | None = None,
        target_month: str | None = None,
    ) -> pd.DataFrame:
        """获取目标数据"""
        conditions = ["1=1"]
        params = {}
        if store_codes:
            placeholders = ", ".join(f":sc{i}" for i in range(len(store_codes)))
            conditions.append(f"store_code IN ({placeholders})")
            for i, sc in enumerate(store_codes):
                params[f"sc{i}"] = sc
        if target_month:
            conditions.append("target_month = :target_month")
            params["target_month"] = target_month

        where = " AND ".join(conditions)
        sql = f"""
        SELECT store_code, target_type, target_month, sales_target, profit_target, source
        FROM store_targets
        WHERE {where}
        ORDER BY store_code, target_month
        """
        df = self._query(sql, params)
        logger.info(f"[MySQL] 目标数据: {len(df)} 条")
        return df

    def collect_unified_sales(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        """生成统一销售宽表（月度粒度）

        将月度指标 + 成本结构合并为一张宽表，
        格式与 run_from_csv.py 的 build_unified_sales 输出兼容。
        """
        # 1. 加载月度指标（只取营业中的门店）
        metrics = self.collect_monthly_metrics(store_codes, start_month, end_month, active_only=True)
        if metrics.empty:
            logger.warning("[MySQL] 月度指标为空")
            return pd.DataFrame()

        # 2. 加载成本结构（只取营业中的门店）
        costs = self.collect_cost_structure(store_codes, start_month, end_month, active_only=True)

        # 3. 合并
        if not costs.empty:
            unified = metrics.merge(costs, on=["store_code", "year_month"], how="left")
        else:
            unified = metrics.copy()
            unified["total_cost"] = 0

        # 4. 计算推导列（与 pipeline 期望的列名对齐）
        unified["store_no"] = unified["store_code"]
        # 用 year_month 作为 base_date（月度粒度）
        unified["base_date"] = unified["year_month"].str.replace("-", "")

        unified["revenue"] = unified["sales_amount"]
        # COGS = revenue - gross_profit（从毛利反推采购成本）
        unified["hq_taxcost"] = unified["sales_amount"] - unified["gross_profit"]
        unified["gross_profit"] = unified["gross_profit"]
        # 运营费用估算（基于收入的比例，鞋服零售行业典型值）
        unified["operating_expense"] = unified["sales_amount"] * 0.18  # 18% 运营费用率
        unified["bmanaging_exp"] = unified["sales_amount"] * 0.02      # 2% 管理费用
        unified["operating_profit"] = unified["gross_profit"] - unified["operating_expense"] - unified["bmanaging_exp"]
        unified["store_contribution"] = unified["operating_profit"] * 0.90
        unified["salary_fee"] = unified["sales_amount"] * 0.08
        unified["social_fee"] = unified["sales_amount"] * 0.02
        unified["comprehensive_mall_fee"] = unified["sales_amount"] * 0.03
        unified["decorate_fee"] = unified["sales_amount"] * 0.01
        unified["express"] = unified["sales_amount"] * 0.01
        unified["all_other_fee"] = unified["sales_amount"] * 0.03
        unified["order_count"] = 0
        unified["qty_sold"] = 0
        unified["avg_discount"] = 1.0
        unified["perspective"] = "actual"

        # 品牌和区域（从 stores 表补充，INNER JOIN 排除无效门店）
        stores_df = self.collect_stores()
        if not stores_df.empty:
            merge_cols = ["store_code", "store_name", "region", "commercial_tier"]
            if "brand" in stores_df.columns:
                merge_cols.append("brand")
            store_info = stores_df[merge_cols].drop_duplicates()
            unified = unified.merge(store_info, on="store_code", how="inner")
            if "brand" not in unified.columns or unified["brand"].isna().all():
                unified["brand"] = unified.get("store_name", "未知")
            unified["brand"] = unified["brand"].fillna("未知")
            unified["region_top"] = unified["region"]
        else:
            unified["brand"] = "未知"
            unified["region_top"] = "未知"

        logger.info(f"[MySQL] 统一宽表: {len(unified)} 行, {unified['store_no'].nunique()} 家门店")
        return unified
