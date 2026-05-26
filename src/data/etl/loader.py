"""数据加载器

从 StarRocks 读取门店、损益、POS、月度指标数据。
复用 scripts/etl_sql/ 中定义的查询逻辑。
"""

import os
from typing import Optional

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text

from src.core.config import get_settings


class SalesLoader:
    """从 StarRocks 加载销售相关数据

    使用方式：
        loader = SalesLoader()
        stores_df = loader.load_stores()
        loss_df = loader.load_store_loss(date_range=("2026-01-01", "2026-03-31"))
    """

    TABLE_STORE_LOSS = os.getenv(
        "TABLE_STORE_LOSS", "proj_facana.ads_fin_fact_day_storeloss_pp"
    )
    TABLE_STORE_LOSS_GJ = os.getenv(
        "TABLE_STORE_LOSS_GJ", "proj_facana.ads_fin_fact_day_storeloss_pp_gj"
    )
    TABLE_POS_ORD = os.getenv(
        "TABLE_POS_ORD", "ads_pub.ads_fact_pos_ord_analysis"
    )
    TABLE_STORES = os.getenv(
        "TABLE_STORES", "dws_pub.dws_dim_org_allinfo"
    )
    TABLE_MONTHLY = os.getenv(
        "TABLE_MONTHLY", "proj_facana.dwd_f04_dayone_countbase_pp_new"
    )

    def __init__(self):
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

    def _execute_query(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                return pd.read_sql(text(sql), conn, params=params or {})
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            return pd.DataFrame()

    def _build_where(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
        store_col: str = "store_no",
        date_col: str = "base_date",
    ) -> tuple[str, dict]:
        conditions = ["1=1"]
        params = {}
        if store_no:
            conditions.append(f"{store_col} = :store_no")
            params["store_no"] = store_no
        if date_range:
            conditions.append(f"{date_col} >= :date_start AND {date_col} <= :date_end")
            params["date_start"] = date_range[0]
            params["date_end"] = date_range[1]
        return " AND ".join(conditions), params

    # ------------------------------------------------------------------
    # 门店主数据
    # ------------------------------------------------------------------
    def load_stores(self, store_no: Optional[str] = None) -> pd.DataFrame:
        """加载门店主数据"""
        where_sql, params = self._build_where(store_no, store_col="org_lno")
        sql = f"""
        SELECT
            org_lno AS store_code,
            org_name AS store_name,
            brd_dtl_abbr AS brand,
            store_type_name AS store_type,
            big_region_name AS region,
            region_name AS sub_region,
            mc_name AS city,
            province_name AS province,
            biz_attr_name AS business_attribute,
            store_level_name AS store_level,
            biz_area AS business_area,
            open_date AS opening_date,
            close_date AS closing_date,
            store_status AS status,
            is_entity,
            is_new_flag AS is_new_store,
            etl_update_time
        FROM {self.TABLE_STORES}
        WHERE {where_sql}
        ORDER BY org_lno
        """
        df = self._execute_query(sql, params)
        logger.info(f"加载门店主数据: {len(df)} 条")
        return df

    # ------------------------------------------------------------------
    # 日损益数据（支持双口径）
    # ------------------------------------------------------------------
    def load_store_loss(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
        perspective: str = "actual",
    ) -> pd.DataFrame:
        """加载日损益数据

        Args:
            perspective: "actual" (业绩口径 d1_pf_) 或 "rebate" (返利口径 d2_)
        """
        prefix = "d1_pf" if perspective == "actual" else "d2"
        where_sql, params = self._build_where(store_no, date_range)

        sql = f"""
        SELECT
            store_no,
            base_date,
            brand_detail_abbreviation AS brand,
            region_top AS region,
            province,
            managing_city,
            business_city,
            shop_category,
            business_attribute,
            {prefix}_total_sal_amt_pp AS sales_amount_pp,
            {prefix}_total_sal_amt AS sales_amount,
            {prefix}_settlement_amt AS settlement_amt,
            {prefix}_hq_taxcost AS hq_taxcost,
            {prefix}_hq_notax_gross_profit AS gross_profit,
            {prefix}_hq_notax_gross_net_profit AS gross_net_profit,
            {prefix}_operating_exp AS operating_expense,
            {prefix}_bmanaging_exp AS bmanaging_exp,
            {prefix}_hq_notax_operating_profit AS operating_profit,
            {prefix}_store_contribution1 AS store_contribution,
            {prefix}_salary_fee AS salary_fee,
            {prefix}_social_fee AS social_fee,
            {prefix}_comprehensive_mall_fee AS comprehensive_mall_fee,
            {prefix}_decorate_fee AS decorate_fee,
            {prefix}_express AS express,
            {prefix}_all_other_fee AS all_other_fee,
            {prefix}_additional_taxes AS additional_taxes,
            {prefix}_server_fee AS server_fee,
            {prefix}_nonoperating_in_out AS nonoperating_in_out,
            {prefix}_total_prm_amt AS prm_amt
        FROM {self.TABLE_STORE_LOSS}
        WHERE {where_sql}
        ORDER BY store_no, base_date
        """
        df = self._execute_query(sql, params)
        df["perspective"] = perspective
        logger.info(f"加载日损益数据: {len(df)} 条, 口径={perspective}")
        return df

    # ------------------------------------------------------------------
    # POS 订单数据
    # ------------------------------------------------------------------
    def load_pos_orders(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
    ) -> pd.DataFrame:
        """加载 POS 订单明细"""
        where_sql, params = self._build_where(
            store_no, date_range, store_col="org_lno", date_col="period_sdate"
        )
        sql = f"""
        SELECT
            org_lno AS store_no,
            period_sdate AS base_date,
            order_no,
            sal_amt,
            sal_qty,
            discount_rate,
            brd_dtl_no,
            sal_amt_sy,
            sal_qty_sy,
            is_new_name,
            brd_season_type_name,
            lsg_mon_qty
        FROM {self.TABLE_POS_ORD}
        WHERE {where_sql}
        """
        df = self._execute_query(sql, params)
        logger.info(f"加载 POS 订单数据: {len(df)} 条")
        return df

    # ------------------------------------------------------------------
    # 月度指标聚合
    # ------------------------------------------------------------------
    def load_monthly_metrics(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
    ) -> pd.DataFrame:
        """从日损益聚合月度指标"""
        where_sql, params = self._build_where(store_no, date_range)

        sql = f"""
        SELECT
            store_no AS store_code,
            SUBSTR(base_date, 1, 7) AS year_month,
            brand_detail_abbreviation AS brand,
            SUM(d1_pf_total_sal_amt) AS sales_amount,
            SUM(d1_pf_total_prm_amt) AS tag_price_amount,
            SUM(d1_pf_hq_taxcost) AS hq_tax_cost,
            SUM(d1_pf_hq_notax_gross_profit) AS hq_notax_gross_profit,
            SUM(d1_pf_operating_exp) AS operating_expense,
            SUM(d1_pf_bmanaging_exp) AS b_managing_expense,
            SUM(d1_pf_hq_notax_operating_profit) AS hq_notax_operating_profit,
            SUM(d1_pf_salary_fee) AS salary_fee,
            SUM(d1_pf_social_fee) AS social_fee,
            CASE WHEN SUM(d1_pf_total_sal_amt) > 0
                 THEN SUM(d1_pf_hq_notax_gross_profit) / SUM(d1_pf_total_sal_amt)
                 ELSE 0 END AS gross_margin,
            CASE WHEN SUM(d1_pf_total_sal_amt) > 0
                 THEN SUM(d1_pf_hq_notax_operating_profit) / SUM(d1_pf_total_sal_amt)
                 ELSE 0 END AS operating_margin
        FROM {self.TABLE_STORE_LOSS}
        WHERE {where_sql}
        GROUP BY store_no, SUBSTR(base_date, 1, 7), brand_detail_abbreviation
        ORDER BY store_no, year_month
        """
        df = self._execute_query(sql, params)
        logger.info(f"加载月度指标: {len(df)} 条")
        return df

    # ------------------------------------------------------------------
    # 统一销售宽表（损益 + POS 聚合）
    # ------------------------------------------------------------------
    def load_unified_sales(
        self,
        store_no: Optional[str] = None,
        date_range: Optional[tuple] = None,
        perspective: str = "actual",
    ) -> pd.DataFrame:
        """生成统一销售宽表（损益 + POS 订单聚合）"""
        loss_df = self.load_store_loss(store_no, date_range, perspective)
        if loss_df.empty:
            logger.warning("损益数据为空")
            return pd.DataFrame()

        pos_df = self.load_pos_orders(store_no, date_range)

        if not pos_df.empty:
            pos_agg = pos_df.groupby(["store_no", "base_date"]).agg(
                order_count=("order_no", "nunique"),
                qty_sold=("sal_qty", "sum"),
                avg_discount=("discount_rate", "mean"),
            ).reset_index()
        else:
            pos_agg = pd.DataFrame(
                columns=["store_no", "base_date", "order_count", "qty_sold", "avg_discount"]
            )

        unified = loss_df.merge(pos_agg, on=["store_no", "base_date"], how="left")
        unified["order_count"] = unified["order_count"].fillna(0).astype(int)
        unified["qty_sold"] = unified["qty_sold"].fillna(0).astype(int)
        unified["avg_discount"] = unified["avg_discount"].fillna(1.0)

        logger.info(f"统一销售宽表: {len(unified)} 行, {unified['store_no'].nunique()} 家门店")
        return unified
