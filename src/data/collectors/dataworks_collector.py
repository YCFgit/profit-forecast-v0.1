"""DataWorks / MaxCompute 数据采集器

支持三种接入方式：
1. DataWorks Open API — 通过 HTTP API 拉取数据
2. MaxCompute (ODPS) 直连 — 通过 pyodps 查询底层表
3. 数据库同步 — 从 DataWorks 同步到的中间库读取

使用方式：
    collector = DataWorksCollector(adapter_type="dataworks_api")
    async with collector:
        stores = await collector.fetch_stores()
"""

from datetime import date

import pandas as pd
from loguru import logger

from src.core.config import get_settings
from src.data.collectors.base import BaseCollector


class DataWorksCollector(BaseCollector):
    """DataWorks 数据采集器 — 生产环境使用

    配置项（通过 .env 或环境变量）：
        DATAWORKS_ADAPTER: dataworks_api | maxcompute | database
        DATAWORKS_ACCESS_KEY_ID: 阿里云 AccessKey ID
        DATAWORKS_ACCESS_KEY_SECRET: 阿里云 AccessKey Secret
        DATAWORKS_PROJECT: DataWorks 项目名
        DATAWORKS_ENDPOINT: MaxCompute Endpoint
    """

    def __init__(self, adapter_type: str | None = None):
        settings = get_settings()
        self.adapter_type = adapter_type or settings.dataworks_adapter
        self.ak_id = settings.dataworks_access_key_id
        self.ak_secret = settings.dataworks_access_key_secret
        self.project = settings.dataworks_project
        self.endpoint = settings.dataworks_endpoint
        self._client = None

    async def connect(self) -> None:
        logger.info(f"[DataWorks] 连接方式: {self.adapter_type}")

        if self.adapter_type == "dataworks_api":
            await self._connect_api()
        elif self.adapter_type == "maxcompute":
            await self._connect_maxcompute()
        elif self.adapter_type == "database":
            await self._connect_database()
        else:
            raise ValueError(f"不支持的接入方式: {self.adapter_type}")

    async def _connect_api(self):
        """通过 DataWorks Open API 连接"""
        # TODO: 实现 DataWorks Open API 客户端
        # 需要安装: pip install alibabacloud-dataworks-public20200518
        logger.info("[DataWorks API] 连接中...")
        logger.warning("[DataWorks API] 尚未实现，请配置具体 API 调用逻辑")

    async def _connect_maxcompute(self):
        """通过 MaxCompute (ODPS) 直连"""
        # TODO: 实现 MaxCompute 连接
        # 需要安装: pip install pyodps
        logger.info("[MaxCompute] 连接中...")
        logger.warning("[MaxCompute] 尚未实现，请配置 pyodps 连接逻辑")

    async def _connect_database(self):
        """从 DataWorks 同步到的中间数据库读取"""
        # TODO: 实现中间库连接
        logger.info("[Database] 连接中间数据库...")
        logger.warning("[Database] 尚未实现，请配置中间库连接逻辑")

    async def disconnect(self) -> None:
        if self._client:
            logger.info("[DataWorks] 断开连接")
            self._client = None

    async def fetch_stores(self) -> pd.DataFrame:
        """从 DataWorks 获取门店主数据

        TODO: 实际对接时，需要：
        1. 确认 DataWorks 中门店表的表名和字段映射
        2. 实现 SQL 查询或 API 调用
        3. 字段名映射到标准格式
        """
        logger.warning("[DataWorks] fetch_stores 尚未实现，请根据实际表结构补充")
        return pd.DataFrame()

    async def fetch_daily_sales(
        self,
        store_codes: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """从 DataWorks 获取日销数据

        TODO: 确认 DataWorks 中的表名，例如：
        - ods_store_daily_sales
        - dwd_store_sale_detail
        """
        logger.warning("[DataWorks] fetch_daily_sales 尚未实现")
        return pd.DataFrame()

    async def fetch_monthly_metrics(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        logger.warning("[DataWorks] fetch_monthly_metrics 尚未实现")
        return pd.DataFrame()

    async def fetch_targets(
        self,
        store_codes: list[str] | None = None,
        target_type: str = "monthly",
        target_month: str | None = None,
    ) -> pd.DataFrame:
        logger.warning("[DataWorks] fetch_targets 尚未实现")
        return pd.DataFrame()

    async def fetch_staff(self, store_codes: list[str] | None = None) -> pd.DataFrame:
        logger.warning("[DataWorks] fetch_staff 尚未实现")
        return pd.DataFrame()

    async def fetch_cost_structure(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        logger.warning("[DataWorks] fetch_cost_structure 尚未实现")
        return pd.DataFrame()

    async def fetch_store_loss(
        self,
        store_codes: list[str] | None = None,
        start_date=None,
        end_date=None,
    ) -> pd.DataFrame:
        logger.warning("[DataWorks] fetch_store_loss 尚未实现")
        return pd.DataFrame()
