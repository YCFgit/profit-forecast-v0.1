"""门店管理路由"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from src.db import get_db
from src.db.models import Store

router = APIRouter()

# 状态中文映射
STATUS_LABELS = {
    "active": "营业中",
    "closed": "已关闭",
    "renovating": "改装中",
    "pre_open": "未开业",
}


@router.get("/summary")
def get_store_summary(db: Session = Depends(get_db)):
    """获取门店汇总统计（按状态分类）"""
    # 按状态分组统计
    result = db.execute(
        select(Store.status, func.count(Store.id).label("cnt"))
        .group_by(Store.status)
    )
    status_counts = {row.status: row.cnt for row in result}

    total = sum(status_counts.values())
    active = status_counts.get("active", 0)
    closed = status_counts.get("closed", 0)
    renovating = status_counts.get("renovating", 0)
    pre_open = status_counts.get("pre_open", 0)

    # 总面积（仅营业中门店）
    total_area = db.scalar(
        select(func.coalesce(func.sum(Store.store_area), 0))
        .where(Store.status == "active")
    ) or 0

    return {
        "total": total,
        "by_status": {
            "active": {"count": active, "label": "营业中"},
            "closed": {"count": closed, "label": "已关闭"},
            "renovating": {"count": renovating, "label": "改装中"},
            "pre_open": {"count": pre_open, "label": "未开业"},
        },
        "active_area": float(total_area),
    }


@router.get("/")
def list_stores(
    status: str | None = None,
    region: str | None = None,
    commercial_tier: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
):
    """查询门店列表

    支持筛选：
    - status: 状态 (active/closed/renovating/pre_open)
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
    result = db.execute(query)
    stores = result.scalars().all()

    return {
        "total": len(stores),
        "stores": [
            {
                "store_code": s.store_code,
                "store_name": s.store_name,
                "store_short_name": s.store_short_name,
                "brand": s.brand,
                "store_type": s.store_type,
                "channel_l1": s.channel_l1,
                "channel_l2": s.channel_l2,
                "channel_l3": s.channel_l3,
                "region": s.region,
                "sub_region": s.sub_region,
                "province": s.province,
                "city": s.city,
                "city_level": s.city_level,
                "business_attribute": s.business_attribute,
                "business_category": s.business_category,
                "commercial_tier": s.commercial_tier,
                "store_area": float(s.store_area) if s.store_area else None,
                "total_area": float(s.total_area) if s.total_area else None,
                "staff_count": s.staff_count,
                "is_new_store": s.is_new_store,
                "cooperation_mode": s.cooperation_mode,
                "status": s.status,
                "status_label": STATUS_LABELS.get(s.status, s.status),
            }
            for s in stores
        ],
    }


@router.get("/{store_code}")
def get_store(store_code: str, db: Session = Depends(get_db)):
    """查询单个门店详情"""
    result = db.execute(select(Store).where(Store.store_code == store_code))
    store = result.scalar_one_or_none()

    if not store:
        raise HTTPException(status_code=404, detail=f"门店 {store_code} 不存在")

    return {
        "store_code": store.store_code,
        "store_name": store.store_name,
        "store_short_name": store.store_short_name,
        "brand": store.brand,
        "store_type": store.store_type,
        "channel_l1": store.channel_l1,
        "channel_l2": store.channel_l2,
        "channel_l3": store.channel_l3,
        "region": store.region,
        "sub_region": store.sub_region,
        "province": store.province,
        "city": store.city,
        "city_level": store.city_level,
        "business_attribute": store.business_attribute,
        "business_category": store.business_category,
        "commercial_tier": store.commercial_tier,
        "store_area": float(store.store_area) if store.store_area else None,
        "total_area": float(store.total_area) if store.total_area else None,
        "opening_date": str(store.opening_date) if store.opening_date else None,
        "closing_date": str(store.closing_date) if store.closing_date else None,
        "actual_open_date": str(store.actual_open_date) if store.actual_open_date else None,
        "is_new_store": store.is_new_store,
        "cooperation_mode": store.cooperation_mode,
        "commercial_circle": store.commercial_circle,
        "status": store.status,
        "status_label": STATUS_LABELS.get(store.status, store.status),
        "staff_count": store.staff_count,
    }
