"""MySQL 异步采集器适配器

将 MySQLCollector 的同步方法包装为 BaseCollector 的异步接口，
使 allocation / risk / forecast 等路由可以通过 create_collector("mysql") 使用 MySQL 数据。
"""

import pandas as pd

from src.data.collectors.base import BaseCollector
from src.data.collectors.mysql_collector import MySQLCollector


class MySQLBaseCollector(BaseCollector):
    """基于 MySQL 的数据采集器（适配 BaseCollector 异步接口）"""

    def __init__(self):
        self._inner = MySQLCollector()

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def fetch_stores(self) -> pd.DataFrame:
        return self._inner.collect_stores()

    async def fetch_monthly_metrics(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        return self._inner.collect_monthly_metrics(
            store_codes=store_codes,
            start_month=start_month,
            end_month=end_month,
            active_only=True,
        )

    async def fetch_daily_sales(
        self,
        store_codes: list[str] | None = None,
        start_date=None,
        end_date=None,
    ) -> pd.DataFrame:
        return pd.DataFrame()

    async def fetch_targets(
        self,
        store_codes: list[str] | None = None,
        target_type: str = "monthly",
        target_month: str | None = None,
    ) -> pd.DataFrame:
        return self._inner.collect_targets(
            store_codes=store_codes,
            target_month=target_month,
        )

    async def fetch_staff(self, store_codes: list[str] | None = None) -> pd.DataFrame:
        return pd.DataFrame()

    async def fetch_cost_structure(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        return self._inner.collect_cost_structure(
            store_codes=store_codes,
            start_month=start_month,
            end_month=end_month,
            active_only=True,
        )

    async def fetch_switch_status(
        self,
        target_month: str | None = None,
    ) -> pd.DataFrame:
        """开关状态数据（MySQL 中无此表，返回空 DataFrame）"""
        return pd.DataFrame()
