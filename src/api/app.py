"""FastAPI 应用入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.core.config import get_settings
from src.core.logging import setup_logging
from src.db.session import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    setup_logging()
    settings = get_settings()
    logger.info(f"启动应用 | 环境: {settings.app_env} | DataWorks: {settings.dataworks_adapter}")

    # 测试数据库连接
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            logger.info("数据库连接正常")
    except Exception as e:
        logger.warning(f"数据库连接失败: {e}（启动时未连接数据库不影响 Mock 模式）")

    yield

    # 清理资源
    engine = get_engine()
    await engine.dispose()
    logger.info("应用关闭")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="鞋服零售利润测算系统",
        description="基线预估 × 承压分配 × 利润测算",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from src.api.routes import health, stores, data_import
    from src.api.routes import forecast, allocation, profit, risk, orchestrate

    app.include_router(health.router, tags=["健康检查"])
    app.include_router(stores.router, prefix="/api/v1/stores", tags=["门店管理"])
    app.include_router(data_import.router, prefix="/api/v1/import", tags=["数据导入"])
    app.include_router(forecast.router, prefix="/api/v1/forecast", tags=["基线预估"])
    app.include_router(allocation.router, prefix="/api/v1/allocation", tags=["承压分配"])
    app.include_router(profit.router, prefix="/api/v1/profit", tags=["利润测算"])
    app.include_router(risk.router, prefix="/api/v1/risk", tags=["风险评估"])
    app.include_router(orchestrate.router, prefix="/api/v1/pipeline", tags=["全流程编排"])

    return app
