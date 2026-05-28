#!/bin/bash
# ============================================================
# 鞋服零售利润测算系统 — 本地开发启动脚本
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo " 鞋服零售利润测算系统 — 本地开发模式"
echo "=========================================="

# 1. 检查 .env 文件
if [ ! -f .env ]; then
    echo "[1/5] 未找到 .env，从 .env.example 复制..."
    cp .env.example .env
    echo "      已创建 .env，请根据实际情况修改配置"
else
    echo "[1/5] .env 已存在"
fi

# 2. 启动 Docker 基础设施（MySQL）
echo "[2/6] 启动 Docker 基础设施..."
docker compose up -d mysql
echo "      等待数据库就绪..."
sleep 3

# 3. 运行数据库迁移
echo "[3/6] 运行数据库迁移..."
source .env 2>/dev/null || true
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}" \
MYSQL_HOST="${MYSQL_HOST:-localhost}" \
MYSQL_PORT="${MYSQL_PORT:-3306}" \
MYSQL_USER="${MYSQL_USER:-root}" \
MYSQL_DATABASE="${MYSQL_DATABASE:-profit_forecast}" \
    alembic upgrade head 2>/dev/null || echo "      跳过（数据库未就绪或已迁移）"

# 4. 安装前端依赖
echo "[4/6] 检查前端依赖..."
cd frontend
if [ ! -d node_modules ]; then
    echo "      首次安装前端依赖..."
    npm install
fi
cd ..

# 5. 启动前端开发服务器（后台）
echo "[5/6] 启动前端开发服务器..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..
echo "      前端 PID: $FRONTEND_PID"

# 6. 启动 FastAPI 应用
echo "[6/6] 启动 FastAPI 应用..."
echo ""
echo "  前端页面: http://localhost:3000"
echo "  API 文档: http://localhost:8000/docs"
echo "  健康检查: http://localhost:8000/health"
echo ""
echo "  按 Ctrl+C 停止所有服务"
trap "kill $FRONTEND_PID 2>/dev/null; exit" INT TERM
python3 run.py
