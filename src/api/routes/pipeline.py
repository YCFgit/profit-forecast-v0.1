"""全流程编排健康检查路由"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def pipeline_health():
    """全流程健康检查

    检查各子系统是否可用（不依赖数据库连接）。
    """
    checks = {}

    # 检查各 Agent 是否可导入
    try:
        from src.agents.baseline_agent import BaselineAgent
        checks["baseline_agent"] = "ok"
    except Exception as e:
        checks["baseline_agent"] = f"error: {e}"

    try:
        from src.agents.allocation_agent import AllocationAgent
        checks["allocation_agent"] = "ok"
    except Exception as e:
        checks["allocation_agent"] = f"error: {e}"

    try:
        from src.agents.profit_agent import ProfitAgent
        checks["profit_agent"] = "ok"
    except Exception as e:
        checks["profit_agent"] = f"error: {e}"

    try:
        from src.agents.risk_agent import RiskAgent
        checks["risk_agent"] = "ok"
    except Exception as e:
        checks["risk_agent"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
    }
