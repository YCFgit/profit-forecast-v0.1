"""数据导入路由 — 从数据源采集并写入数据库"""

import io

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.config import get_settings
from src.data.collectors.factory import create_collector
from src.data.validators.quality_checker import run_quality_check
from src.db import get_db
from src.db.models import Store, StoreDailySales, StoreMonthlyMetrics, StoreStaff, StoreTarget, CostStructure

router = APIRouter()


@router.post("/from-source")
async def import_from_source(db: AsyncSession = Depends(get_db)):
    """从配置的数据源（DataWorks/Mock）导入数据

    流程：
    1. 创建采集器（根据 DATAWORKS_ADAPTER 配置自动选择）
    2. 采集各维度数据
    3. 数据质量检查
    4. 写入数据库
    """
    collector = create_collector()

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

        # 2. 写入门店数据（upsert）
        store_count = 0
        for _, row in stores_df.iterrows():
            stmt = pg_insert(Store).values(
                store_code=row["store_code"],
                store_name=row["store_name"],
                store_type=row.get("store_type", "direct"),
                channel_code=row.get("channel_code"),
                region=row.get("region"),
                province=row.get("province"),
                city=row.get("city"),
                commercial_tier=row.get("commercial_tier", "B"),
                store_area=row.get("store_area"),
                opening_date=row.get("opening_date"),
                status=row.get("status", "active"),
                staff_count=row.get("staff_count"),
            ).on_conflict_do_update(
                index_elements=["store_code"],
                set_={
                    "store_name": row["store_name"],
                    "store_type": row.get("store_type", "direct"),
                    "region": row.get("region"),
                    "commercial_tier": row.get("commercial_tier", "B"),
                    "store_area": row.get("store_area"),
                    "status": row.get("status", "active"),
                    "staff_count": row.get("staff_count"),
                },
            )
            await db.execute(stmt)
            store_count += 1

        await db.commit()
        logger.info(f"[导入] 门店数据: {store_count} 条")

        # 3. 采集日销数据
        sales_df = await collector.fetch_daily_sales()
        if not sales_df.empty:
            sales_count = 0
            for _, row in sales_df.iterrows():
                stmt = pg_insert(StoreDailySales).values(
                    store_code=row["store_code"],
                    sale_date=row["sale_date"],
                    category_code=row.get("category_code"),
                    channel_code=row.get("channel_code"),
                    sales_amount=row["sales_amount"],
                    sales_qty=row["sales_qty"],
                    avg_price=row.get("avg_price"),
                    return_amount=row.get("return_amount", 0),
                    return_qty=row.get("return_qty", 0),
                    customer_count=row.get("customer_count", 0),
                ).on_conflict_do_nothing()
                await db.execute(stmt)
                sales_count += 1
                if sales_count % 1000 == 0:
                    await db.commit()

            await db.commit()
            logger.info(f"[导入] 日销数据: {sales_count} 条")
        else:
            sales_count = 0

        # 4. 采集月度指标
        metrics_df = await collector.fetch_monthly_metrics()
        if not metrics_df.empty:
            metrics_count = 0
            for _, row in metrics_df.iterrows():
                stmt = pg_insert(StoreMonthlyMetrics).values(
                    store_code=row["store_code"],
                    year_month=row["year_month"],
                    sales_amount=row.get("sales_amount"),
                    gross_profit=row.get("gross_profit"),
                    gross_margin=row.get("gross_margin"),
                    sales_per_sqm=row.get("sales_per_sqm"),
                    revenue_per_staff=row.get("revenue_per_staff"),
                    avg_ticket=row.get("avg_ticket"),
                    return_rate=row.get("return_rate"),
                    staff_count=row.get("staff_count"),
                ).on_conflict_do_nothing()
                await db.execute(stmt)
                metrics_count += 1

            await db.commit()
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
    db: AsyncSession = Depends(get_db),
):
    """从 Excel 文件导入数据

    Args:
        file: 上传的 Excel 文件
        data_type: 数据类型 (stores | daily_sales | monthly_metrics | staff | targets | costs)
    """
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))
    logger.info(f"[Excel] 读取 {file.filename}: {len(df)} 行, {data_type}")

    # 数据质量检查
    critical_cols_map = {
        "stores": ["store_code", "store_name"],
        "daily_sales": ["store_code", "sale_date", "sales_amount"],
        "monthly_metrics": ["store_code", "year_month"],
        "staff": ["store_code", "staff_name"],
        "targets": ["store_code", "sales_target"],
        "costs": ["store_code", "year_month"],
    }
    critical = critical_cols_map.get(data_type, [])
    for col in critical:
        if col not in df.columns:
            return {"status": "error", "message": f"缺少关键字段: {col}"}

    quality = run_quality_check(df, name=f"Excel-{data_type}", critical_cols=critical)

    # 写入数据库（简化版，仅示例 stores）
    count = 0
    if data_type == "stores":
        for _, row in df.iterrows():
            stmt = pg_insert(Store).values(
                store_code=str(row["store_code"]),
                store_name=str(row["store_name"]),
                store_type=str(row.get("store_type", "direct")),
                region=str(row.get("region", "")) if pd.notna(row.get("region")) else None,
                commercial_tier=str(row.get("commercial_tier", "B")),
                store_area=float(row["store_area"]) if pd.notna(row.get("store_area")) else None,
                status="active",
            ).on_conflict_do_update(
                index_elements=["store_code"],
                set_={"store_name": str(row["store_name"]), "status": "active"},
            )
            await db.execute(stmt)
            count += 1
        await db.commit()

    return {
        "status": "success",
        "data_type": data_type,
        "rows_imported": count,
        "quality": {"is_clean": quality.is_clean, "errors": quality.errors},
    }
