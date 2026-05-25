"""门店管理路由"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.models import Store

router = APIRouter()


@router.get("/")
async def list_stores(
    status: str = "active",
    region: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """查询门店列表"""
    query = select(Store).where(Store.status == status)
    if region:
        query = query.where(Store.region == region)

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
                "city": s.city,
                "commercial_tier": s.commercial_tier,
                "store_area": float(s.store_area) if s.store_area else None,
                "staff_count": s.staff_count,
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
        return {"error": f"门店 {store_code} 不存在"}, 404

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
