"""基线预估路由"""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.agents.baseline_agent import BaselineAgent
from src.api.data_loader import load_stores, load_monthly_metrics, load_daily_sales, load_switch_status
from src.api.cache import result_cache

router = APIRouter()


class ForecastResponse(BaseModel):
    status: str
    store_count: int
    avg_mape: float
    baselines: dict[str, float]
    model_info: dict[str, dict]


@router.get("/baselines", response_model=ForecastResponse)
async def get_baselines():
    """获取所有门店的基线预估"""
    cached = result_cache.get("baselines")
    if cached:
        return cached

    stores = await load_stores()
    monthly_metrics = await load_monthly_metrics()
    daily_sales = await load_daily_sales()
    switch_status = await load_switch_status()

    agent = BaselineAgent()
    result = agent.forecast(
        monthly_metrics=monthly_metrics,
        stores_df=stores,
        daily_sales=daily_sales,
        switch_status=switch_status,
    )

    response = ForecastResponse(
        status="success",
        store_count=result.store_count,
        avg_mape=round(result.avg_mape, 4),
        baselines={k: round(v, 0) for k, v in result.baselines.items()},
        model_info=result.model_info,
    )
    result_cache.set("baselines", response)
    return response


@router.get("/baselines/{store_code}")
async def get_store_baseline(store_code: str):
    """获取单门店的基线预估详情"""
    stores = await load_stores()
    monthly_metrics = await load_monthly_metrics()

    agent = BaselineAgent()
    result = agent.forecast(
        monthly_metrics=monthly_metrics,
        stores_df=stores,
    )

    if store_code not in result.baselines:
        return {"status": "error", "message": f"门店 {store_code} 无数据"}

    return {
        "status": "success",
        "store_code": store_code,
        "baseline": round(result.baselines[store_code], 0),
        "model_info": result.model_info.get(store_code, {}),
    }


@router.post("/predict")
async def predict_month(
    target_month: str = Query(..., description="目标月份，格式 YYYY-MM，如 2026-06"),
):
    """预测指定月份的销售额"""
    cache_key = f"predict:{target_month}"
    cached = result_cache.get(cache_key)
    if cached:
        return cached

    stores = await load_stores()
    monthly_metrics = await load_monthly_metrics()
    daily_sales = await load_daily_sales()
    switch_status = await load_switch_status()

    # 只保留有月度数据的门店
    stores_with_metrics = monthly_metrics["store_code"].unique()
    stores = stores[stores["store_code"].isin(stores_with_metrics)]

    agent = BaselineAgent()
    result = agent.predict(
        target_month=target_month,
        stores_df=stores,
        monthly_metrics=monthly_metrics,
        daily_sales=daily_sales,
        switch_status=switch_status,
    )

    # 构建门店级明细（含置信区间）
    store_details = []
    for code in sorted(result.baselines.keys()):
        pred = result.baselines[code]
        ci = result.confidence_intervals.get(code, {})
        info = result.model_info.get(code, {})
        store_details.append({
            "store_code": code,
            "predicted": round(pred, 0),
            "ci_low": ci.get("low", round(pred * 0.8, 0)),
            "ci_mid": ci.get("mid", round(pred, 0)),
            "ci_high": ci.get("high", round(pred * 1.2, 0)),
            "cv": ci.get("cv", 0.2),
            "category": info.get("category", "unknown"),
            "mechanism": info.get("mechanism", "unknown"),
            "confidence": info.get("confidence", "medium"),
            "seasonal_index": info.get("seasonal_index", 1.0),
        })

    sorted_stores = sorted(store_details, key=lambda x: -x["predicted"])
    top_stores = sorted_stores[:10]
    bottom_stores = sorted_stores[-10:]

    response = {
        "status": "success",
        "target_month": result.target_month,
        "summary": {
            "total_predicted": result.total_predicted,
            "store_count": result.store_count,
            "avg_per_store": round(result.total_predicted / result.store_count, 0) if result.store_count > 0 else 0,
        },
        "region_summary": result.region_summary,
        "brand_summary": result.brand_summary,
        "category_summary": result.category_summary,
        "top_stores": top_stores,
        "bottom_stores": bottom_stores,
        "store_details": store_details,
    }
    result_cache.set(cache_key, response)
    return response


@router.post("/predict-yoy")
async def predict_yoy():
    """同比预测本月和下月利润"""
    cached = result_cache.get("predict_yoy")
    if cached:
        return cached

    stores = await load_stores()
    monthly_metrics = await load_monthly_metrics()

    agent = BaselineAgent()
    result = agent.predict_yoy(
        monthly_metrics=monthly_metrics,
        stores_df=stores,
    )

    details = result["store_details"]
    top_stores = details[:10]
    bottom_stores = details[-10:]

    response = {
        "status": "success",
        "current_month": {
            "month": result["current_month"]["month"],
            "total": result["current_month"]["total"],
            "store_count": result["current_month"]["store_count"],
        },
        "next_month": {
            "month": result["next_month"]["month"],
            "total": result["next_month"]["total"],
            "store_count": result["next_month"]["store_count"],
        },
        "top_stores": top_stores,
        "bottom_stores": bottom_stores,
        "store_details": details,
    }
    result_cache.set("predict_yoy", response)
    return response
