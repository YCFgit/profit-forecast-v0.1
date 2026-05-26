"""统一销售数据采集器

从 3 张销售相关表采集数据，生成统一宽表供下游模块使用。

注意：此类不继承 BaseCollector，因为 BaseCollector 的接口（async fetch_* 方法）
与本类的接口（sync collect_* 方法）不兼容。这是一个独立的数据采集组件。
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

        if adapter == "mock":
            self._generate_mock_data()

    def _generate_mock_data(self):
        """生成高仿真模拟数据

        特性：
        - 新店开业促销效应（1.4x → 1.2x → 1.05x → 1.0x 衰减）
        - 品牌差异化基础业绩
        - 区域差异
        - 周末效应（周末 +20%）
        - 季节波动
        - 返利口径模拟（d2_ = d1_pf_ × 返利系数）
        - 每店独立成本比率
        """
        import numpy as np

        rng = np.random.RandomState(42)
        store_codes = [f"ST{i:04d}" for i in range(1, 21)]
        dates = pd.date_range("2025-01-01", "2025-03-31", freq="D")
        brands = ["品牌A", "品牌B", "品牌C"]
        regions = ["华东", "华南", "华北"]

        # 品牌基础系数（品牌A最强）
        brand_base = {"品牌A": 1.2, "品牌B": 1.0, "品牌C": 0.85}
        # 区域系数
        region_base = {"华东": 1.15, "华南": 1.0, "华北": 0.9}
        # 季节系数
        season_map = {
            1: 0.70, 2: 0.65, 3: 0.80, 4: 0.90, 5: 0.95, 6: 1.10,
            7: 0.90, 8: 0.85, 9: 0.95, 10: 1.00, 11: 1.20, 12: 1.30,
        }
        # 新店开业效应系数（月龄 → 系数）
        def promotion_effect(days_since_opening):
            months = days_since_opening / 30.0
            if months <= 3:
                return 1.40
            elif months <= 6:
                return 1.20
            elif months <= 12:
                return 1.05
            else:
                return 1.00

        # 每店固定属性
        store_attrs = {}
        for i, store in enumerate(store_codes):
            brand = brands[i % 3]
            region = regions[i % 3]
            # 基础日收入（大店 8-20 万，小店 2-8 万）
            if i < 12:
                base_rev = rng.uniform(80000, 200000)
            else:
                base_rev = rng.uniform(20000, 80000)
            # 每店独立成本比率
            cogs_ratio = rng.uniform(0.38, 0.52)
            salary_ratio = rng.uniform(0.08, 0.14)
            social_ratio = rng.uniform(0.03, 0.05)
            mall_fee_ratio = rng.uniform(0.02, 0.05)
            # 返利系数（返利口径 = 业绩口径 × rebate_factor）
            rebate_factor = rng.uniform(0.93, 1.05)
            # 新店：ST0017-ST0020 开业于 2025-01-15
            is_new = i >= 16
            opening_date = pd.Timestamp("2025-01-15") if is_new else pd.Timestamp("2022-06-01")

            store_attrs[store] = {
                "brand": brand, "region": region, "base_rev": base_rev,
                "cogs_ratio": cogs_ratio, "salary_ratio": salary_ratio,
                "social_ratio": social_ratio, "mall_fee_ratio": mall_fee_ratio,
                "rebate_factor": rebate_factor, "is_new": is_new,
                "opening_date": opening_date,
            }

        # 生成 store_loss 数据
        rows = []
        for store in store_codes:
            attrs = store_attrs[store]
            brand = attrs["brand"]
            region = attrs["region"]
            base_rev = attrs["base_rev"]
            brand_mult = brand_base[brand]
            region_mult = region_base[region]

            for dt in dates:
                season = season_map[dt.month]
                # 周末效应
                weekday_mult = 1.20 if dt.dayofweek >= 5 else 1.0
                # 新店开业效应
                days_open = (dt - attrs["opening_date"]).days
                promo_mult = promotion_effect(max(0, days_open))

                # 最终收入
                revenue = base_rev * brand_mult * region_mult * season * weekday_mult * promo_mult
                revenue *= rng.uniform(0.85, 1.15)  # 随机波动
                revenue = max(1000, revenue)

                cogs = revenue * attrs["cogs_ratio"]
                gross = revenue - cogs
                salary = revenue * attrs["salary_ratio"]
                social = revenue * attrs["social_ratio"]
                mall_fee = revenue * attrs["mall_fee_ratio"]
                b_manage = revenue * rng.uniform(0.02, 0.04)
                opex = salary + social + mall_fee + revenue * 0.02
                operating_profit = gross - opex - b_manage

                # 返利口径（revenue × 返利系数，有波动）
                rebate_revenue = revenue * attrs["rebate_factor"] * rng.uniform(0.98, 1.02)
                rebate_cogs = cogs * rng.uniform(0.98, 1.02)
                rebate_gross = rebate_revenue - rebate_cogs
                rebate_opex = opex * rng.uniform(0.98, 1.02)
                rebate_operating_profit = rebate_gross - rebate_opex - b_manage

                rows.append({
                    "store_no": store,
                    "base_date": dt.strftime("%Y-%m-%d"),
                    "brand_detail_abbreviation": brand,
                    "region_top": region,
                    "province": "上海",
                    "managing_city": "上海",
                    "business_city": "上海",
                    "shop_category": "直营",
                    "business_attribute": "A类",
                    # 业绩口径 (d1_pf_)
                    "d1_pf_total_sal_amt_pp": round(revenue * 1.05, 2),
                    "d1_pf_total_sal_amt": round(revenue, 2),
                    "d1_pf_settlement_amt": round(revenue * 0.98, 2),
                    "d1_pf_hq_notax_gross_profit": round(gross, 2),
                    "d1_pf_hq_notax_gross_net_profit": round(gross * 0.95, 2),
                    "d1_pf_operating_exp": round(opex, 2),
                    "d1_pf_bmanaging_exp": round(b_manage, 2),
                    "d1_pf_hq_notax_operating_profit": round(operating_profit, 2),
                    "d1_pf_store_contribution1": round(operating_profit * 0.85, 2),
                    "d1_pf_salary_fee": round(salary, 2),
                    "d1_pf_social_fee": round(social, 2),
                    "d1_pf_comprehensive_mall_fee": round(mall_fee, 2),
                    "d1_pf_decorate_fee": round(revenue * 0.005, 2),
                    "d1_pf_express": round(revenue * 0.01, 2),
                    "d1_pf_all_other_fee": round(revenue * 0.015, 2),
                    "d1_pf_hq_taxcost": round(cogs, 2),
                    "d1_pf_additional_taxes": 0.0,
                    "d1_pf_server_fee": round(revenue * 0.005, 2),
                    "d1_pf_nonoperating_in_out": 0.0,
                    "d1_pf_total_prm_amt": round(revenue * 0.02, 2),
                    # 返利口径 (d2_)
                    "d2_total_sal_amt": round(rebate_revenue, 2),
                    "d2_hq_notax_gross_profit": round(rebate_gross, 2),
                    "d2_operating_exp": round(rebate_opex, 2),
                    "d2_hq_notax_operating_profit": round(rebate_operating_profit, 2),
                })
        self._mock_store_loss_df = pd.DataFrame(rows)

        # 生成 POS 订单数据
        pos_rows = []
        for store in store_codes:
            attrs = store_attrs[store]
            brand = attrs["brand"]
            for dt in dates:
                season = season_map[dt.month]
                weekday_mult = 1.20 if dt.dayofweek >= 5 else 1.0
                days_open = (dt - attrs["opening_date"]).days
                promo_mult = promotion_effect(max(0, days_open))

                # 订单数与收入成正比
                base_orders = int(attrs["base_rev"] / 3000)
                n_orders = max(1, int(base_orders * season * weekday_mult * promo_mult * rng.uniform(0.7, 1.3)))

                for _ in range(n_orders):
                    discount = rng.uniform(0.55, 1.0)
                    # 新店折扣更大（促销）
                    if attrs["is_new"] and days_open <= 90:
                        discount = rng.uniform(0.45, 0.85)
                    sal_amt = rng.uniform(300, 5000) * discount
                    pos_rows.append({
                        "org_lno": store,
                        "period_sdate": dt.strftime("%Y-%m-%d"),
                        "order_no": f"ORD{rng.randint(100000, 999999)}",
                        "sal_amt": round(sal_amt, 2),
                        "sal_qty": max(1, int(sal_amt / rng.uniform(200, 800))),
                        "discount_rate": round(discount, 4),
                        "brd_dtl_no": f"SKU{rng.randint(1000, 9999)}",
                        "sal_amt_sy": round(sal_amt * rng.uniform(0.9, 1.1), 2),
                        "sal_qty_sy": max(1, int(sal_amt / rng.uniform(200, 800))),
                        "is_new_name": rng.choice(["新品", "老品"]),
                        "brd_season_type_name": rng.choice(["春季", "夏季", "秋季", "冬季"]),
                        "lsg_mon_qty": rng.randint(0, 5),
                    })
        self._mock_pos_df = pd.DataFrame(pos_rows)

        logger.info(
            f"[Mock] SalesDataCollector 生成高仿真数据: "
            f"{len(self._mock_store_loss_df)} 条损益, "
            f"{len(self._mock_pos_df)} 条 POS 订单, "
            f"新店促销效应已启用"
        )

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
        """构建 WHERE 子句和参数"""
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
        where_sql, params = self._build_where(store_no, date_range)

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
        df = self._execute_query(sql, params)
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

        where_sql, params = self._build_where(store_no, date_range)

        sql = f"""
        SELECT
            store_no, base_date, brand_detail_abbreviation, region_top,
            d2_total_sal_amt, d2_settlement_amt, d2_hq_taxcost,
            d2_hq_notax_gross_profit, d2_operating_exp, d2_bmanaging_exp,
            d2_hq_notax_operating_profit, d2_store_contribution1
        FROM {self.TABLE_STORE_LOSS_GJ}
        WHERE {where_sql}
        """
        df = self._execute_query(sql, params)
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

        where_sql, params = self._build_where(
            store_no, date_range, store_col="org_lno", date_col="period_sdate"
        )

        sql = f"""
        SELECT
            org_lno AS store_no, period_sdate AS base_date,
            order_no, sal_amt, sal_qty, discount_rate, brd_dtl_no,
            sal_amt_sy, sal_qty_sy, is_new_name,
            brd_season_type_name, lsg_mon_qty
        FROM {self.TABLE_POS_ORD}
        WHERE {where_sql}
        """
        df = self._execute_query(sql, params)
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
        df = df.rename(columns={"org_lno": "store_no", "period_sdate": "base_date"})
        return df
