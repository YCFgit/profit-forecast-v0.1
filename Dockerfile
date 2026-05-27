# ============================================================
# profit-forecast v0.1 — 销售驱动利润测算系统
# ============================================================

FROM python:3.13-slim

WORKDIR /app

# 复制依赖文件和代码（利用 Docker 缓存层）
COPY pyproject.toml ./
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY run.py ./

# 安装 Python 依赖
RUN pip install --no-cache-dir .

# 环境变量
ENV APP_ENV=production \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    APP_DEBUG=false \
    STORAGE_BACKEND=sqlite \
    SQLITE_DB_PATH=/app/data/profit_forecast.db

# 数据目录
RUN mkdir -p /app/data

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["python", "run.py"]
