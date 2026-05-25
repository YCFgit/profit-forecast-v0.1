"""StarRocks 数据采集器

StarRocks 支持 MySQL 协议，使用 pymysql 连接即可。
直接查询阿里云上的源数据，实时性强。

源表映射：
  - 门店主数据: dws_pub.dws_dim_org_allinfo (机构信息维表)
  - 日销售/损益: proj_facana.dwd_f04_dayone_countbase_pp_new (日实时损益表-业绩版)
  - 门店基础信息: proj_facana.dwd_f04_dayone_s_store_info (日实时扩充店铺信息)
  - POS订单明细: spark_catalog.ads_pub.ads_fact_pos_ord_analysis (POS订单分析)
  - 门店日损益: proj_facana.ads_fin_fact_day_storeloss_pp (日门店损益)
  - 日目标数据: dws_pub.dws_fact_day_org_target_cost (日店铺基础目标表)
  - 开关状态: dws_pub.dws_dim_org_on_off (店铺开改关表)

配置项（.env）：
    STARROCKS_HOST: StarRocks FE 地址
    STARROCKS_PORT: 端口（默认 9030）
    STARROCKS_USER: 用户名
    STARROCKS_PASSWORD: 密码
    STARROCKS_DATABASE: 默认数据库名
"""

from datetime import date

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text

from src.core.config import get_settings
from src.data.collectors.base import BaseCollector


