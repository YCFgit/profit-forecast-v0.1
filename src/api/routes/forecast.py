"""基线预估路由"""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.agents.baseline_agent import BaselineAgent
from src.data.collectors.factory import create_collector

router = APIRouter()


class ForecastResponse(BaseModel):
    status: str
    store_count: int
    avg_mape: float
    baselines: dict[str, float]
    model_info: dict[str, dict]


@router.get("/baselines", response_model=ForecastResponse)
async def get_baselines():
    """获取所有门店的基线预估

    使用业务规则引擎为每家门店生成基线预估值。
    """
    collector = create_collector("mysql")
    async with collector:
        stores = await collector.fetch_stores()
        monthly_metrics = await collector.fetch_monthly_metrics()
        daily_sales = await collector.fetch_daily_sales()
        switch_status = await collector.fetch_switch_status()

    agent = BaselineAgent()
    result = agent.forecast(
        monthly_metrics=monthly_metrics,
        stores_df=stores,
        daily_sales=daily_sales,
        switch_status=switch_status,
    )

    return ForecastResponse(
        status="success",
        store_count=result.store_count,
        avg_mape=round(result.avg_mape, 4),
        baselines={k: round(v, 0) for k, v in result.baselines.items()},
        model_info=result.model_info,
    )


@router.get("/baselines/{store_code}")
async def get_store_baseline(store_code: str):
    """获取单门店的基线预估详情"""
    collector = create_collector("mysql")
    async with collector:
        stores = await collector.fetch_stores()
        monthly_metrics = await collector.fetch_monthly_metrics()

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
    """预测指定月份的销售额

    使用完整的基线预估引擎（门店分类 + 季节指数 + 6种预估器），
    并基于历史波动率计算置信区间（乐观/中性/悲观）。

    返回：
    - 每家门店的预测值和置信区间
    - 区域/品牌维度汇总
    - 门店分类统计
    """
    collector = create_collector("mysql")

    async with collector:
        stores = await collector.fetch_stores()
        monthly_metrics = await collector.fetch_monthly_metrics()
        daily_sales = await collector.fetch_daily_sales()
        switch_status = await collector.fetch_switch_status()

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

    # Top / Bottom
    sorted_stores = sorted(store_details, key=lambda x: -x["predicted"])
    top_stores = sorted_stores[:10]
    bottom_stores = sorted_stores[-10:]

    return {
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
