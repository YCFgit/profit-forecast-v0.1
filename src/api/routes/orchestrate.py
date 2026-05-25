"""全流程编排路由"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.agents.orchestrator import Orchestrator

router = APIRouter()


class PipelineRequest(BaseModel):
    total_target: float = Field(..., description="老板设定的总利润目标", gt=0)
    adapter: str | None = Field(None, description="数据源适配器（mock/starrocks）")


class PipelineResponse(BaseModel):
    status: str
    summary: dict
    allocation_detail: list[dict]
    profit_summary: dict
    pnl: list[dict]
    profit_details: list[dict]
    risk_summary: dict
    recommendations: list[str]


@router.post("/run", response_model=PipelineResponse)
async def run_pipeline(request: PipelineRequest):
    """执行完整利润测算流程

    一键跑通：数据采集 → 基线预估 → 承压分配 → 利润测算 → 风险评估
    使用真实损益数据构建成本结构。
    """
    orchestrator = Orchestrator(adapter=request.adapter)
    result = await orchestrator.run(total_target=request.total_target)

    # 分配明细
    allocation_detail = []
    for code, alloc in sorted(result.allocation.plan.allocations.items()):
        allocation_detail.append({
            "store_code": code,
            "baseline": round(alloc.baseline, 0),
            "target": round(alloc.target, 0),
            "pressure_ratio": f"{alloc.pressure_ratio:.1%}",
            "growth_rate": f"{alloc.growth_rate:.1%}",
        })

    # 利润汇总
    profit_summary = result.profit.summary_dict

    # P&L 表
    pnl = result.profit.pnl_table.to_dict(orient="records") if result.profit.pnl_table is not None else []

    # 门店利润明细
    from src.profit.profit_calculator import ProfitCalculator
    calc = ProfitCalculator()
    profit_details = calc.to_dataframe(result.profit.summary).to_dict(orient="records")

    # 风险汇总
    risk_summary = result.risk.summary_dict

    return PipelineResponse(
        status="success",
        summary=result.summary,
        allocation_detail=allocation_detail,
        profit_summary=profit_summary,
        pnl=pnl,
        profit_details=profit_details,
        risk_summary=risk_summary,
        recommendations=result.risk.recommendations,
    )


@router.get("/health")
async def pipeline_health():
    """检查各模块可用性"""
    checks = {}

    # 检查数据源
    try:
        from src.data.collectors.factory import create_collector
        collector = create_collector()
        checks["data_collector"] = "ok"
    except Exception as e:
        checks["data_collector"] = f"error: {e}"

    # 检查各模块导入
    for module in ["forecasting", "allocation", "profit", "risk", "agents"]:
        try:
            __import__(f"src.{module}")
            checks[module] = "ok"
        except Exception as e:
            checks[module] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
    }
