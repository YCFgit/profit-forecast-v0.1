"""利润测算路由"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.agents.profit_agent import ProfitAgent
from src.agents.baseline_agent import BaselineAgent
from src.agents.allocation_agent import AllocationAgent
from src.data.collectors.factory import create_collector
from src.profit.cost_estimator import CostEstimator

router = APIRouter()


class ProfitRequest(BaseModel):
    total_target: float = Field(..., description="总利润目标", gt=0)


class ProfitResponse(BaseModel):
    status: str
    summary: dict
    pnl: list[dict]
    comparison: list[dict]
    top_stores: list[dict]
    bottom_stores: list[dict]


@router.post("/calculate", response_model=ProfitResponse)
async def calculate_profit(request: ProfitRequest):
    """测算利润

    根据承压分配结果计算各门店和整体的利润。
    包含 P&L 利润表、基线对比、Top/Bottom 排行。
    优先使用真实损益数据，无数据时降级到默认比例。
    """
    # 采集数据
    collector = create_collector()
    async with collector:
        stores_df = await collector.fetch_stores()
        monthly_metrics = await collector.fetch_monthly_metrics()
        store_loss_df = await collector.fetch_store_loss()

    # 基线预估
    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(monthly_metrics)

    # 承压分配
    allocation_agent = AllocationAgent()
    store_profiles = allocation_agent.build_store_profiles(stores_df, monthly_metrics)
    allocation_result = allocation_agent.allocate(
        total_target=request.total_target,
        baselines=baseline_result.baselines,
        store_profiles=store_profiles,
        with_scenarios=False,
    )

    # 构建映射
    store_region_map = {}
    store_type_map = {}
    for _, row in stores_df.iterrows():
        store_region_map[row["store_code"]] = row.get("region", "未知")
        store_type_map[row["store_code"]] = row.get("store_type", "标准店")

    # 从真实损益数据构建成本结构
    targets = {c: a.target for c, a in allocation_result.plan.allocations.items()}
    cost_structures = None
    if not store_loss_df.empty:
        cost_estimator = CostEstimator()
        cost_structures = cost_estimator.from_store_loss_data(
            store_loss_df=store_loss_df,
            targets=targets,
            months=3,
        )

    # 利润测算
    profit_agent = ProfitAgent()
    result = profit_agent.calculate(
        targets=targets,
        baselines=baseline_result.baselines,
        cost_structures=cost_structures,
        store_region_map=store_region_map,
        store_type_map=store_type_map,
    )

    # Top/Bottom
    ranking = profit_agent.get_top_bottom(result.summary, n=10)

    return ProfitResponse(
        status="success",
        summary=result.summary_dict,
        pnl=result.pnl_table.to_dict(orient="records"),
        comparison=result.comparison.to_dict(orient="records"),
        top_stores=ranking["top_n"].to_dict(orient="records"),
        bottom_stores=ranking["bottom_n"].to_dict(orient="records"),
    )


@router.get("/drill-down/region")
async def profit_by_region():
    """按区域下钻利润"""
    collector = create_collector()
    async with collector:
        stores_df = await collector.fetch_stores()
        monthly_metrics = await collector.fetch_monthly_metrics()
        store_loss_df = await collector.fetch_store_loss()

    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(monthly_metrics)

    allocation_agent = AllocationAgent()
    store_profiles = allocation_agent.build_store_profiles(stores_df, monthly_metrics)
    allocation_result = allocation_agent.allocate(
        total_target=sum(baseline_result.baselines.values()) * 1.2,
        baselines=baseline_result.baselines,
        store_profiles=store_profiles,
        with_scenarios=False,
    )

    store_region_map = {}
    for _, row in stores_df.iterrows():
        store_region_map[row["store_code"]] = row.get("region", "未知")

    targets = {c: a.target for c, a in allocation_result.plan.allocations.items()}
    cost_structures = None
    if not store_loss_df.empty:
        cost_estimator = CostEstimator()
        cost_structures = cost_estimator.from_store_loss_data(store_loss_df, targets, months=3)

    profit_agent = ProfitAgent()
    result = profit_agent.calculate(
        targets=targets,
        baselines=baseline_result.baselines,
        cost_structures=cost_structures,
        store_region_map=store_region_map,
    )

    return {
        "status": "success",
        "dimension": "区域",
        "data": result.region_drill_down.to_dataframe().to_dict(orient="records") if result.region_drill_down else [],
    }


@router.get("/drill-down/type")
async def profit_by_type():
    """按门店类型下钻利润"""
    collector = create_collector()
    async with collector:
        stores_df = await collector.fetch_stores()
        monthly_metrics = await collector.fetch_monthly_metrics()
        store_loss_df = await collector.fetch_store_loss()

    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(monthly_metrics)

    allocation_agent = AllocationAgent()
    store_profiles = allocation_agent.build_store_profiles(stores_df, monthly_metrics)
    allocation_result = allocation_agent.allocate(
        total_target=sum(baseline_result.baselines.values()) * 1.2,
        baselines=baseline_result.baselines,
        store_profiles=store_profiles,
        with_scenarios=False,
    )

    store_type_map = {}
    for _, row in stores_df.iterrows():
        store_type_map[row["store_code"]] = row.get("store_type", "标准店")

    targets = {c: a.target for c, a in allocation_result.plan.allocations.items()}
    cost_structures = None
    if not store_loss_df.empty:
        cost_estimator = CostEstimator()
        cost_structures = cost_estimator.from_store_loss_data(store_loss_df, targets, months=3)

    profit_agent = ProfitAgent()
    result = profit_agent.calculate(
        targets=targets,
        baselines=baseline_result.baselines,
        cost_structures=cost_structures,
        store_type_map=store_type_map,
    )

    return {
        "status": "success",
        "dimension": "门店类型",
        "data": result.type_drill_down.to_dataframe().to_dict(orient="records") if result.type_drill_down else [],
    }
