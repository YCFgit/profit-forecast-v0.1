"""编排 API 路由"""

from dataclasses import asdict

from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/orchestrate", tags=["orchestrate"])


def _serialize_result(result: dict) -> dict:
    """将 Orchestrator 返回值转为可 JSON 序列化的 dict"""
    out = {}
    for key, value in result.items():
        if value is None:
            out[key] = None
        elif hasattr(value, "to_dict"):
            # DataFrame
            out[key] = value.to_dict(orient="records")
        elif hasattr(value, "__dataclass_fields__"):
            # dataclass
            out[key] = asdict(value)
        elif isinstance(value, dict):
            # 递归处理 dict（如 risk_result）
            out[key] = {
                k: (asdict(v) if hasattr(v, "__dataclass_fields__") else v)
                for k, v in value.items()
            }
        else:
            out[key] = value
    return out


@router.post("/full")
async def run_full(
    store_no: Optional[str] = Query(None),
    date_start: str = Query(...),
    date_end: str = Query(...),
    total_target: Optional[float] = Query(None),
    perspective: str = Query("actual"),
):
    """执行完整流程"""
    from src.agents.orchestrator import Orchestrator

    orch = Orchestrator()
    result = orch.run(
        store_no=store_no,
        date_range=(date_start, date_end),
        boss_target=total_target,
        perspective=perspective,
    )
    return _serialize_result(result)


@router.post("/quick")
async def run_quick(
    store_no: str = Query(...),
    date_start: str = Query(...),
    date_end: str = Query(...),
):
    """快速测算"""
    from src.agents.orchestrator import Orchestrator

    orch = Orchestrator()
    result = orch.run(store_no=store_no, date_range=(date_start, date_end))
    return _serialize_result(result)
