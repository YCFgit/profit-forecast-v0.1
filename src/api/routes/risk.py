"""风险评估路由"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.agents.risk_agent import RiskAgent
from src.agents.profit_agent import ProfitAgent
from src.agents.baseline_agent import BaselineAgent
from src.agents.allocation_agent import AllocationAgent
from src.data.collectors.factory import create_collector
import pandas as pd

router = APIRouter()


class RiskRequest(BaseModel):
    total_target: float = Field(..., description="总利润目标", gt=0)


class RiskResponse(BaseModel):
    status: str
    overall_score: float
    overall_level: str
    factors: list[dict]
    recommendations: list[str]
    high_risk_stores: list[dict]
    monte_carlo: dict | None = None


@router.post("/assess", response_model=RiskResponse)
async def assess_risk(request: RiskRequest):
    """综合风险评估

    评估承压分配方案的风险，包括：
    - 目标可达性
    - 承压均匀度
    - 保底线覆盖率
    - 新店风险
    - 利润不确定性（蒙特卡洛）
    """
    # 采集数据
    collector = create_collector()
    async with collector:
        stores_df = await collector.fetch_stores()
        monthly_metrics = await collector.fetch_monthly_metrics()
        daily_sales = await collector.fetch_daily_sales()

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

    # 利润测算
    targets = {c: a.target for c, a in allocation_result.plan.allocations.items()}
    profit_agent = ProfitAgent()
    profit_result = profit_agent.calculate(
        targets=targets,
        baselines=baseline_result.baselines,
    )

    # 构建历史月度数据
    historical_monthly = {}
    for code in baseline_result.baselines:
        store_sales = daily_sales[daily_sales["store_code"] == code] if not daily_sales.empty else pd.DataFrame()
        if not store_sales.empty and "sales_amount" in store_sales.columns:
            historical_monthly[code] = store_sales["sales_amount"].tolist()

    # 风险评估
    risk_agent = RiskAgent()
    result = risk_agent.assess(
        plan=allocation_result.plan,
        profit_summary=profit_result.summary,
        historical_monthly=historical_monthly,
    )

    # 蒙特卡洛
    mc = None
    if result.monte_carlo:
        mc = {
            "profit_mean": round(result.monte_carlo.profit_mean, 0),
            "profit_std": round(result.monte_carlo.profit_std, 0),
            "loss_probability": f"{result.monte_carlo.loss_probability:.1%}",
            "var_95": round(result.monte_carlo.var_95, 0),
            "cvar_95": round(result.monte_carlo.cvar_95, 0),
        }

    return RiskResponse(
        status="success",
        overall_score=round(result.assessment.overall_score, 1),
        overall_level=result.assessment.overall_level,
        factors=[{
            "name": f.name,
            "score": round(f.score, 1),
            "level": f.level,
            "description": f.description,
            "affected_stores": len(f.affected_stores),
        } for f in result.assessment.factors],
        recommendations=result.recommendations,
        high_risk_stores=result.high_risk_stores.to_dict(orient="records") if not result.high_risk_stores.empty else [],
        monte_carlo=mc,
    )


@router.post("/monte-carlo")
async def run_monte_carlo(request: RiskRequest):
    """单独运行蒙特卡洛模拟"""
    collector = create_collector()
    async with collector:
        monthly_metrics = await collector.fetch_monthly_metrics()

    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(monthly_metrics)

    allocation_agent = AllocationAgent()
    stores_df = await collector.fetch_stores() if not hasattr(collector, '_closed') else pd.DataFrame()
    store_profiles = allocation_agent.build_store_profiles(stores_df, monthly_metrics)
    allocation_result = allocation_agent.allocate(
        total_target=request.total_target,
        baselines=baseline_result.baselines,
        store_profiles=store_profiles,
        with_scenarios=False,
    )

    profit_agent = ProfitAgent()
    targets = {c: a.target for c, a in allocation_result.plan.allocations.items()}
    profit_result = profit_agent.calculate(targets=targets, baselines=baseline_result.baselines)

    risk_agent = RiskAgent()
    mc = risk_agent.simulate_monte_carlo(
        base_revenue=profit_result.summary.total_revenue,
        base_cost=profit_result.summary.total_cogs + profit_result.summary.total_operating_expense,
    )

    return {
        "status": "success",
        "n_simulations": mc.n_simulations,
        "profit_mean": round(mc.profit_mean, 0),
        "profit_std": round(mc.profit_std, 0),
        "profit_median": round(mc.profit_median, 0),
        "loss_probability": f"{mc.loss_probability:.1%}",
        "var_95": round(mc.var_95, 0),
        "cvar_95": round(mc.cvar_95, 0),
        "percentiles": {
            "p5": round(mc.profit_p5, 0),
            "p10": round(mc.profit_p10, 0),
            "p25": round(mc.profit_p25, 0),
            "p50": round(mc.profit_median, 0),
            "p75": round(mc.profit_p75, 0),
            "p95": round(mc.profit_p95, 0),
        },
    }
