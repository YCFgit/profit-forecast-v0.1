"""门店管理路由"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.models import Store

router = APIRouter()


@router.get("/summary")
async def get_store_summary(db: AsyncSession = Depends(get_db)):
    """获取门店汇总统计"""
    # 总数
    total = await db.scalar(select(func.count(Store.id)))
    # 营业中
    active = await db.scalar(
        select(func.count(Store.id)).where(Store.status == "active")
    )
    # 总人数
    total_staff = await db.scalar(
        select(func.coalesce(func.sum(Store.staff_count), 0))
    )
    # 总面积
    total_area = await db.scalar(
        select(func.coalesce(func.sum(Store.store_area), 0))
    )

    return {
        "total": total or 0,
        "active": active or 0,
        "total_staff": total_staff or 0,
        "total_area": float(total_area or 0),
    }


@router.get("/")
async def list_stores(
    status: str | None = None,
    region: str | None = None,
    commercial_tier: str | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """查询门店列表

    支持筛选：
    - status: 状态 (active/closed/renovating)
    - region: 区域
    - commercial_tier: 商圈等级 (A/B/C/D)
    - keyword: 搜索关键词（匹配编码/名称）
    """
    query = select(Store)

    # 筛选条件
    if status:
        query = query.where(Store.status == status)
    if region:
        query = query.where(Store.region == region)
    if commercial_tier:
        query = query.where(Store.commercial_tier == commercial_tier)
    if keyword:
        query = query.where(
            or_(
                Store.store_code.contains(keyword),
                Store.store_name.contains(keyword),
            )
        )

    query = query.order_by(Store.store_code)
    result = await db.execute(query)
    stores = result.scalars().all()

    return {
        "total": len(stores),
        "stores": [
            {
                "store_code": s.store_code,
                "store_name": s.store_name,
                "store_type": s.store_type,
                "region": s.region,
                "province": s.province,
                "city": s.city,
                "commercial_tier": s.commercial_tier,
                "store_area": float(s.store_area) if s.store_area else None,
                "staff_count": s.staff_count,
                "status": s.status,
            }
            for s in stores
        ],
    }


@router.get("/{store_code}")
async def get_store(store_code: str, db: AsyncSession = Depends(get_db)):
    """查询单个门店详情"""
    result = await db.execute(select(Store).where(Store.store_code == store_code))
    store = result.scalar_one_or_none()

    if not store:
        raise HTTPException(status_code=404, detail=f"门店 {store_code} 不存在")

    return {
        "store_code": store.store_code,
        "store_name": store.store_name,
        "store_type": store.store_type,
        "region": store.region,
        "province": store.province,
        "city": store.city,
        "commercial_tier": store.commercial_tier,
        "store_area": float(store.store_area) if store.store_area else None,
        "opening_date": str(store.opening_date) if store.opening_date else None,
        "status": store.status,
        "staff_count": store.staff_count,
    }
