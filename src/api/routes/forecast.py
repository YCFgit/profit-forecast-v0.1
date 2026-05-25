"""基线预估路由"""

from fastapi import APIRouter
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
    collector = create_collector()
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
    collector = create_collector()
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
