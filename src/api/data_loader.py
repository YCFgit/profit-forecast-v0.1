"""带缓存的数据加载器

所有路由共用，避免重复查 MySQL。
"""

import pandas as pd
from loguru import logger

from src.api.cache import data_cache
from src.data.collectors.factory import create_collector


async def load_stores() -> pd.DataFrame:
    """加载门店数据（带缓存）"""
    cached = data_cache.get("stores")
    if cached is not None:
        return cached
    collector = create_collector("mysql")
    async with collector:
        df = await collector.fetch_stores()
    data_cache.set("stores", df)
    logger.info(f"[Cache] 加载门店数据: {len(df)} 条")
    return df


async def load_monthly_metrics() -> pd.DataFrame:
    """加载月度指标（带缓存）"""
    cached = data_cache.get("monthly_metrics")
    if cached is not None:
        return cached
    collector = create_collector("mysql")
    async with collector:
        df = await collector.fetch_monthly_metrics()
    data_cache.set("monthly_metrics", df)
    logger.info(f"[Cache] 加载月度指标: {len(df)} 条")
    return df


async def load_daily_sales() -> pd.DataFrame:
    """加载日销数据（带缓存）"""
    cached = data_cache.get("daily_sales")
    if cached is not None:
        return cached
    collector = create_collector("mysql")
    async with collector:
        df = await collector.fetch_daily_sales()
    data_cache.set("daily_sales", df)
    logger.info(f"[Cache] 加载日销数据: {len(df)} 条")
    return df


async def load_switch_status() -> pd.DataFrame:
    """加载开关状态（带缓存）"""
    cached = data_cache.get("switch_status")
    if cached is not None:
        return cached
    collector = create_collector("mysql")
    async with collector:
        df = await collector.fetch_switch_status()
    data_cache.set("switch_status", df)
    logger.info(f"[Cache] 加载开关状态: {len(df)} 条")
    return df


async def load_all_data() -> dict:
    """一次性加载所有数据（带缓存）"""
    stores = await load_stores()
    monthly = await load_monthly_metrics()
    daily = await load_daily_sales()
    switch = await load_switch_status()
    return {
        "stores": stores,
        "monthly_metrics": monthly,
        "daily_sales": daily,
        "switch_status": switch,
    }
