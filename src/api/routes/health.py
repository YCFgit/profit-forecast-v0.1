"""健康检查路由"""

from fastapi import APIRouter

from src.core.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "ok",
        "env": settings.app_env,
        "dataworks_adapter": settings.dataworks_adapter,
    }
