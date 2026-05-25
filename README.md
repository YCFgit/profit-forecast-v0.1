# 鞋服零售利润测算系统

基线预估 × 承压分配 × 利润测算 — 多 Agent 智能协作

## 快速开始

### 1. 启动基础设施

```bash
cd docker
docker compose up -d
```

### 2. 安装依赖

```bash
pip install -e .
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，配置数据源等
```

### 4. 启动应用

```bash
python run.py
```

API 文档: http://localhost:8000/docs

## 架构文档

详见 [`docs/architecture/`](docs/architecture/)：

- [Agent 组织架构图](docs/architecture/org_chart.mmd) — 6 个 Agent 的协作关系
- [全流程泳道图](docs/architecture/swimlane.mmd) — 5 个 Phase 的执行时序
- [Agent 配置](docs/architecture/agents.json) — 各 Agent 角色、输入输出、代码位置
- [多 Agent 协作方案](docs/architecture/index.html) — 汇报用 HTML（浏览器打开）
- [实施方案](docs/architecture/implementation_plan.html) — 20 周路线图 + 团队/成本

## 项目结构

```
profit-forecast/
├── src/
│   ├── agents/           # Agent 编排层（Orchestrator + 5 个专业 Agent）
│   ├── allocation/       # 承压分配算法（Phase 3）
│   ├── api/              # FastAPI 路由
│   │   └── routes/       # API 端点
│   ├── baseline/         # 基线预估（Phase 2）
│   ├── core/             # 配置、日志
│   ├── data/
│   │   ├── collectors/   # 数据采集器（StarRocks/Mock/DataWorks）
│   │   ├── validators/   # 数据校验和质量检查
│   │   └── storage/      # 存储层
│   ├── db/               # SQLAlchemy 模型和连接
│   ├── forecasting/      # 预测模型（Phase 2）
│   ├── profit/           # 利润测算（Phase 4）+ 成本预估器
│   └── risk/             # 风险评估（Phase 4）
├── docs/
│   ├── architecture/     # 架构文档（Agent 图/泳道图/方案 HTML）
│   └── data_requirements.md
├── scripts/
│   ├── etl_sql/          # 8 个 ETL SQL 脚本（StarRocks 数据导出）
│   ├── run_real_profit.py # 真实数据利润测算脚本
│   └── export_to_csv.py  # 数据导出脚本
├── docker/               # Docker Compose 配置
├── tests/                # 测试（159 个）
├── .env.example          # 环境变量模板
├── pyproject.toml        # Python 项目配置
└── run.py                # 应用入口
```

## 数据源配置

在 `.env` 中设置 `DATAWORKS_ADAPTER`：

| 值 | 说明 |
|---|---|
| `mock` | 模拟数据（开发测试用） |
| `dataworks_api` | DataWorks Open API |
| `maxcompute` | MaxCompute 直连 |
| `database` | 从 DataWorks 同步到的中间库 |

## 当前进度

- [x] M1: 项目结构 + Docker + 数据库 Schema
- [x] M1: 数据采集层（可扩展适配器模式）
- [x] M1: FastAPI 应用骨架
- [x] M2: 基线预估模型（v2 业务规则引擎：6 分类 + 季节指数 + 6 预估器）
- [x] M3: 承压分配算法（TargetAllocator + 公平性/约束检查 + 情景模拟）
- [x] M4: 利润测算 + 风险评估（ProfitCalculator + RiskAgent）
- [x] M5: Agent 编排 + Web 界面（Orchestrator + React 前端 4 页面）
- [x] M6: 测试上线（150 测试通过 + Docker Compose + Alembic 迁移）
