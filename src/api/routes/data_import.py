"""数据导入路由 — 从数据源采集并写入数据库"""

import io

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.collectors.factory import create_collector
from src.data.storage.factory import create_storage
from src.data.validators.quality_checker import run_quality_check
from src.db import get_db

router = APIRouter()


@router.post("/from-source")
async def import_from_source():
    """从配置的数据源（DataWorks/Mock）导入数据

    流程：
    1. 创建采集器（根据 DATAWORKS_ADAPTER 配置自动选择）
    2. 采集各维度数据
    3. 数据质量检查
    4. 写入存储后端
    """
    collector = create_collector()
    storage = create_storage()

    async with collector:
        # 1. 采集门店数据
        stores_df = await collector.fetch_stores()
        if stores_df.empty:
            return {"status": "error", "message": "未采集到门店数据"}

        quality = run_quality_check(
            stores_df, name="门店数据",
            critical_cols=["store_code", "store_name"],
            duplicate_subset=["store_code"],
        )

        # 2. 写入门店数据
        store_count = storage.write_stores(stores_df)
        logger.info(f"[导入] 门店数据: {store_count} 条")

        # 3. 采集日销数据
        sales_df = await collector.fetch_daily_sales()
        if not sales_df.empty:
            sales_count = storage.write_daily_sales(sales_df)
            logger.info(f"[导入] 日销数据: {sales_count} 条")
        else:
            sales_count = 0

        # 4. 采集月度指标
        metrics_df = await collector.fetch_monthly_metrics()
        if not metrics_df.empty:
            metrics_count = storage.write_monthly_metrics(metrics_df)
            logger.info(f"[导入] 月度指标: {metrics_count} 条")
        else:
            metrics_count = 0

    return {
        "status": "success",
        "data": {
            "stores": store_count,
            "daily_sales": sales_count,
            "monthly_metrics": metrics_count,
        },
        "quality": {
            "is_clean": quality.is_clean,
            "errors": quality.errors,
        },
    }


@router.post("/from-excel")
async def import_from_excel(
    file: UploadFile = File(...),
    data_type: str = "stores",
):
    """从 Excel 文件导入数据

    Args:
        file: 上传的 Excel 文件
        data_type: 数据类型 (stores | daily_sales | monthly_metrics)
    """
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))
    logger.info(f"[Excel] 读取 {file.filename}: {len(df)} 行, {data_type}")

    # 数据质量检查
    critical_cols_map = {
        "stores": ["store_code", "store_name"],
        "daily_sales": ["store_code", "sale_date", "sales_amount"],
        "monthly_metrics": ["store_code", "year_month"],
    }
    critical = critical_cols_map.get(data_type, [])
    for col in critical:
        if col not in df.columns:
            return {"status": "error", "message": f"缺少关键字段: {col}"}

    quality = run_quality_check(df, name=f"Excel-{data_type}", critical_cols=critical)

    # 写入存储后端
    storage = create_storage()
    count = 0

    if data_type == "stores":
        count = storage.write_stores(df)
    elif data_type == "daily_sales":
        count = storage.write_daily_sales(df)
    elif data_type == "monthly_metrics":
        count = storage.write_monthly_metrics(df)
    else:
        return {"status": "error", "message": f"不支持的数据类型: {data_type}"}

    return {
        "status": "success",
        "data_type": data_type,
        "rows_imported": count,
        "quality": {"is_clean": quality.is_clean, "errors": quality.errors},
    }
