"""承压分配路由"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.agents.allocation_agent import AllocationAgent
from src.agents.baseline_agent import BaselineAgent
from src.data.collectors.factory import create_collector

router = APIRouter()


class AllocateRequest(BaseModel):
    total_target: float = Field(..., description="老板设定的总利润目标", gt=0)
    with_scenarios: bool = Field(True, description="是否生成情景对比")


class AllocateResponse(BaseModel):
    status: str
    total_target: float
    total_baseline: float
    total_allocated: float
    avg_growth_rate: str
    fairness_grade: str
    store_count: int
    allocations: list[dict]
    scenarios: dict | None = None


@router.post("/", response_model=AllocateResponse)
async def allocate_targets(request: AllocateRequest):
    """执行承压分配

    将老板的总利润目标按门店能力权重分配到各门店。
    包含保底线约束、新店保护、公平性检查。
    """
    # 采集数据
    collector = create_collector()
    async with collector:
        stores_df = await collector.fetch_stores()
        monthly_metrics = await collector.fetch_monthly_metrics()

    # 基线预估
    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(monthly_metrics)

    # 构建门店画像
    allocation_agent = AllocationAgent()
    store_profiles = allocation_agent.build_store_profiles(stores_df, monthly_metrics)

    # 执行分配
    result = allocation_agent.allocate(
        total_target=request.total_target,
        baselines=baseline_result.baselines,
        store_profiles=store_profiles,
        with_scenarios=request.with_scenarios,
    )

    # 构建分配明细
    allocations = []
    for code, alloc in sorted(result.plan.allocations.items()):
        allocations.append({
            "store_code": code,
            "baseline": round(alloc.baseline, 0),
            "target": round(alloc.target, 0),
            "pressure": round(alloc.pressure, 0),
            "pressure_ratio": f"{alloc.pressure_ratio:.1%}",
            "growth_rate": f"{alloc.growth_rate:.1%}",
            "is_new_store": alloc.is_new_store,
        })

    # 情景对比
    scenarios = None
    if result.scenario_comparison:
        scenarios = {}
        for name, scenario in result.scenario_comparison.scenarios.items():
            scenarios[name] = {
                "total_target": round(scenario.total_target, 0),
                "growth_target": f"{scenario.growth_target:.0%}",
                "fairness_grade": scenario.fairness.grade,
                "avg_pressure_rate": f"{scenario.fairness.avg_pressure_rate:.1%}",
            }

    return AllocateResponse(
        status="success",
        total_target=round(result.plan.total_target, 0),
        total_baseline=round(result.plan.total_baseline, 0),
        total_allocated=round(result.plan.total_allocated, 0),
        avg_growth_rate=f"{result.plan.avg_growth_rate:.1%}",
        fairness_grade=result.fairness.grade,
        store_count=result.store_count,
        allocations=allocations,
        scenarios=scenarios,
    )


@router.get("/scenarios")
async def get_scenarios():
    """获取多情景模拟结果（保守/稳健/激进）"""
    collector = create_collector()
    async with collector:
        stores_df = await collector.fetch_stores()
        monthly_metrics = await collector.fetch_monthly_metrics()

    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(monthly_metrics)

    allocation_agent = AllocationAgent()
    store_profiles = allocation_agent.build_store_profiles(stores_df, monthly_metrics)

    from src.allocation.scenario_simulator import ScenarioSimulator
    simulator = ScenarioSimulator()
    comparison = simulator.simulate(baseline_result.baselines, store_profiles)

    return {
        "status": "success",
        "recommendation": comparison.recommend(),
        "scenarios": comparison.to_dataframe().to_dict(orient="records"),
    }