class StarRocksCollector(BaseCollector):
    """StarRocks 数据采集器

    通过 MySQL 协议连接 StarRocks FE，直接查询源数据。
    支持标准 SQL，查询速度快，适合 OLAP 场景。

    使用方式：
        collector = StarRocksCollector()
        async with collector:
            stores = await collector.fetch_stores()
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ):
        settings = get_settings()
        self.host = host or getattr(settings, "starrocks_host", "localhost")
        self.port = port or getattr(settings, "starrocks_port", 9030)
        self.user = user or getattr(settings, "starrocks_user", "root")
        self.password = password or getattr(settings, "starrocks_password", "")
        self.database = database or getattr(settings, "starrocks_database", "")
        self._engine = None

    @property
    def connection_url(self) -> str:
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?charset=utf8mb4"

    async def connect(self) -> None:
        """建立连接"""
        logger.info(f"[StarRocks] 连接: {self.host}:{self.port}/{self.database}")
        self._engine = create_engine(
            self.connection_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info(f"[StarRocks] 连接成功: {result.scalar()}")
        except Exception as e:
            logger.error(f"[StarRocks] 连接失败: {e}")
            raise

    async def disconnect(self) -> None:
        """关闭连接"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            logger.info("[StarRocks] 连接已关闭")

    def _query(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        """执行查询，返回 DataFrame"""
        logger.debug(f"[StarRocks] 执行查询:\n{sql[:300]}...")
        with self._engine.connect() as conn:
            df = pd.read_sql(text(sql), conn, params=params)
        logger.info(f"[StarRocks] 查询返回 {len(df)} 行")
        return df

    def _build_in_clause(
        self, values: list[str], prefix: str, field: str
    ) -> tuple[str, dict]:
        """构建 IN 子句和参数字典"""
        placeholders = ", ".join([f":{prefix}{i}" for i in range(len(values))])
        condition = f"{field} IN ({placeholders})"
        params = {f"{prefix}{i}": v for i, v in enumerate(values)}
        return condition, params

    # ==============================================================
    # 1. 门店主数据 — dws_pub.dws_dim_org_allinfo
    # ==============================================================

    async def fetch_stores(self) -> pd.DataFrame:
        """获取门店主数据

        数据源: dws_pub.dws_dim_org_allinfo (DIM_机构信息维表)
        主键: org_lno (机构原编码)
        """
        sql = """
        SELECT
            org_lno            AS store_code,
            org_name           AS store_name,
            store_abbr         AS store_short_name,
            brd_dtl_abbr       AS brand,
            store_type_name    AS store_type,
            store_channel_name1 AS channel_l1,
            store_channel_name2 AS channel_l2,
            store_channel_name3 AS channel_l3,
            big_region_name    AS region,
            region_name        AS sub_region,
            mc_name            AS city,
            province_name      AS province,
            city_name          AS admin_city,
            biz_attr_name      AS business_attribute,
            biz_attr_name2     AS business_category,
            biz_attr_name3     AS business_detail,
            store_level_name   AS store_level,
            mall_name          AS mall_name,
            biz_circle_name    AS commercial_circle,
            city_level         AS city_level,
            biz_area           AS business_area,
            area_total         AS total_area,
            open_date          AS opening_date,
            close_date         AS closing_date,
            actual_open_date   AS actual_open_date,
            real_withdrawal_date AS withdrawal_date,
            store_status       AS status,
            is_entity          AS is_entity,
            is_new_flag        AS is_new_store,
            property_cooperation AS cooperation_mode,
            property_cooperation_cond AS cooperation_cond,
            settlement_mth     AS settlement_method,
            self_checking_mode AS self_cash_mode,
            big_store_format   AS big_store_format,
            org_sal_biz_type   AS sales_biz_type,
            org_sal_mode       AS sales_mode,
            fin_code           AS fin_code,
            virtual_shop_type  AS virtual_shop_type,
            store_type         AS store_type_flag,
            etl_update_time    AS etl_update_time
        FROM dws_pub.dws_dim_org_allinfo
        WHERE store_status = 1
          AND is_entity = 1
        ORDER BY org_lno
        """
        try:
            df = self._query(sql)
            logger.info(f"[StarRocks] 获取门店主数据: {len(df)} 家门店")
            return df
        except Exception as e:
            logger.error(f"[StarRocks] fetch_stores 失败: {e}")
            return pd.DataFrame()

    # ==============================================================
    # 2. 日销售/损益数据 — proj_facana.dwd_f04_dayone_countbase_pp_new
    # ==============================================================

    async def fetch_daily_sales(
        self,
        store_codes: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取门店日销/损益数据

        数据源: proj_facana.dwd_f04_dayone_countbase_pp_new (日实时损益表-业绩版)
        主键: (base_date, store_no, brand_detail_abbreviation)
        """
        conditions = ["1=1"]
        params = {}

        if store_codes:
            clause, p = self._build_in_clause(store_codes, "sc", "store_no")
            conditions.append(clause)
            params.update(p)

        if start_date:
            conditions.append("base_date >= :start_date")
            params["start_date"] = start_date.strftime("%Y-%m-%d")

        if end_date:
            conditions.append("base_date <= :end_date")
            params["end_date"] = end_date.strftime("%Y-%m-%d")

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT
            store_no                         AS store_code,
            base_date                        AS sale_date,
            brand_detail_abbreviation        AS brand,
            -- 销售额
            total_sal_amt                    AS sales_amount,
            total_prm_amt                    AS tag_price_amount,
            shoes_sal_amt                    AS shoes_sales,
            clothes_sal_amt                  AS clothes_sales,
            bag_sal_amt                      AS bag_sales,
            parts_sal_amt                    AS parts_sales,
            -- 成本
            taxcost                          AS tax_cost,
            hq_taxcost                       AS hq_tax_cost,
            notax_cost                       AS notax_cost,
            -- 毛利
            tax_gross_profit                 AS tax_gross_profit,
            notax_gross_profit               AS notax_gross_profit,
            hq_tax_gross_profit              AS hq_tax_gross_profit,
            hq_notax_gross_profit            AS hq_notax_gross_profit,
            -- 费用
            operating_exp                    AS operating_expense,
            total_operating_exp              AS total_operating_expense,
            bmanaging_exp                    AS b_managing_expense,
            managing_exp                     AS managing_expense,
            financial_exp                    AS financial_expense,
            additional_taxes                 AS additional_taxes,
            -- 利润
            notax_operating_profit           AS notax_operating_profit,
            hq_notax_operating_profit        AS hq_notax_operating_profit,
            notax_net_profit                 AS notax_net_profit,
            hq_notax_net_profit              AS hq_notax_net_profit,
            net_profit                       AS net_profit,
            -- 折扣
            sal_dct                          AS sales_deduction,
            deduction_rate                   AS deduction_rate,
            -- 收入
            stm_income                       AS settlement_income,
            notax_income                     AS notax_income,
            -- 人员
            staff_number                     AS staff_count,
            store_area                       AS store_area,
            -- 门店属性
            affiliation                      AS affiliation,
            region                           AS region,
            province                         AS province,
            managing_city                    AS managing_city,
            business_city                    AS business_city,
            store_type                       AS store_type,
            store_status                     AS store_status,
            business_attribute               AS business_attribute,
            distribution_level               AS distribution_level,
            prop_cooperation_mode            AS cooperation_mode,
            prop_cooperation_conds           AS cooperation_cond,
            -- 目标
            total_sal_amt_pp                 AS total_sales_pp,
            total_sal_amt_dpp                AS total_sales_dpp,
            -- 税率
            income_tax_rate                  AS income_tax_rate,
            hq_income_tax_rate               AS hq_income_tax_rate,
            -- ETL
            etl_update_time                  AS etl_update_time
        FROM proj_facana.dwd_f04_dayone_countbase_pp_new
        WHERE {where_clause}
        ORDER BY store_no, base_date
        """
        try:
            df = self._query(sql, params)
            logger.info(f"[StarRocks] 获取日销售数据: {len(df)} 行")
            return df
        except Exception as e:
            logger.error(f"[StarRocks] fetch_daily_sales 失败: {e}")
            return pd.DataFrame()

    # ==============================================================
    # 3. 月度指标 — 聚合自 dwd_f04_dayone_countbase_pp_new
    # ==============================================================

    async def fetch_monthly_metrics(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        """获取门店月度指标（从日损益表聚合）

        数据源: proj_facana.dwd_f04_dayone_countbase_pp_new
        聚合粒度: store_no + 月份
        """
        conditions = ["1=1"]
        params = {}

        if store_codes:
            clause, p = self._build_in_clause(store_codes, "sc", "store_no")
            conditions.append(clause)
            params.update(p)

        if start_month:
            conditions.append("SUBSTR(base_date, 1, 7) >= :start_month")
            params["start_month"] = start_month

        if end_month:
            conditions.append("SUBSTR(base_date, 1, 7) <= :end_month")
            params["end_month"] = end_month

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT
            store_no                         AS store_code,
            SUBSTR(base_date, 1, 7)          AS year_month,
            brand_detail_abbreviation        AS brand,
            -- 销售汇总
            SUM(total_sal_amt)               AS sales_amount,
            SUM(total_prm_amt)               AS tag_price_amount,
            SUM(shoes_sal_amt)               AS shoes_sales,
            SUM(clothes_sal_amt)             AS clothes_sales,
            SUM(bag_sal_amt)                 AS bag_sales,
            SUM(parts_sal_amt)               AS parts_sales,
            -- 成本汇总
            SUM(taxcost)                     AS tax_cost,
            SUM(hq_taxcost)                  AS hq_tax_cost,
            -- 毛利汇总
            SUM(hq_notax_gross_profit)       AS hq_notax_gross_profit,
            SUM(tax_gross_profit)            AS tax_gross_profit,
            -- 费用汇总
            SUM(operating_exp)               AS operating_expense,
            SUM(bmanaging_exp)               AS b_managing_expense,
            SUM(additional_taxes)            AS additional_taxes,
            -- 利润汇总
            SUM(notax_operating_profit)      AS notax_operating_profit,
            SUM(hq_notax_operating_profit)   AS hq_notax_operating_profit,
            SUM(notax_net_profit)            AS notax_net_profit,
            SUM(hq_notax_net_profit)         AS hq_notax_net_profit,
            SUM(net_profit)                  AS net_profit,
            -- 折扣率（加权平均）
            CASE WHEN SUM(total_prm_amt) > 0
                 THEN SUM(sal_dct) / SUM(total_prm_amt)
                 ELSE 0 END                  AS deduction_rate,
            -- 坪效（销售额 / 面积）
            CASE WHEN MAX(store_area) > 0
                 THEN SUM(total_sal_amt) / MAX(store_area)
                 ELSE 0 END                  AS sales_per_sqm,
            -- 人效（销售额 / 人数）
            CASE WHEN MAX(staff_number) > 0
                 THEN SUM(total_sal_amt) / MAX(staff_number)
                 ELSE 0 END                  AS revenue_per_staff,
            -- 毛利率
            CASE WHEN SUM(total_sal_amt) > 0
                 THEN SUM(hq_notax_gross_profit) / SUM(total_sal_amt)
                 ELSE 0 END                  AS gross_margin,
            -- 营业利润率
            CASE WHEN SUM(total_sal_amt) > 0
                 THEN SUM(notax_operating_profit) / SUM(total_sal_amt)
                 ELSE 0 END                  AS operating_margin,
            -- 净利率
            CASE WHEN SUM(total_sal_amt) > 0
                 THEN SUM(notax_net_profit) / SUM(total_sal_amt)
                 ELSE 0 END                  AS net_margin,
            -- 门店属性（取最新值）
            MAX(store_area)                  AS store_area,
            MAX(staff_number)                AS staff_count
        FROM proj_facana.dwd_f04_dayone_countbase_pp_new
        WHERE {where_clause}
        GROUP BY store_no, SUBSTR(base_date, 1, 7), brand_detail_abbreviation
        ORDER BY store_no, year_month
        """
        try:
            df = self._query(sql, params)
            logger.info(f"[StarRocks] 获取月度指标: {len(df)} 行")
            return df
        except Exception as e:
            logger.error(f"[StarRocks] fetch_monthly_metrics 失败: {e}")
            return pd.DataFrame()

    # ==============================================================
    # 4. 目标数据 — spark_catalog.ads_pub.ads_fact_pos_ord_analysis
    # ==============================================================

    async def fetch_targets(
        self,
        store_codes: list[str] | None = None,
        target_type: str = "monthly",
        target_month: str | None = None,
    ) -> pd.DataFrame:
        """获取目标数据

        数据源: spark_catalog.ads_pub.ads_fact_pos_ord_analysis (POS订单分析)
        注意: 店铺编码字段为 sy_org_lno（业绩归属店号）
        分区字段: p_mon (yyyymm)

        target_type:
          - "daily": 日营业目标 (amt_target)
          - "monthly": 月营业目标 (mon_amt_target)
        """
        conditions = ["1=1"]
        params = {}

        if store_codes:
            clause, p = self._build_in_clause(store_codes, "sc", "sy_org_lno")
            conditions.append(clause)
            params.update(p)

        if target_month:
            # p_mon 分区字段格式: yyyymm
            conditions.append("p_mon = :p_mon")
            params["p_mon"] = target_month.replace("-", "")[:6]

        where_clause = " AND ".join(conditions)

        if target_type == "daily":
            # 日目标：按门店+日期去重取目标值
            sql = f"""
            SELECT
                sy_org_lno                   AS store_code,
                period_sdate                 AS target_date,
                brd_dtl_abbr                 AS brand,
                pro_cate_name                AS category,
                -- 日营业目标（取非空非零的最大值）
                MAX(amt_target)              AS daily_sales_target,
                -- 进店人数
                SUM(enter_store_qty)         AS foot_traffic,
                -- 销售数据
                SUM(sal_qty)                 AS sales_qty,
                SUM(sal_amt)                 AS sales_amount,
                SUM(sal_prm_amt)             AS tag_price_amount,
                -- 折扣
                CASE WHEN SUM(sal_prm_amt) > 0
                     THEN 1 - SUM(sal_amt) / SUM(sal_prm_amt)
                     ELSE 0 END             AS discount_rate
            FROM spark_catalog.ads_pub.ads_fact_pos_ord_analysis
            WHERE {where_clause}
              AND amt_target > 0
            GROUP BY sy_org_lno, period_sdate, brd_dtl_abbr, pro_cate_name
            ORDER BY store_code, target_date
            """
        else:
            # 月目标：按门店+月份聚合，取月营业目标
            sql = f"""
            SELECT
                sy_org_lno                   AS store_code,
                p_mon                        AS target_month,
                brd_dtl_abbr                 AS brand,
                pro_cate_name                AS category,
                -- 月营业目标（取非空非零的最大值）
                MAX(mon_amt_target)          AS monthly_sales_target,
                -- 月度汇总
                SUM(sal_qty)                 AS sales_qty,
                SUM(sal_amt)                 AS sales_amount,
                SUM(sal_prm_amt)             AS tag_price_amount,
                SUM(enter_store_qty)         AS foot_traffic,
                -- 折扣率
                CASE WHEN SUM(sal_prm_amt) > 0
                     THEN 1 - SUM(sal_amt) / SUM(sal_prm_amt)
                     ELSE 0 END             AS discount_rate
            FROM spark_catalog.ads_pub.ads_fact_pos_ord_analysis
            WHERE {where_clause}
              AND mon_amt_target > 0
            GROUP BY sy_org_lno, p_mon, brd_dtl_abbr, pro_cate_name
            ORDER BY store_code, target_month
            """

        try:
            df = self._query(sql, params)
            logger.info(f"[StarRocks] 获取目标数据({target_type}): {len(df)} 行")
            return df
        except Exception as e:
            logger.error(f"[StarRocks] fetch_targets 失败: {e}")
            return pd.DataFrame()

    # ==============================================================
    # 5. 门店人员数据 — proj_facana.dwd_f04_dayone_s_store_info
    # ==============================================================

    async def fetch_staff(
        self, store_codes: list[str] | None = None
    ) -> pd.DataFrame:
        """获取门店人员数据

        数据源: proj_facana.dwd_f04_dayone_s_store_info (日实时扩充店铺信息)
        说明: 此表为门店维度的人员汇总（employee_qty），非个人明细。
              如需个人明细，需对接 HR 系统。
        """
        conditions = ["1=1"]
        params = {}

        if store_codes:
            clause, p = self._build_in_clause(store_codes, "sc", "store_no")
            conditions.append(clause)
            params.update(p)

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT
            store_no                         AS store_code,
            store_name_short                 AS store_name,
            brand_detail_abbreviation        AS brand,
            employee_qty                     AS staff_count,
            business_area                    AS business_area,
            storage_area                     AS storage_area,
            total_area                       AS total_area,
            contract_area                    AS contract_area,
            open_date                        AS opening_date,
            close_date                       AS closing_date,
            shop_category                    AS shop_category,
            business_detail                  AS business_detail,
            business_circle_name             AS commercial_circle,
            shopping_mall_name               AS mall_name,
            region_top                       AS region,
            managing_city                    AS managing_city,
            pay_method                       AS pay_method,
            self_cash_method                 AS self_cash_mode,
            reform_complete_time             AS reform_date,
            decoration_date                  AS decoration_date,
            decoration_end_date              AS decoration_end_date,
            contract_start_date              AS contract_start,
            contract_end_date                AS contract_end,
            affiliation                      AS affiliation,
            org_structure_classification     AS org_structure,
            operation_mode                   AS operation_mode,
            platform                         AS platform,
            store_type_new                   AS store_type_new,
            business_unit                    AS business_unit,
            etl_update_time                  AS etl_update_time
        FROM proj_facana.dwd_f04_dayone_s_store_info
        WHERE {where_clause}
        ORDER BY store_no
        """
        try:
            df = self._query(sql, params)
            logger.info(f"[StarRocks] 获取门店人员/基础数据: {len(df)} 行")
            return df
        except Exception as e:
            logger.error(f"[StarRocks] fetch_staff 失败: {e}")
            return pd.DataFrame()

    # ==============================================================
    # 6. 成本结构 — proj_facana.dwd_f04_dayone_countbase_pp_new
    # ==============================================================

    async def fetch_cost_structure(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        """获取成本结构数据（从日损益表按月聚合）

        数据源: proj_facana.dwd_f04_dayone_countbase_pp_new (日实时损益表-业绩版)
        包含：人工、租金、物业、折旧、促销、装修等明细费用
        """
        conditions = ["1=1"]
        params = {}

        if store_codes:
            clause, p = self._build_in_clause(store_codes, "sc", "store_no")
            conditions.append(clause)
            params.update(p)

        if start_month:
            conditions.append("SUBSTR(base_date, 1, 7) >= :start_month")
            params["start_month"] = start_month

        if end_month:
            conditions.append("SUBSTR(base_date, 1, 7) <= :end_month")
            params["end_month"] = end_month

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT
            store_no                         AS store_code,
            SUBSTR(base_date, 1, 7)          AS year_month,
            brand_detail_abbreviation        AS brand,
            -- 收入
            SUM(total_sal_amt)               AS sales_amount,
            SUM(total_prm_amt)               AS tag_price_amount,
            -- 销售成本
            SUM(taxcost)                     AS tax_cost,
            SUM(hq_taxcost)                  AS hq_tax_cost,
            SUM(notax_cost)                  AS notax_cost,
            -- 经营费用明细
            SUM(operating_exp)               AS total_operating_expense,
            SUM(salary)                      AS salary,
            SUM(labor_service_fee)           AS labor_service_fee,
            SUM(depreciation_charge)         AS depreciation,
            SUM(property_fee)                AS property_fee,
            SUM(rental_fee)                  AS rent,
            SUM(social_security_fee)         AS social_security,
            SUM(labor_insurance_fee)         AS labor_insurance,
            SUM(display_installation_fee)    AS display_installation,
            SUM(promotion_fee)               AS promotion,
            SUM(packing_charge)              AS packing,
            SUM(trade_union_funds)           AS trade_union,
            SUM(mall_charge)                 AS mall_charge,
            SUM(office_supplies)             AS office_supplies,
            SUM(repair_cost)                 AS repair,
            SUM(communication_fee)           AS communication,
            SUM(low_value_cons)              AS low_value_consumption,
            SUM(other_fee)                   AS other_fee,
            SUM(express_fee)                 AS express_fee,
            -- B管理费用
            SUM(bmanaging_exp)               AS b_managing_expense,
            SUM(managing_exp)                AS managing_expense,
            SUM(financial_exp)               AS financial_expense,
            -- 总部费用明细
            SUM(hq_salary)                   AS hq_salary,
            SUM(hq_depreciation_charge)      AS hq_depreciation,
            SUM(hq_property_fee)             AS hq_property_fee,
            SUM(hq_rental_fee)               AS hq_rent,
            SUM(hq_promotion_fee)            AS hq_promotion,
            SUM(hq_other_fee)                AS hq_other_fee,
            -- 毛利与利润
            SUM(hq_notax_gross_profit)       AS hq_notax_gross_profit,
            SUM(notax_operating_profit)      AS notax_operating_profit,
            SUM(hq_notax_operating_profit)   AS hq_notax_operating_profit,
            SUM(notax_net_profit)            AS notax_net_profit,
            SUM(net_profit)                  AS net_profit,
            -- 附加税
            SUM(additional_taxes)            AS additional_taxes,
            -- 非经常性损益
            SUM(nonoperating_income)         AS nonoperating_income,
            SUM(nonoperating_expenditure)    AS nonoperating_expenditure,
            -- 所得税
            SUM(income_tax)                  AS income_tax
        FROM proj_facana.dwd_f04_dayone_countbase_pp_new
        WHERE {where_clause}
        GROUP BY store_no, SUBSTR(base_date, 1, 7), brand_detail_abbreviation
        ORDER BY store_no, year_month
        """
        try:
            df = self._query(sql, params)
            logger.info(f"[StarRocks] 获取成本结构: {len(df)} 行")
            return df
        except Exception as e:
            logger.error(f"[StarRocks] fetch_cost_structure 失败: {e}")
            return pd.DataFrame()

    # ==============================================================
    # 辅助查询
    # ==============================================================

    async def fetch_store_loss(
        self,
        store_codes: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取门店日损益数据（含预算/同期对比）

        数据源: proj_facana.ads_fin_fact_day_storeloss_pp
        特点: 包含返利(d2_)、预算地区(d4_)、预算返利(d5_)、
              预算考核(d6_)、预算全年(d7_/d8_/d9_)、同期(d1t_)等多口径数据
        """
        conditions = ["1=1"]
        params = {}

        if store_codes:
            clause, p = self._build_in_clause(store_codes, "sc", "store_no")
            conditions.append(clause)
            params.update(p)

        if start_date:
            conditions.append("base_date >= :start_date")
            params["start_date"] = start_date.strftime("%Y-%m-%d")

        if end_date:
            conditions.append("base_date <= :end_date")
            params["end_date"] = end_date.strftime("%Y-%m-%d")

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT
            store_no                         AS store_code,
            base_date                        AS sale_date,
            brand_detail_abbreviation        AS brand,
            store_name                       AS store_name,
            region_top                       AS region,
            region                           AS sub_region,
            managing_city                    AS managing_city,
            business_city                    AS business_city,
            business_attribute               AS business_attribute,
            shop_category                    AS shop_category,
            business_detail                  AS business_detail,
            store_type_new                   AS store_type_new,
            org_structure_classification     AS channel_type,
            -- 当期实际（地区口径）
            d1_pf_total_sal_amt_pp           AS actual_sales_pp,
            d1_pf_total_sal_amt              AS actual_sales,
            d1_pf_hq_taxcost                 AS actual_cost,
            d1_pf_hq_notax_gross_profit      AS actual_gross_profit,
            d1_pf_operating_exp              AS actual_operating_expense,
            d1_pf_bmanaging_exp              AS actual_b_manage_expense,
            d1_pf_hq_notax_operating_profit  AS actual_operating_profit,
            d1_pf_comprehensive_mall_fee     AS actual_mall_fee,
            d1_pf_salary_fee                 AS actual_salary,
            d1_pf_fix_salary                 AS actual_fix_salary,
            d1_pf_float_salary               AS actual_float_salary,
            d1_pf_social_fee                 AS actual_social_fee,
            d1_pf_decorate_fee               AS actual_decorate_fee,
            d1_pf_express                    AS actual_express,
            d1_pf_all_other_fee              AS actual_other_fee,
            d1_pf_store_contribution1        AS actual_store_contribution,
            d1_pf_b_salary_social_fee        AS actual_b_salary_social,
            d1_pf_b_rental_property          AS actual_b_rental_property,
            d1_pf_b_warehousing_service      AS actual_b_warehousing,
            d1_pf_b_travel_expense           AS actual_b_travel,
            d1_pf_b_labor_insurance_benefits AS actual_b_labor_insurance,
            d1_pf_b_all_other_fee            AS actual_b_other_fee,
            -- 返利口径
            d2_total_sal_amt                 AS rebate_sales,
            d2_hq_notax_gross_profit         AS rebate_gross_profit,
            d2_operating_exp                 AS rebate_operating_expense,
            d2_hq_notax_operating_profit     AS rebate_operating_profit,
            d2_comprehensive_mall_fee        AS rebate_mall_fee,
            d2_salary_fee                    AS rebate_salary,
            -- 预算地区口径
            d4_total_sal_amt_pp              AS budget_sales_pp,
            d4_total_sal_amt                 AS budget_sales,
            d4_hq_notax_gross_profit         AS budget_gross_profit,
            d4_operating_exp                 AS budget_operating_expense,
            d4_hq_notax_operating_profit     AS budget_operating_profit,
            d4_comprehensive_mall_fee        AS budget_mall_fee,
            d4_salary_fee                    AS budget_salary,
            -- 预算考核口径
            d6_total_sal_amt_pp              AS budget_eval_sales_pp,
            d6_total_sal_amt                 AS budget_eval_sales,
            d6_hq_notax_operating_profit     AS budget_eval_operating_profit,
            -- 同期
            d1t_pf_total_sal_amt_pp          AS ly_sales_pp,
            d1t_pf_total_sal_amt             AS ly_sales,
            d1t_pf_hq_notax_gross_profit     AS ly_gross_profit,
            d1t_pf_hq_notax_operating_profit AS ly_operating_profit,
            -- ETL
            etl_update_time                  AS etl_update_time
        FROM proj_facana.ads_fin_fact_day_storeloss_pp
        WHERE {where_clause}
        ORDER BY store_no, base_date
        """
        try:
            df = self._query(sql, params)
            logger.info(f"[StarRocks] 获取门店日损益: {len(df)} 行")
            return df
        except Exception as e:
            logger.error(f"[StarRocks] fetch_store_loss 失败: {e}")
            return pd.DataFrame()

    async def fetch_pos_orders(
        self,
        store_codes: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        p_mon: str | None = None,
    ) -> pd.DataFrame:
        """获取 POS 订单明细数据

        数据源: spark_catalog.ads_pub.ads_fact_pos_ord_analysis
        注意: 店铺编码字段为 sy_org_lno（业绩归属店号）
        分区字段: p_mon (yyyymm)，必须指定以避免全表扫描
        """
        conditions = ["1=1"]
        params = {}

        if store_codes:
            clause, p = self._build_in_clause(store_codes, "sc", "sy_org_lno")
            conditions.append(clause)
            params.update(p)

        if p_mon:
            conditions.append("p_mon = :p_mon")
            params["p_mon"] = p_mon
        elif start_date:
            # 从 start_date 推导 p_mon
            conditions.append("p_mon >= :p_mon_start")
            params["p_mon_start"] = start_date.replace("-", "")[:6]

        if start_date:
            conditions.append("period_sdate >= :start_date")
            params["start_date"] = start_date.replace("-", "")

        if end_date:
            conditions.append("period_sdate <= :end_date")
            params["end_date"] = end_date.replace("-", "")

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT
            sy_org_lno                       AS store_code,
            period_sdate                     AS sale_date,
            brd_dtl_abbr                     AS brand,
            brd_dtl_no                       AS brand_code,
            pro_no                           AS product_code,
            pro_name                         AS product_name,
            pro_cate_name                    AS category,
            size_code                        AS size_code,
            order_type                       AS order_type,
            -- 销售数据
            sal_qty                          AS sales_qty,
            sal_amt                          AS sales_amount,
            sal_prm_amt                      AS tag_price_amount,
            sal_nos_prm_amt                  AS tag_price_no_material,
            -- 业绩
            sal_qty_sy                       AS perf_qty,
            sal_amt_sy                       AS perf_amount,
            sal_prm_amt_sy                   AS perf_tag_amount,
            -- 折扣
            discount_rate                    AS discount_rate,
            discount_amt                     AS discount_amount,
            -- 客流
            enter_store_qty                  AS foot_traffic,
            -- 库存
            balance_qty                      AS stock_qty,
            balance_prm_amt                  AS stock_tag_amount,
            total_inv_qty                    AS total_inv_qty,
            -- 会员
            mem_id                           AS member_id,
            level_attr                       AS member_level,
            -- 订单信息
            order_no                         AS order_no,
            pay_time                         AS pay_time,
            pay_name                         AS pay_method,
            asst_no                          AS staff_code,
            asst_name                        AS staff_name,
            -- 目标
            amt_target                       AS daily_target,
            mon_amt_target                   AS monthly_target,
            -- 渠道
            online_offline                   AS online_flag,
            order_source                     AS order_source,
            third_one_level_channel_name     AS channel_l1,
            third_two_level_channel_name     AS channel_l2,
            -- 分区
            p_mon                            AS partition_month
        FROM spark_catalog.ads_pub.ads_fact_pos_ord_analysis
        WHERE {where_clause}
        ORDER BY sy_org_lno, period_sdate
        """
        try:
            df = self._query(sql, params)
            logger.info(f"[StarRocks] 获取POS订单明细: {len(df)} 行")
            return df
        except Exception as e:
            logger.error(f"[StarRocks] fetch_pos_orders 失败: {e}")
            return pd.DataFrame()

    # ==============================================================
    # 7. 日目标数据 — dws_pub.dws_fact_day_org_target_cost
    # ==============================================================

    async def fetch_daily_target_cost(
        self,
        store_codes: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        p_mon: str | None = None,
    ) -> pd.DataFrame:
        """获取日店铺基础目标数据

        数据源: dws_pub.dws_fact_day_org_target_cost (日店铺基础目标表)
        分区字段: p_mon (YYYYMM)，必须指定以避免全表扫描
        """
        conditions = ["1=1"]
        params = {}

        if store_codes:
            clause, p = self._build_in_clause(store_codes, "sc", "org_lno")
            conditions.append(clause)
            params.update(p)

        if p_mon:
            conditions.append("p_mon = :p_mon")
            params["p_mon"] = p_mon
        elif start_date:
            conditions.append("p_mon >= :p_mon_start")
            params["p_mon_start"] = start_date.strftime("%Y%m")

        if start_date:
            conditions.append("period_sdate >= :start_date")
            params["start_date"] = start_date.strftime("%Y%m%d")

        if end_date:
            conditions.append("period_sdate <= :end_date")
            params["end_date"] = end_date.strftime("%Y%m%d")

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT
            org_lno                AS store_code,
            period_sdate           AS target_date,
            brd_dtl_no             AS brand_code,
            store_brd              AS store_brand,
            day_amt_target         AS daily_sales_target,
            mon_amt_target         AS monthly_sales_target,
            year_amt_target        AS yearly_sales_target,
            cust_sal_nos_qty_target AS customer_qty_target,
            cust_sal_price_target  AS customer_price_target,
            avg_price_target       AS avg_price_target,
            virtual_mon_amt_target AS virtual_monthly_target,
            clg_mon_amt_target     AS challenge_monthly_target,
            offline_mon_amt_target AS offline_monthly_target,
            sy_mon_amt_target      AS private_domain_target,
            live_mon_amt_target    AS live_stream_target,
            wholesale_amt_target   AS wholesale_target,
            p_mon                  AS partition_month
        FROM dws_pub.dws_fact_day_org_target_cost
        WHERE {where_clause}
        ORDER BY org_lno, period_sdate
        """
        try:
            df = self._query(sql, params)
            logger.info(f"[StarRocks] 获取日目标数据: {len(df)} 行")
            return df
        except Exception as e:
            logger.error(f"[StarRocks] fetch_daily_target_cost 失败: {e}")
            return pd.DataFrame()

    # ==============================================================
    # 8. 开关状态矩阵 — dws_pub.dws_dim_org_on_off
    # ==============================================================

    async def fetch_switch_status(
        self,
        store_codes: list[str] | None = None,
        target_month: str | None = None,
    ) -> pd.DataFrame:
        """获取门店开关状态矩阵

        数据源: dws_pub.dws_dim_org_on_off (店铺开改关表)
        返回格式: store_code, year_month, status ("on"/"off"/"renovating")

        逻辑：
          - on_off_type = '开店' AND real_time 已到 → on
          - on_off_type = '关店' AND real_time 已到 → off
          - on_off_type = '改造' AND real_time 已到 → renovating
          - plan_time 在目标月内 → 计划中（按 plan 状态处理）
        """
        conditions = ["1=1"]
        params = {}

        if store_codes:
            clause, p = self._build_in_clause(store_codes, "sc", "org_lno")
            conditions.append(clause)
            params.update(p)

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT
            org_lno                AS store_code,
            org_name               AS store_name,
            brd_dtl_no             AS brand_code,
            on_off_type            AS event_type,
            plan_time              AS plan_time,
            real_time              AS actual_time,
            region_name            AS region,
            biz_city_name          AS city,
            biz_area               AS store_area,
            mon_avg_sal_amt        AS avg_monthly_sales,
            diff_status            AS diff_status,
            last_plan_time         AS latest_plan_time
        FROM dws_pub.dws_dim_org_on_off
        WHERE {where_clause}
        ORDER BY org_lno, plan_time
        """
        try:
            df = self._query(sql, params)
            logger.info(f"[StarRocks] 获取开关状态: {len(df)} 行")

            if df.empty:
                return pd.DataFrame(columns=["store_code", "year_month", "status"])

            # 转换为月度状态矩阵
            return self._build_switch_matrix(df, target_month)
        except Exception as e:
            logger.error(f"[StarRocks] fetch_switch_status 失败: {e}")
            return pd.DataFrame(columns=["store_code", "year_month", "status"])

    def _build_switch_matrix(
        self, raw_df: pd.DataFrame, target_month: str | None = None
    ) -> pd.DataFrame:
        """将开改关事件表转换为月度状态矩阵

        输入: 原始事件表 (store_code, event_type, plan_time, actual_time, ...)
        输出: 月度状态表 (store_code, year_month, status)
        """
        from datetime import datetime

        import pandas as pd

        # 确定要生成的月份范围
        today = date.today()
        if target_month:
            months = [target_month]
        else:
            # 生成近 6 个月 + 未来 3 个月
            months = []
            for offset in range(-5, 4):
                d = today.replace(day=1)
                if offset >= 0:
                    for _ in range(offset):
                        if d.month == 12:
                            d = d.replace(year=d.year + 1, month=1)
                        else:
                            d = d.replace(month=d.month + 1)
                else:
                    for _ in range(-offset):
                        if d.month == 1:
                            d = d.replace(year=d.year - 1, month=12)
                        else:
                            d = d.replace(month=d.month - 1)
                months.append(d.strftime("%Y-%m"))

        # 按门店构建状态映射
        records = []
        for store_code, group in raw_df.groupby("store_code"):
            # 解析事件时间线
            events = []
            for _, row in group.iterrows():
                event_type = str(row.get("event_type", ""))
                plan_time = str(row.get("plan_time", ""))
                actual_time = str(row.get("actual_time", ""))

                # 确定事件日期（优先用实际时间）
                event_date = actual_time if actual_time and actual_time != "None" else plan_time
                if not event_date or event_date == "None":
                    continue

                # 解析日期
                for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
                    try:
                        event_date = datetime.strptime(event_date[:10], fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    continue

                # 映射事件类型
                if "开" in event_type:
                    status = "on"
                elif "关" in event_type:
                    status = "off"
                elif "改" in event_type or "装修" in event_type:
                    status = "renovating"
                else:
                    continue

                events.append((event_date, status))

            events.sort(key=lambda x: x[0])

            # 对每个月确定状态
            for ym in months:
                y, m = int(ym[:4]), int(ym[5:7])
                # 月末日期
                if m == 12:
                    month_end = date(y + 1, 1, 1) - pd.Timedelta(days=1)
                else:
                    month_end = date(y, m + 1, 1) - pd.Timedelta(days=1)

                # 找到该月之前（含）最近的事件
                current_status = "on"  # 默认开业
                for event_date, status in events:
                    if event_date <= month_end:
                        current_status = status
                    else:
                        break

                records.append({
                    "store_code": store_code,
                    "year_month": ym,
                    "status": current_status,
                })

        return pd.DataFrame(records)
