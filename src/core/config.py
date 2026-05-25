"""应用配置管理"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 数据库
    database_url: str = "postgresql+asyncpg://profit:profit123@localhost:5432/profit_forecast"
    database_url_sync: str = "postgresql+psycopg2://profit:profit123@localhost:5432/profit_forecast"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # DataWorks / StarRocks
    dataworks_adapter: str = "mock"  # mock | starrocks | dataworks_api | maxcompute | database
    dataworks_access_key_id: str = ""
    dataworks_access_key_secret: str = ""
    dataworks_project: str = ""
    dataworks_endpoint: str = "https://service.cn-shanghai.maxcompute.aliyun.com/api"

    # StarRocks
    starrocks_host: str = "localhost"
    starrocks_port: int = 9030
    starrocks_user: str = "root"
    starrocks_password: str = ""
    starrocks_database: str = ""

    # 应用
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # 日志
    log_level: str = "DEBUG"
    log_file: str = "logs/app.log"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
