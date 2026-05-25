# ETL SQL 脚本说明

## 数据源总览

| 序号 | SQL 文件 | 数据源表 | 用途 | 优先级 |
|------|----------|---------|------|--------|
| 01 | `01_stores.sql` | `dws_pub.dws_dim_org_allinfo` | 门店主数据 | 必需 |
| 02 | `02_store_loss.sql` | `proj_facana.ads_fin_fact_day_storeloss_pp` | 门店日损益（**核心**） | **必需** |
| 03 | `03_monthly_metrics.sql` | `proj_facana.dwd_f04_dayone_countbase_pp_new` | 月度指标聚合 | 必需 |
| 04 | `04_cost_structure.sql` | `proj_facana.dwd_f04_dayone_countbase_pp_new` | 成本结构明细 | 推荐 |
| 05 | `05_daily_target_cost.sql` | `dws_pub.dws_fact_day_org_target_cost` | 日目标数据 | 可选 |
| 06 | `06_switch_status.sql` | `dws_pub.dws_dim_org_on_off` | 开关状态 | 可选 |
| 07 | `07_pos_orders.sql` | `spark_catalog.ads_pub.ads_fact_pos_ord_analysis` | POS 订单明细 | 可选 |
| 08 | `08_store_info.sql` | `proj_facana.dwd_f04_dayone_s_store_info` | 门店扩充信息 | 可选 |

## 最小数据集

跑通利润测算**最少需要 3 张表**的数据：

1. **`01_stores.sql`** — 门店主数据（门店编码、名称、区域）
2. **`02_store_loss.sql`** — 门店日损益（真实成本结构的来源）
3. **`03_monthly_metrics.sql`** — 月度指标（基线预估的数据源）

## 使用方式

### 方式一：直接在 StarRocks 客户端执行

将 SQL 复制到 StarRocks 的 MySQL 客户端（如 DBeaver、Navicat、mysql CLI）中执行，将结果导出为 CSV。

### 方式二：使用 Python 脚本自动采集 + 测算

```bash
# 确保 .env 配置了 StarRocks 连接信息
# STARROCKS_HOST=xxx
# STARROCKS_PORT=9030
# STARROCKS_USER=xxx
# STARROCKS_PASSWORD=xxx
# STARROCKS_DATABASE=xxx

# 运行完整利润测算
python scripts/run_real_profit.py

# 指定总目标
python scripts/run_real_profit.py --target 10000000

# 只跑部分门店
python scripts/run_real_profit.py --stores ST0001,ST0002,ST0003

# 导出结果
python scripts/run_real_profit.py --export result.csv
```

### 方式三：只导出原始数据

```bash
# 导出全部表
python scripts/export_to_csv.py

# 导出到指定目录
python scripts/export_to_csv.py --output ./data/export

# 只导出核心表
python scripts/export_to_csv.py --tables stores,store_loss,monthly_metrics
```

## 口径说明（store_loss 表）

`ads_fin_fact_day_storeloss_pp` 包含多种会计口径：

| 前缀 | 口径 | 说明 |
|------|------|------|
| `d1_pf_` | 业绩口径（地区版） | **默认使用**，门店真实经营数据 |
| `d2_` | 返利口径 | 考虑返利后的真实收入 |
| `d4_` | 预算地区口径 | 年度预算分解 |
| `d6_` | 预算考核口径 | 考核用预算 |
| `d1t_` | 同期 | 去年同期数据 |

利润测算默认使用 `d1_pf_`（业绩口径）。如需切换口径，修改 `CostEstimator.from_store_loss_data()` 中的 `revenue_perspective` 参数。

## 数据质量注意事项

1. **日期范围**：建议取最近 90 天数据，太早的数据可能不具代表性
2. **不含当天**：当天数据可能不完整，SQL 中已排除
3. **门店筛选**：只取 `store_status=1 AND is_entity=1` 的在营实体门店
4. **cogs_ratio 异常值**：成本率限制在 [0.20, 0.80] 范围内，防止数据异常
5. **无数据降级**：无损益数据的门店会自动使用默认成本比例
