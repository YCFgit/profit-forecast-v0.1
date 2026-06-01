"""数据采集器工厂 — 根据配置自动选择适配器"""

from src.core.config import get_settings
from src.data.collectors.base import BaseCollector


def create_collector(adapter_type: str | None = None) -> BaseCollector:
    """创建数据采集器实例

    Args:
        adapter_type: 适配器类型，None 时从配置读取
            - mock: 模拟数据（开发测试用）
            - dataworks_api: DataWorks Open API
            - maxcompute: MaxCompute 直连
            - database: 中间数据库

    Returns:
        BaseCollector 子类实例
    """
    if adapter_type is None:
        adapter_type = get_settings().dataworks_adapter

    if adapter_type == "mock":
        from src.data.collectors.mock_collector import MockCollector
        return MockCollector()
    elif adapter_type == "mysql":
        from src.data.collectors.mysql_base_collector import MySQLBaseCollector
        return MySQLBaseCollector()
    elif adapter_type == "starrocks":
        from src.data.collectors.starrocks_collector import StarRocksCollector
        return StarRocksCollector()
    elif adapter_type in ("dataworks_api", "maxcompute", "database"):
        from src.data.collectors.dataworks_collector import DataWorksCollector
        return DataWorksCollector(adapter_type=adapter_type)
    else:
        raise ValueError(
            f"未知的适配器类型: {adapter_type}，可选: mock | mysql | starrocks | dataworks_api | maxcompute | database"
        )
