"""全流程编排路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from src.api.cache import result_cache

router = APIRouter()


class PipelineRequest(BaseModel):
    total_target: float
    adapter: str = "mock"


@router.get("/cache-stats")
async def cache_stats():
    """查看缓存状态"""
    from src.api.cache import data_cache, result_cache
    return {
        "data_cache": data_cache.stats(),
        "result_cache": result_cache.stats(),
    }


@router.post("/cache-clear")
async def cache_clear():
    """清除所有缓存"""
    from src.api.cache import data_cache, result_cache
    data_cache.invalidate()
    result_cache.invalidate()
    return {"status": "ok", "message": "缓存已清除"}


@router.get("/health")
async def pipeline_health():
    """全流程健康检查"""
    checks = {}

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


@router.post("/run")
async def run_pipeline(req: PipelineRequest):
    """执行全流程利润测算"""
    cache_key = f"pipeline:{req.total_target}:{req.adapter}"
    cached = result_cache.get(cache_key)
    if cached:
        return cached

    from src.agents.orchestrator import Orchestrator

    try:
        orch = Orchestrator(adapter=req.adapter)
        result = orch.run(boss_target=req.total_target)
    except Exception as e:
        logger.error(f"Pipeline 执行失败: {e}")
        raise HTTPException(status_code=500, detail=f"测算失败: {e}")

    profit = result.get("profit_summary")
    risk = result.get("risk_result")
    alloc = result.get("allocation_result")

    if profit is None:
        raise HTTPException(status_code=400, detail="数据为空，无法测算")

    # 风险等级判定
    risk_summary = risk.get("summary", {}) if risk else {}
    high_count = risk_summary.get("high_risk", 0) + risk_summary.get("critical_risk", 0)
    total_stores = risk_summary.get("total_stores", 1)
    risk_ratio = high_count / total_stores if total_stores > 0 else 0

    if risk_ratio > 0.3:
        risk_level = "critical"
        risk_score = 80 + risk_ratio * 20
    elif risk_ratio > 0.15:
        risk_level = "high"
        risk_score = 60 + risk_ratio * 20
    elif risk_ratio > 0.05:
        risk_level = "medium"
        risk_score = 30 + risk_ratio * 30
    else:
        risk_level = "low"
        risk_score = risk_ratio * 100

    # 构建 summary
    summary = {
        "总目标": req.total_target,
        "净利润": profit.total_net_profit,
        "净利率": f"{profit.avg_net_margin:.1%}" if hasattr(profit, 'avg_net_margin') else "N/A",
        "门店数": profit.store_count,
        "盈利门店": profit.profitable_count,
        "亏损门店": profit.loss_count,
        "风险等级": risk_level,
        "风险分": round(risk_score, 2),
    }

    # 构建 allocation_detail
    allocation_detail = []
    if alloc:
        # 优先 MIP 分配结果
        if alloc.mip_result and alloc.mip_result.stores:
            for store_code, sr in alloc.mip_result.stores.items():
                allocation_detail.append({
                    "store_code": store_code,
                    "baseline": round(sr.baseline, 2),
                    "target": round(sr.target, 2),
                    "pressure_ratio": f"{sr.pressure / sr.baseline:.1%}" if sr.baseline > 0 else "0.0%",
                    "growth_rate": f"{sr.growth_rate:.1%}",
                })
        # 降级：权重分配结果
        elif alloc.plan and alloc.plan.allocations:
            for store_code, ar in alloc.plan.allocations.items():
                allocation_detail.append({
                    "store_code": store_code,
                    "baseline": round(ar.baseline, 2),
                    "target": round(ar.target, 2),
                    "pressure_ratio": f"{ar.pressure_ratio:.1%}",
                    "growth_rate": f"{ar.growth_rate:.1%}",
                })

    # 构建 recommendations
    recommendations = []
    if risk:
        store_risks = risk.get("store_risks", {})
        critical_stores = [s for s, r in store_risks.items() if r.get("risk_level") in ("high", "critical")]
        if critical_stores:
            recommendations.append(f"共 {len(critical_stores)} 家高风险门店需重点关注: {', '.join(critical_stores[:5])}")
        if profit.loss_count > 0:
            recommendations.append(f"当前有 {profit.loss_count} 家亏损门店，建议优化成本结构或调整目标")
        if alloc and alloc.fairness:
            recommendations.append(f"分配公平性评级: {alloc.fairness.grade}")

    response = {
        "summary": summary,
        "allocation_detail": allocation_detail,
        "recommendations": recommendations,
    }
    result_cache.set(cache_key, response)
    return response
