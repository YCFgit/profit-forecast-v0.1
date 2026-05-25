"""应用启动入口"""

import uvicorn

from src.api.app import create_app
from src.core.config import get_settings

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "run:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
