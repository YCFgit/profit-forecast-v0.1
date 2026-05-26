"""风险评估路由"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.agents.baseline_agent import BaselineAgent
from src.agents.allocation_agent import AllocationAgent
from src.data.collectors.factory import create_collector
from src.risk.risk_assessor import RiskAssessor
from src.risk.scenario_modeler import MonteCarloSimulator
from src.profit.profit_calculator import ProfitCalculator
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

    # 利润测算（使用 ProfitCalculator）
    calc = ProfitCalculator()
    profit_summary = calc.calculate(
        targets={c: a.target for c, a in allocation_result.plan.allocations.items()},
    )

    # 构建历史月度数据
    historical_monthly = {}
    for code in baseline_result.baselines:
        store_sales = daily_sales[daily_sales["store_code"] == code] if not daily_sales.empty else pd.DataFrame()
        if not store_sales.empty and "sales_amount" in store_sales.columns:
            historical_monthly[code] = store_sales["sales_amount"].tolist()

    # 风险评估（使用 RiskAssessor）
    risk_assessor = RiskAssessor()
    assessment = risk_assessor.assess(
        plan=allocation_result.plan,
        profit_summary=profit_summary,
        historical_monthly=historical_monthly,
    )

    # 蒙特卡洛
    mc = None
    if assessment.monte_carlo:
        mc = {
            "profit_mean": round(assessment.monte_carlo.profit_mean, 0),
            "profit_std": round(assessment.monte_carlo.profit_std, 0),
            "loss_probability": f"{assessment.monte_carlo.loss_probability:.1%}",
            "var_95": round(assessment.monte_carlo.var_95, 0),
            "cvar_95": round(assessment.monte_carlo.cvar_95, 0),
        }

    return RiskResponse(
        status="success",
        overall_score=round(assessment.overall_score, 1),
        overall_level=assessment.overall_level,
        factors=[{
            "name": f.name,
            "score": round(f.score, 1),
            "level": f.level,
            "description": f.description,
            "affected_stores": len(f.affected_stores),
        } for f in assessment.factors],
        recommendations=assessment.recommendations,
        high_risk_stores=[],
        monte_carlo=mc,
    )


@router.post("/monte-carlo")
async def run_monte_carlo(request: RiskRequest):
    """单独运行蒙特卡洛模拟"""
    collector = create_collector()
    async with collector:
        stores_df = await collector.fetch_stores()
        monthly_metrics = await collector.fetch_monthly_metrics()

    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(monthly_metrics)

    allocation_agent = AllocationAgent()
    store_profiles = allocation_agent.build_store_profiles(stores_df, monthly_metrics)
    allocation_result = allocation_agent.allocate(
        total_target=request.total_target,
        baselines=baseline_result.baselines,
        store_profiles=store_profiles,
        with_scenarios=False,
    )

    # 利润测算
    calc = ProfitCalculator()
    profit_summary = calc.calculate(
        targets={c: a.target for c, a in allocation_result.plan.allocations.items()},
    )

    # 蒙特卡洛模拟
    mc_simulator = MonteCarloSimulator()
    mc = mc_simulator.simulate(
        base_revenue=profit_summary.total_revenue,
        base_cost=profit_summary.total_cogs + profit_summary.total_operating_expense,
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
