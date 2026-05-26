# 真实数据 ETL 加工设计

## 目标

从 StarRocks 读取真实业务数据，经过加工后写入本地 MySQL + 文件宽表，供利润测算系统使用。

## 架构

```
StarRocks (远端)
    │
    ▼
ETLPipeline
    ├─ load_stores()        → 门店主数据
    ├─ load_store_loss()    → 日损益（支持 业绩/返利 双口径）
    ├─ load_pos_orders()    → POS 订单
    ├─ load_monthly_metrics() → 月度指标聚合
    │
    ▼
Writer (双输出)
    ├─ MySQLWriter  → upsert 到本地 MySQL（元数据存储）
    └─ FileCSVWriter → 输出 CSV 宽表（分析用）
```

## 核心模块

### 1. ETLPipeline (`src/data/etl/pipeline.py`)

统一入口，协调 loader → writer 流程。

```python
class ETLPipeline:
    def __init__(self, write_mysql=True, write_csv=True, output_dir="data/etl_output")
    def run_full(self, date_range, perspective="actual", store_no=None) -> ETLResult
    def run_stores(self, store_no=None) -> pd.DataFrame
    def run_store_loss(self, date_range, perspective, store_no=None) -> pd.DataFrame
    def run_pos_orders(self, date_range, store_no=None) -> pd.DataFrame
    def run_monthly_metrics(self, date_range, store_no=None) -> pd.DataFrame
```

### 2. SalesLoader (`src/data/etl/loader.py`)

从 StarRocks 读取数据，复用 `scripts/etl_sql/` 中的 SQL。

- 支持双口径：`d1_pf_`（业绩口径）和 `d2_`（返利口径）
- 参数化查询（`:param` 语法），防止 SQL 注入
- 返回标准化的 DataFrame
- `load_unified_sales()` 生成损益 + POS 聚合的统一宽表

### 3. MySQLWriter (`src/data/etl/writer.py`)

将加工后的数据写入本地 MySQL（profit_forecast 数据库）。

- 使用 `INSERT ... ON DUPLICATE KEY UPDATE`（upsert）
- 分批写入（batch_size=500），避免大事务
- 写入表：stores, store_daily_sales, store_monthly_metrics, cost_structure

### 4. CSVWriter (`src/data/etl/writer.py`)

输出 CSV 文件到指定目录。支持 stores / daily_sales / monthly_metrics / unified_sales。

## 返利口径处理 (`src/data/etl/rebate.py`)

### compare_perspectives(actual_df, rebate_df)

对比业绩口径（d1_pf_）和返利口径（d2_）的差异：
- `sales_diff` / `sales_diff_pct` — 销售额差异及比率
- `gross_profit_diff` — 毛利差异
- `operating_profit_diff` — 营业利润差异

### summarize_rebate_impact(comparison_df)

按门店汇总返利影响：
- `total_sales_diff` / `total_gp_diff` / `total_op_diff` — 总差异
- `avg_sales_diff_pct` — 平均差异率
- `stores_positive` / `stores_negative` — 正向/负向门店数

## 高仿真 Mock 数据

### 新店开业效应（"先高后低"）

`sales_collector.py` 和 `mock_collector.py` 中的新店（ST0017-ST0020 / ST0041-ST0045）：

| 开业月龄 | 效应系数 | 含义 |
|---------|---------|------|
| 0-3月 | 1.40 | 开业促销期，高于稳态 40% |
| 4-6月 | 1.20 | 促销效应减弱 |
| 7-12月 | 1.05 | 接近稳态 |
| 12月+ | 1.00 | 稳态 |

### 其他仿真特性

- **周末效应**：周末日收入 ×1.20
- **品牌差异化**：品牌A(1.2)、品牌B(1.0)、品牌C(0.85)
- **区域差异化**：华东(1.15)、华南(1.0)、华北(0.9)
- **季节波动**：11-12月旺季(1.2-1.3)，1-2月淡季(0.65-0.70)
- **返利系数**：每店独立返利系数(0.93-1.05)，返利 ≠ 随机噪声
- **新店折扣更深**：开业期折扣 0.45-0.85，成熟店 0.55-1.0

## Orchestrator 集成 (`src/agents/orchestrator.py`)

### adapter 选项

| adapter | 数据源 | 用途 |
|---------|--------|------|
| `"mock"` | SalesDataCollector (Mock) | 开发/测试 |
| `"starrocks"` | SalesDataCollector (StarRocks) | 直连查询 |
| `"etl"` | ETLDataAgent (SalesLoader) | ETL Pipeline |

### run_etl() 方法

ETL + 利润测算一体化流程：
1. 从 StarRocks 提取数据 → 写入本地 MySQL/CSV
2. 用提取的数据执行利润测算（基线→利润→风险→分配）

## 数据流

1. **门店主数据**：StarRocks `dws_pub.dws_dim_org_allinfo` → `stores` 表
2. **日损益**：StarRocks `proj_facana.ads_fin_fact_day_storeloss_pp` → `store_daily_sales` 表
3. **POS 订单**：StarRocks `ads_pub.ads_fact_pos_ord_analysis` → POS 聚合
4. **月度指标**：从日损益聚合 → `store_monthly_metrics` 表

## 口径切换

- `perspective="actual"` → 使用 `d1_pf_*` 字段（业绩口径，默认）
- `perspective="rebate"` → 使用 `d2_*` 字段（返利口径）

## 文件清单

| 文件 | 用途 |
|------|------|
| `src/data/etl/__init__.py` | 模块导出 |
| `src/data/etl/pipeline.py` | ETLPipeline + ETLResult |
| `src/data/etl/loader.py` | SalesLoader（StarRocks 读取） |
| `src/data/etl/writer.py` | MySQLWriter + CSVWriter |
| `src/data/etl/rebate.py` | 返利口径对比与汇总 |
| `src/agents/etl_data_agent.py` | ETLDataAgent（接入 Orchestrator） |
| `src/agents/orchestrator.py` | 支持 adapter="etl" + run_etl() |
| `scripts/etl_sql/*.sql` | 10 个 SQL 查询脚本 |
| `tests/unit/test_etl_pipeline.py` | ETL Pipeline 测试（8 个） |
| `tests/unit/test_rebate.py` | 返利处理测试（11 个） |
| `tests/unit/test_mock_high_fidelity.py` | 高仿真 Mock 测试（14 个） |
