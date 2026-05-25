"""数据采集器基类 — 适配器模式"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

import pandas as pd
from loguru import logger


class BaseCollector(ABC):
    """数据采集器抽象基类

    所有数据源适配器（DataWorks API、MaxCompute、数据库、Excel、Mock）
    都继承此类，实现统一的接口。
    """

    @abstractmethod
    async def connect(self) -> None:
        """建立连接"""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """关闭连接"""
        ...

    @abstractmethod
    async def fetch_stores(self) -> pd.DataFrame:
        """获取门店主数据

        Returns:
            DataFrame with columns: store_code, store_name, store_type, region,
            province, city, commercial_tier, store_area, opening_date, status, ...
        """
        ...

    @abstractmethod
    async def fetch_daily_sales(
        self,
        store_codes: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取门店日销数据

        Args:
            store_codes: 门店编码列表，None=全部
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with columns: store_code, sale_date, category_code,
            sales_amount, sales_qty, avg_price, return_amount, ...
        """
        ...

    @abstractmethod
    async def fetch_monthly_metrics(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        """获取门店月度指标

        Returns:
            DataFrame with columns: store_code, year_month, sales_amount,
            gross_profit, gross_margin, sales_per_sqm, avg_ticket, ...
        """
        ...

    @abstractmethod
    async def fetch_targets(
        self,
        store_codes: list[str] | None = None,
        target_type: str = "monthly",
        target_month: str | None = None,
    ) -> pd.DataFrame:
        """获取目标数据

        Returns:
            DataFrame with columns: store_code, target_type, target_date,
            target_month, sales_target, profit_target, ...
        """
        ...

    @abstractmethod
    async def fetch_staff(
        self,
        store_codes: list[str] | None = None,
    ) -> pd.DataFrame:
        """获取门店人员数据

        Returns:
            DataFrame with columns: store_code, staff_name, role,
            base_salary, commission_rate, hire_date, status, ...
        """
        ...

    @abstractmethod
    async def fetch_cost_structure(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        """获取成本结构数据

        Returns:
            DataFrame with columns: store_code, year_month, procurement_cost,
            labor_cost, rent_cost, logistics_cost, marketing_cost, ...
        """
        ...

    async def fetch_daily_target_cost(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        """获取日店铺基础目标数据 (dws_pub.dws_fact_day_org_target_cost)

        Returns:
            DataFrame with columns: store_code, period_sdate, day_amt_target,
            mon_amt_target, p_mon, ...
        """
        return pd.DataFrame()

    async def fetch_switch_status(
        self,
        target_month: str | None = None,
    ) -> pd.DataFrame:
        """获取开关状态矩阵 (dws_pub.dws_dim_org_on_off)

        Args:
            target_month: 目标月份 (YYYY-MM)，用于筛选

        Returns:
            DataFrame with columns: store_code, on_off_type, plan_time,
            real_time, region_name, ...
        """
        return pd.DataFrame()

    async def fetch_store_loss(
        self,
        store_codes: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """获取门店日损益数据（含多口径：业绩/返利/预算/同期）

        数据源: ads_fin_fact_day_storeloss_pp
        Returns:
            DataFrame with columns: store_code, sale_date, brand,
            actual_sales_pp, actual_cost, actual_gross_profit,
            actual_salary, actual_social_fee, actual_operating_expense,
            actual_b_manage_expense, actual_mall_fee, actual_express,
            actual_other_fee, actual_decorate_fee, actual_operating_profit,
            rebate_sales, budget_sales_pp, ly_sales_pp...
        """
        return pd.DataFrame()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
