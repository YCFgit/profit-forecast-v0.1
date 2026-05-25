"""统一销售数据采集器

从 3 张销售相关表采集数据，生成统一宽表供下游模块使用。
"""

import os
from typing import Optional

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text

from src.core.config import get_settings


class SalesDataCollector:
    """统一销售数据采集器

    使用方式：
        collector = SalesDataCollector(adapter="starrocks")
        df = collector.collect_unified_sales(store_no="S001", date_range=("20260101", "20260131"))
    """

    TABLE_POS_ORD = os.getenv("TABLE_POS_ORD", "ads_pub.ads_fact_pos_ord_analysis")
    TABLE_STORE_LOSS = os.getenv("TABLE_STORE_LOSS", "proj_facana.ads_fin_fact_day_storeloss_pp")
    TABLE_STORE_LOSS_GJ = os.getenv("TABLE_STORE_LOSS_GJ", "proj_facana.ads_fin_fact_day_storeloss_pp_gj")

    def __init__(self, adapter: str = "mock"):
        self._adapter = adapter
        self._mock_store_loss_df = None
        self._mock_pos_df = None
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            settings = get_settings()
            url = (
                f"mysql+pymysql://{settings.starrocks_user}:{settings.starrocks_password}"
                f"@{settings.starrocks_host}:{settings.starrocks_port}/{settings.starrocks_database}"
            )
            self._engine = create_engine(url, pool_pre_ping=True)
        return self._engine

    def _execute_query(self, sql: str) -> pd.DataFrame:
        engine = self._get_engine()
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn)

    def collect_store_loss(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
        perspective: str = "actual",
    ) -> pd.DataFrame:
        """采集门店损益数据"""
        if self._adapter == "mock":
            return self._mock_collect_store_loss(store_no, date_range)

        prefix = "d1_pf" if perspective == "actual" else "d2"

        where_clauses = []
        if store_no:
            where_clauses.append(f"store_no = '{store_no}'")
        if date_range:
            where_clauses.append(f"base_date >= '{date_range[0]}' AND base_date <= '{date_range[1]}'")
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT
            store_no, base_date, brand_detail_abbreviation, region_top,
            province, managing_city, business_city, shop_category, business_attribute,
            {prefix}_total_sal_amt_pp AS d1_pf_total_sal_amt_pp,
            {prefix}_total_sal_amt AS d1_pf_total_sal_amt,
            {prefix}_settlement_amt AS d1_pf_settlement_amt,
            {prefix}_hq_notax_gross_profit AS d1_pf_hq_notax_gross_profit,
            {prefix}_hq_notax_gross_net_profit AS d1_pf_hq_notax_gross_net_profit,
            {prefix}_operating_exp AS d1_pf_operating_exp,
            {prefix}_bmanaging_exp AS d1_pf_bmanaging_exp,
            {prefix}_hq_notax_operating_profit AS d1_pf_hq_notax_operating_profit,
            {prefix}_store_contribution1 AS d1_pf_store_contribution1,
            {prefix}_salary_fee AS d1_pf_salary_fee,
            {prefix}_social_fee AS d1_pf_social_fee,
            {prefix}_comprehensive_mall_fee AS d1_pf_comprehensive_mall_fee,
            {prefix}_decorate_fee AS d1_pf_decorate_fee,
            {prefix}_express AS d1_pf_express,
            {prefix}_all_other_fee AS d1_pf_all_other_fee,
            {prefix}_hq_taxcost AS d1_pf_hq_taxcost,
            {prefix}_additional_taxes AS d1_pf_additional_taxes,
            {prefix}_server_fee AS d1_pf_server_fee,
            {prefix}_nonoperating_in_out AS d1_pf_nonoperating_in_out,
            {prefix}_total_prm_amt AS d1_pf_total_prm_amt
        FROM {self.TABLE_STORE_LOSS}
        WHERE {where_sql}
        """
        df = self._execute_query(sql)
        logger.info(f"采集 storeloss 数据: {len(df)} 行, perspective={perspective}")
        return df

    def collect_store_loss_gj(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
    ) -> pd.DataFrame:
        """采集门店损益数据（管理口径）"""
        if self._adapter == "mock":
            return self._mock_collect_store_loss(store_no, date_range)

        where_clauses = []
        if store_no:
            where_clauses.append(f"store_no = '{store_no}'")
        if date_range:
            where_clauses.append(f"base_date >= '{date_range[0]}' AND base_date <= '{date_range[1]}'")
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT
            store_no, base_date, brand_detail_abbreviation, region_top,
            d2_total_sal_amt, d2_settlement_amt, d2_hq_taxcost,
            d2_hq_notax_gross_profit, d2_operating_exp, d2_bmanaging_exp,
            d2_hq_notax_operating_profit, d2_store_contribution1
        FROM {self.TABLE_STORE_LOSS_GJ}
        WHERE {where_sql}
        """
        df = self._execute_query(sql)
        logger.info(f"采集 storeloss_gj 数据: {len(df)} 行")
        return df

    def collect_pos_orders(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
    ) -> pd.DataFrame:
        """采集 POS 订单数据"""
        if self._adapter == "mock":
            return self._mock_collect_pos_orders(store_no, date_range)

        where_clauses = []
        if store_no:
            where_clauses.append(f"org_lno = '{store_no}'")
        if date_range:
            where_clauses.append(f"period_sdate >= '{date_range[0]}' AND period_sdate <= '{date_range[1]}'")
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT
            org_lno AS store_no, period_sdate AS base_date,
            order_no, sal_amt, sal_qty, discount_rate, brd_dtl_no,
            sal_amt_sy, sal_qty_sy, is_new_name,
            brd_season_type_name, lsg_mon_qty
        FROM {self.TABLE_POS_ORD}
        WHERE {where_sql}
        """
        df = self._execute_query(sql)
        logger.info(f"采集 POS 订单数据: {len(df)} 行")
        return df

    def collect_unified_sales(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
        perspective: str = "actual",
    ) -> pd.DataFrame:
        """生成统一销售宽表"""
        loss_df = self.collect_store_loss(store_no, date_range, perspective)
        if loss_df.empty:
            logger.warning("storeloss 数据为空")
            return pd.DataFrame()

        pos_df = self.collect_pos_orders(store_no, date_range)

        if not pos_df.empty:
            pos_agg = pos_df.groupby(["store_no", "base_date"]).agg(
                order_count=("order_no", "nunique"),
                qty_sold=("sal_qty", "sum"),
                avg_discount=("discount_rate", "mean"),
            ).reset_index()
        else:
            pos_agg = pd.DataFrame(columns=["store_no", "base_date", "order_count", "qty_sold", "avg_discount"])

        unified = loss_df.merge(pos_agg, on=["store_no", "base_date"], how="left")

        unified = unified.rename(columns={
            "d1_pf_total_sal_amt_pp": "sales_amount",
            "d1_pf_total_sal_amt": "revenue",
            "d1_pf_settlement_amt": "settlement_amt",
            "d1_pf_hq_notax_gross_profit": "gross_profit",
            "d1_pf_hq_notax_gross_net_profit": "gross_net_profit",
            "d1_pf_operating_exp": "operating_expense",
            "d1_pf_bmanaging_exp": "bmanaging_exp",
            "d1_pf_hq_notax_operating_profit": "operating_profit",
            "d1_pf_store_contribution1": "store_contribution",
            "d1_pf_salary_fee": "salary_fee",
            "d1_pf_social_fee": "social_fee",
            "d1_pf_comprehensive_mall_fee": "comprehensive_mall_fee",
            "d1_pf_decorate_fee": "decorate_fee",
            "d1_pf_express": "express",
            "d1_pf_all_other_fee": "all_other_fee",
            "d1_pf_hq_taxcost": "hq_taxcost",
            "d1_pf_additional_taxes": "additional_taxes",
            "d1_pf_server_fee": "server_fee",
            "d1_pf_nonoperating_in_out": "nonoperating_in_out",
            "d1_pf_total_prm_amt": "prm_amt",
            "brand_detail_abbreviation": "brand",
        })

        unified["order_count"] = unified["order_count"].fillna(0).astype(int)
        unified["qty_sold"] = unified["qty_sold"].fillna(0).astype(int)
        unified["avg_discount"] = unified["avg_discount"].fillna(1.0)
        unified["perspective"] = perspective

        logger.info(f"统一销售宽表生成: {len(unified)} 行, {unified['store_no'].nunique()} 家门店")
        return unified

    def _mock_collect_store_loss(self, store_no, date_range):
        df = self._mock_store_loss_df.copy()
        if store_no:
            df = df[df["store_no"] == store_no]
        if date_range:
            df = df[(df["base_date"] >= date_range[0]) & (df["base_date"] <= date_range[1])]
        return df

    def _mock_collect_pos_orders(self, store_no, date_range):
        df = self._mock_pos_df.copy()
        if store_no:
            df = df[df["org_lno"] == store_no]
        if date_range:
            df = df[(df["period_sdate"] >= date_range[0]) & (df["period_sdate"] <= date_range[1])]
        # 与真实 SQL 保持一致，重命名列
        df = df.rename(columns={"org_lno": "store_no", "period_sdate": "base_date"})
        return df
