# profit-forecast v0.1 — 销售驱动利润测算系统设计文档

> 版本：v0.1 | 日期：2026-05-25 | 状态：待实施

---

## 0. 项目策略：新建独立项目

**不在原项目上修改**，而是复制一份新的项目文件夹。

| 项目 | 路径 | 说明 |
|------|------|------|
| 原项目 | `profit-forecast/` | 完整多功能版本（含客流、库存、6 Agent 全功能），保留不动 |
| v0.1 | `profit-forecast-v0.1/` | 销售驱动精简版，从原项目复制后裁剪 |

**操作步骤**：

```bash
# 1. 复制原项目（排除 node_modules、.venv、.git、__pycache__）
cp -r profit-forecast/ profit-forecast-v0.1/
cd profit-forecast-v0.1/
rm -rf node_modules .venv .git __pycache__ .pytest_cache

# 2. 初始化新 git 仓库
git init
git add .
git commit -m "v0.1: 从 profit-forecast 复制，作为销售驱动利润测算起点"

# 3. 按本文档裁剪和修改
```

**两个项目独立演进**：
- 原项目继续保留全功能版本，后续可接入客流、库存等数据
- v0.1 专注销售驱动，后续逐步填充成本数据

---

## 目录

0. [项目策略](#0-项目策略新建独立项目)
1. [核心理念](#1-核心理念)
2. [数据层设计](#2-数据层设计)
3. [基线预估模块](#3-基线预估模块)
4. [折扣预测模块](#4-折扣预测模块)
5. [承压分配模块](#5-承压分配模块)
6. [利润测算模块](#6-利润测算模块)
7. [预测模块](#7-预测模块)
8. [风险评估模块](#8-风险评估模块)
9. [Agent 编排层](#9-agent-编排层)
10. [前端设计](#10-前端设计)
11. [Docker 编排](#11-docker-编排)
12. [v0.1 与原项目差异总结](#12-v01-与原项目差异总结)
13. [新增文件清单](#13-新增文件清单)
14. [修改文件清单](#14-修改文件清单)

---

## 1. 核心理念

v0.1 定位：**以销售数据为唯一真实输入的端到端利润测算系统**。

### 1.1 数据流全景

```
┌─────────────────────────────────────────────────────────┐
│                    数据层（3 张源表）                      │
│  ads_fact_pos_ord_analysis    ← POS 订单明细              │
│  ads_fin_fact_day_storeloss_pp ← 门店损益（业绩口径）      │
│  ads_fin_fact_day_storeloss_pp_gj ← 门店损益（管理口径）   │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│              基线预估（从销售数据推算）                      │
│  日销售额 → 月度趋势 → 季节因子 → 基线收入                 │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│              承压分配（销售目标分解）                       │
│  总目标 × 门店权重 × 压力系数 → 单店目标                   │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│              利润测算（从 storeloss 取真实损益数据）         │
│  收入 → COGS → 毛利 → 经营费用 → 营业利润 → 店铺贡献      │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│              风险评估（基于销售波动）                       │
│  销售额波动率 → 达标概率 → 风险等级                       │
└─────────────────────────────────────────────────────────┘
```

### 1.2 设计原则

- **销售驱动**：所有模块的输入数据来源统一为 3 张销售表
- **结构保留**：成本相关的字段和公式保留结构，数据从 storeloss 表直接取值
- **可演进**：每个模块都可以在 v0.2+ 无缝接入更多数据源（客流、库存等）
- **双口径**：保留业绩口径（d1_pf_*）和返利口径（d2_*）对比能力

---

## 2. 数据层设计

### 2.1 三表定位与用途

| 表名 | 定位 | v0.1 用途 | 关键字段 |
|------|------|----------|---------|
| `ads_fact_pos_ord_analysis` | POS 订单明细 | 销售明细分析（折扣、件数、客单价、新旧货） | `sal_amt`, `sal_qty`, `discount_rate`, `brd_dtl_no`, `org_lno`, `period_sdate` |
| `ads_fin_fact_day_storeloss_pp` | 门店损益（业绩口径） | **主表** — 日粒度销售额 + 完整损益结构 | `d1_pf_total_sal_amt_pp`(业绩额), `d1_pf_total_sal_amt`(损益收入), `d1_pf_hq_notax_gross_profit`(毛利), `store_no`, `base_date` |
| `ads_fin_fact_day_storeloss_pp_gj` | 门店损益（管理口径） | 对比校验 — 同一指标的管理视角 | 同上结构，`d2_*` 字段 |

### 2.2 数据流向

```
ads_fact_pos_ord_analysis ──┐
                            ├──→ 统一销售宽表 ──→ 各业务模块
ads_fin_fact_day_storeloss_pp ──┘
       │
       └──→ ads_fin_fact_day_storeloss_pp_gj（校验用）
```

### 2.3 统一销售宽表（v0.1 新增）

从 3 张表聚合出一张日+门店粒度的宽表，作为下游所有模块的统一输入：

| 字段 | 来源 | 说明 |
|------|------|------|
| `store_no` | storeloss | 门店编码 |
| `base_date` | storeloss | 日期 |
| `brand` | storeloss.brand_detail_abbreviation | 品牌 |
| `region` | storeloss.region_top | 大区 |
| `province` | storeloss.province | 省份 |
| `managing_city` | storeloss.managing_city | 管理城市 |
| `business_city` | storeloss.business_city | 经营城市 |
| `shop_category` | storeloss.shop_category | 店铺类型 |
| `business_attribute` | storeloss.business_attribute | 经营属性 |
| `sales_amount` | storeloss.d1_pf_total_sal_amt_pp | 业绩额 |
| `revenue` | storeloss.d1_pf_total_sal_amt | 损益收入 |
| `settlement_amt` | storeloss.d1_pf_settlement_amt | 结款额 |
| `gross_profit` | storeloss.d1_pf_hq_notax_gross_profit | 总部无税毛利 |
| `gross_net_profit` | storeloss.d1_pf_hq_notax_gross_net_profit | 总部无税毛利净额 |
| `operating_expense` | storeloss.d1_pf_operating_exp | 经营费用 |
| `bmanaging_exp` | storeloss.d1_pf_bmanaging_exp | B管理费用 |
| `operating_profit` | storeloss.d1_pf_hq_notax_operating_profit | 营业利润 |
| `store_contribution` | storeloss.d1_pf_store_contribution1 | 店铺贡献 |
| `salary_fee` | storeloss.d1_pf_salary_fee | 工资 |
| `social_fee` | storeloss.d1_pf_social_fee | 社保公积金 |
| `comprehensive_mall_fee` | storeloss.d1_pf_comprehensive_mall_fee | 商场综合收费 |
| `decorate_fee` | storeloss.d1_pf_decorate_fee | 装修费 |
| `express` | storeloss.d1_pf_express | 快递费 |
| `all_other_fee` | storeloss.d1_pf_all_other_fee | 其他费用 |
| `hq_taxcost` | storeloss.d1_pf_hq_taxcost | 总部含税成本 |
| `additional_taxes` | storeloss.d1_pf_additional_taxes | 附加税金 |
| `server_fee` | storeloss.d1_pf_server_fee | 服务收支 |
| `nonoperating_in_out` | storeloss.d1_pf_nonoperating_in_out | 营业外收支 |
| `order_count` | pos_ord (聚合 COUNT DISTINCT order_no) | 订单数 |
| `qty_sold` | pos_ord (聚合 SUM sal_qty) | 销售件数 |
| `avg_discount` | pos_ord (聚合 AVG discount_rate) | 平均折扣率 |
| `prm_amt` | storeloss.d1_pf_total_prm_amt | 牌价收入 |
| `perspective` | 固定值 "actual" | 口径标识 |

返利口径（d2_*）同理，另建 `unified_sales_rebate` 宽表。

### 2.4 采集器设计

保留适配器模式，新增 `SalesDataCollector` 作为统一入口：

```python
class SalesDataCollector(BaseCollector):
    """统一销售数据采集器"""

    def collect_store_loss(self, store_no: str, date_range: tuple) -> pd.DataFrame:
        """采集门店损益数据（业绩口径）"""

    def collect_store_loss_gj(self, store_no: str, date_range: tuple) -> pd.DataFrame:
        """采集门店损益数据（管理口径）"""

    def collect_pos_orders(self, store_no: str, date_range: tuple) -> pd.DataFrame:
        """采集 POS 订单数据"""

    def collect_unified_sales(self, store_no: str, date_range: tuple,
                               perspective: str = "actual") -> pd.DataFrame:
        """聚合生成统一销售宽表"""
```

保留现有采集器：
- `StarRocksCollector` — StarRocks 直连
- `MockCollector` — 模拟数据
- `DataWorksCollector` — DataWorks API

---

## 3. 基线预估模块

### 3.1 核心逻辑

从历史销售额推算未来基线收入：

```
历史日销售额（storeloss 表）
    │
    ▼
时间序列分解（趋势 + 季节性 + 残差）
    │
    ├──→ 趋势项：近 N 天移动平均 / 线性回归
    ├──→ 季节项：月度/周度季节指数（从历史同期计算）
    └──→ 残差项：异常值检测（节假日、促销 spike）
    │
    ▼
基线收入 = 趋势 × 季节指数 × 门店类型系数
```

### 3.2 门店分类（精简版）

保留现有 6 分类逻辑，分类依据只用销售数据：

| 分类 | 判定依据（v0.1） | 估算器 |
|------|-----------------|--------|
| 新店 | 开店日期 < 6 个月 | `NewStoreEstimator` — 用爬坡曲线 |
| 大店 | 月均销售额 > 阈值 | `LargeStoreEstimator` — 用同级别大店均值 |
| 小店 | 月均销售额 < 阈值 | `SmallStoreEstimator` — 用同区域小店均值 |
| 临时店 | 店铺类型标记 | `TempStoreEstimator` — 用短周期数据 |
| 虚拟店 | 线上标记 | `VirtualStoreEstimator` — 用线上渠道数据 |
| 闭店 | 关店日期有值 | `ClosingStoreEstimator` — 按剩余天数折算 |

### 3.3 砍掉的输入

- ~~客流数据（enter_store_qty）~~ — 不参与基线计算
- ~~库存数据（balance_qty, total_inv_qty）~~ — 不参与基线计算
- ~~进店转化率~~ — 不参与基线计算

### 3.4 保留的文件

| 文件 | 用途 | 变化 |
|------|------|------|
| `seasonal_index.py` | 季节指数 | 改为用销售额计算 |
| `store_classifier.py` | 门店分类 | 改为用销售数据判定 |
| `lunar_calendar.py` | 农历节假日效应 | 无变化 |
| `spring_festival.py` | 春节特殊处理 | 无变化 |
| `outlier_detector.py` | 异常值检测 | 无变化 |
| `time_series.py` | 时间序列基础模型 | 无变化 |
| `baseline_engine.py` | 基线引擎 | 去掉客流/库存输入 |
| `new_store_estimator.py` | 新店估算器 | 无变化 |
| `large_store_estimator.py` | 大店估算器 | 无变化 |
| `small_store_estimator.py` | 小店估算器 | 无变化 |
| `temp_store_estimator.py` | 临时店估算器 | 无变化 |
| `virtual_store_estimator.py` | 虚拟店估算器 | 无变化 |
| `closing_store_estimator.py` | 闭店估算器 | 无变化 |

### 3.5 API 端点

```
POST /api/forecast/baseline
  输入: { store_no, date_range, method: "auto" }
  输出: {
    baseline_revenue: float,
    confidence_interval: [lower, upper],
    store_type: str,
    seasonal_factor: float,
    trend: str  # "up" | "stable" | "down"
  }
```

---

## 4. 折扣预测模块

### 4.1 方法论：同比趋势 + 品牌季节修正

**两层结合**：

| 层级 | 方法 | 作用 |
|------|------|------|
| **底层** | 同比折扣趋势法 | 提供时间维度的折扣基线 |
| **上层** | 品牌季节折扣矩阵 | 提供商品维度的折扣修正 |

**公式**：

```
预测折扣 = 同比折扣基线 × 品牌季节修正系数

品牌季节修正系数 = 该品牌季节当前平均折扣 / 该品牌季节去年同期平均折扣
```

### 4.2 同比折扣趋势法

```
去年本月折扣率 ──┐
                 ├──→ 加权/插值 ──→ 今年本月~下月折扣预算
去年下月折扣率 ──┘
```

从 POS 表按（品牌, 月份）聚合，计算月度平均折扣率，取去年同期值作为基线。

### 4.3 品牌季节折扣矩阵

从 POS 表的 `brd_season_type_name`（品牌季节类型）和 `lsg_mon_qty`（上市月数）字段，构建折扣衰减曲线：

| 品牌季节 | 典型折扣模式 | 生命周期 |
|---------|------------|---------|
| 当季新品 | 9-10 折（接近正价） | 上市 0-3 个月 |
| 上季品 | 6-8 折（适度促销） | 上市 4-6 个月 |
| 旧款 | 3-5 折（清仓） | 上市 7 个月+ |

### 4.4 实现

```
ads_fact_pos_ord_analysis
    │
    ├──→ 按 (品牌, 品牌季节, 上市月数) 聚合 → 折扣衰减曲线
    │
    ├──→ 按 (品牌, 月份) 聚合 → 同比折扣趋势
    │
    └──→ 合并 → 月度折扣预测
```

**新增字段到统一宽表**：

| 字段 | 说明 |
|------|------|
| `avg_discount_rate` | 当月实际平均折扣率 |
| `discount_yoy_ratio` | 同比折扣比（今年/去年） |
| `brand_season_discount_index` | 品牌季节折扣指数 |
| `forecast_discount_rate` | 预测折扣率 |

**新增文件**：

| 文件 | 说明 |
|------|------|
| `src/forecasting/discount/__init__.py` | 模块初始化 |
| `src/forecasting/discount/predictor.py` | 折扣率预测器 |
| `src/forecasting/discount/brand_season_matrix.py` | 品牌季节折扣矩阵 |
| `scripts/etl_sql/10_discount_matrix.sql` | 折扣矩阵构建 SQL |

### 4.5 API 端点

```
POST /api/forecast/discount
  输入: { brand: str, months_ahead: int }
  输出: {
    forecast: [
      { month: str, discount_rate: float, confidence: float }
    ],
    method: str,
    brand_season_matrix: dict
  }
```

---

## 5. 承压分配模块

### 5.1 分配流程

```
公司总目标（输入）
    │
    ▼
门店权重计算
    ├── 历史销售额占比（主权重）
    ├── 门店类型系数（新店/大店/小店 加权）
    └── 区域系数（大区/地区平衡）
    │
    ▼
初次分配 → 单店目标 = 总目标 × 门店权重
    │
    ▼
约束检查
    ├── 最低目标（不能低于历史基线 × 0.5）
    ├── 最高目标（不能超过历史基线 × 2.0）
    └── 区域总量校验（各区域目标之和 = 总目标）
    │
    ▼
压力模拟（可选）
    ├── 乐观场景：目标 × 0.9
    ├── 基准场景：目标 × 1.0
    └── 悲观场景：目标 × 1.1
    │
    ▼
最终分配结果
```

### 5.2 与 v0.1 的结合点

| 模块 | 输入来源 | 变化 |
|------|---------|------|
| 门店权重 | storeloss 表的历史销售额 | 只用销售数据，不用客流/库存 |
| 门店类型 | store_classifier（基于销售数据分类） | 沿用基线模块的分类结果 |
| 约束检查 | 基线收入（from 基线模块） | 依赖基线模块输出 |
| 压力模拟 | 固定系数 | 无变化 |

### 5.3 保留的文件

| 文件 | 用途 | 变化 |
|------|------|------|
| `target_allocator.py` | 目标分配主逻辑 | 无变化 |
| `weight_calculator.py` | 权重计算 | 输入改为销售数据 |
| `constraint_checker.py` | 约束检查 | 无变化 |
| `fairness_checker.py` | 公平性检查 | 无变化 |
| `scenario_simulator.py` | 情景模拟 | 无变化 |

### 5.4 API 端点

```
POST /api/allocation/allocate
  输入: {
    total_target: float,
    date_range: [start, end],
    method: "weighted" | "equal" | "custom"
  }
  输出: {
    store_targets: [
      { store_no: str, target: float, weight: float, constraints: dict }
    ],
    scenarios: {
      optimistic: dict,
      base: dict,
      pessimistic: dict
    }
  }
```

---

## 6. 利润测算模块

### 6.1 公式结构（完整保留）

```
单店净利润 = 收入 - 采购成本 - 人工 - 租金 - 物业 - 营销 - 物流 - 折旧 - 其他 - 税费
```

### 6.2 数据来源（v0.1）

storeloss 表的 `d1_pf_*` 字段已包含完整的损益结构，大部分成本项可直接取真实数据：

| 成本项 | v0.1 数据来源 | 状态 |
|--------|-------------|------|
| 收入 | `d1_pf_total_sal_amt` | 真实数据 |
| 采购成本 COGS | `d1_pf_hq_taxcost` | 真实数据 |
| 毛利 | `d1_pf_hq_notax_gross_profit` | 真实数据 |
| 毛利净额 | `d1_pf_hq_notax_gross_net_profit` | 真实数据 |
| 经营费用 | `d1_pf_operating_exp` | 真实数据 |
| 营业利润 | `d1_pf_hq_notax_operating_profit` | 真实数据 |
| 店铺贡献 | `d1_pf_store_contribution1` | 真实数据 |
| 工资 | `d1_pf_salary_fee` | 真实数据 |
| 社保公积金 | `d1_pf_social_fee` | 真实数据 |
| 商场综合收费 | `d1_pf_comprehensive_mall_fee` | 真实数据 |
| 装修费 | `d1_pf_decorate_fee` | 真实数据 |
| 快递费 | `d1_pf_express` | 真实数据 |
| 其他费用 | `d1_pf_all_other_fee` | 真实数据 |
| B管理费用 | `d1_pf_bmanaging_exp` | 真实数据 |
| 附加税金 | `d1_pf_additional_taxes` | 真实数据 |
| 服务收支 | `d1_pf_server_fee` | 真实数据 |
| 营业外收支 | `d1_pf_nonoperating_in_out` | 真实数据 |
| 租金物业 | 置零 | v0.2 从 `d1_pf_a_rental + d1_pf_a_property` 填充 |
| 税费（所得税） | 置零 | v0.2 接入税务数据 |

### 6.3 利润层次（四层）

| 层级 | 公式 | v0.1 数据来源 |
|------|------|-------------|
| 毛利 | 收入 - COGS | `d1_pf_hq_notax_gross_profit` |
| 毛利净额 | 毛利 - 附加税 | `d1_pf_hq_notax_gross_net_profit` |
| 营业利润 | 毛利净额 - 经营费用 - B管理费 | `d1_pf_hq_notax_operating_profit` |
| 店铺贡献 | 营业利润 - 服务收支 - 营业外 | `d1_pf_store_contribution1` |

### 6.4 双口径对比

保留业绩口径（d1_pf_*）和返利口径（d2_*）对比能力，前端可切换。

### 6.5 保留的文件

| 文件 | 用途 | 变化 |
|------|------|------|
| `profit_calculator.py` | 利润计算主逻辑 | 改为从 storeloss 表直接取值 |
| `cost_estimator.py` | 成本预估 | 保留，用于默认值填充 |
| `profit_report.py` | 利润报告 | 无变化 |
| `drill_down.py` | 按维度下钻 | 无变化 |

### 6.6 API 端点

```
POST /api/profit/calculate
  输入: {
    scope: { store_no: str } | { region: str } | { brand: str },
    date_range: [start, end],
    perspective: "actual" | "rebate"
  }
  输出: ProfitSummary（四层利润 + 各成本项明细 + 双口径对比）

GET /api/profit/drill-down
  输入: { dimension: "region" | "brand" | "store", date_range: [start, end] }
  输出: 按维度聚合的利润明细
```

---

## 7. 预测模块

### 7.1 预测目标

| 预测对象 | 说明 | 用途 |
|---------|------|------|
| 门店月销售额 | 单店未来 1-3 月销售额 | 基线预估输入 |
| 品牌月销售额 | 品牌维度汇总 | 品牌策略参考 |
| 区域月销售额 | 大区/地区汇总 | 区域目标分配 |
| 折扣率预测 | 未来月度平均折扣 | 利润测算修正 |

### 7.2 模型矩阵

| 模型 | 适用场景 | v0.1 输入变化 |
|------|---------|-------------|
| ARIMA | 销售趋势平稳的门店 | 只用销售额序列，去掉客流/库存外生变量 |
| Prophet | 有明显季节性和节假日效应 | 保留节假日因子，去掉客流 regressor |
| ExponentialSmoothing | 短期预测（1-4 周） | 只用销售额 |
| EnsembleModel | 多模型加权融合 | 保留，自动选最优权重 |
| ModelSelector | 自动选模型 | 保留，按 MAPE 选最优 |

### 7.3 预测流程

```
历史销售额（storeloss，近 12 个月）
    │
    ▼
数据预处理
    ├── 缺失值填充（线性插值）
    ├── 异常值检测（outlier_detector）
    └── 节假日标记（lunar_calendar + spring_festival）
    │
    ▼
模型选择（ModelSelector）
    ├── 对每个门店跑 ARIMA / Prophet / ES
    ├── 用最近 3 个月做回测
    └── 选 MAPE 最小的模型
    │
    ▼
预测输出
    ├── 点预测值
    ├── 置信区间（80% / 95%）
    └── 预测精度指标（MAPE, RMSE）
```

### 7.4 砍掉的预测

- ~~客流预测~~ — 不引入客流数据
- ~~库存预测~~ — 不引入库存数据
- ~~转化率预测~~ — 不引入客流数据

### 7.5 保留的文件

| 文件 | 用途 | 变化 |
|------|------|------|
| `arima_model.py` | ARIMA 模型 | 去掉外生变量 |
| `prophet_model.py` | Prophet 模型 | 去掉 regressor |
| `exponential_smoothing.py` | 指数平滑 | 无变化 |
| `ensemble_model.py` | 集成模型 | 无变化 |
| `model_selector.py` | 模型选择器 | 无变化 |
| `outlier_detector.py` | 异常值检测 | 无变化 |
| `seasonal_decompose.py` | 季节分解 | 无变化 |
| `time_series.py` | 时间序列基础 | 无变化 |
| `backtester.py` | 回测 | 无变化 |
| `accuracy_metrics.py` | 精度指标 | 无变化 |

### 7.6 API 端点

```
POST /api/forecast/predict
  输入: {
    scope: { store_no: str } | { brand: str } | { region: str },
    horizon: int,  # 预测月数
    model: "auto" | "arima" | "prophet" | "es"
  }
  输出: {
    predictions: [
      { date: str, value: float, lower: float, upper: float }
    ],
    model_used: str,
    accuracy: { mape: float, rmse: float }
  }
```

---

## 8. 风险评估模块

### 8.1 风险评估维度

| 维度 | 计算逻辑 | 数据来源 |
|------|---------|---------|
| 达标概率 | 基于历史销售波动率，蒙特卡洛模拟目标达成概率 | storeloss 历史销售额 |
| 压力分布 | 各门店目标 vs 基线的偏离度分布 | 基线模块 + 分配模块输出 |
| 区域风险 | 按大区/地区聚合达标概率，识别高风险区域 | 门店级结果聚合 |
| 品牌风险 | 按品牌聚合，识别下滑品牌 | POS 表按品牌聚合 |
| 趋势风险 | 近 3 个月销售趋势是上升/平稳/下降 | storeloss 时间序列 |

### 8.2 达标概率计算

```
历史日销售额 → 计算均值 μ 和标准差 σ
    │
    ▼
正态假设：月销售额 ~ N(30μ, √30 × σ)
    │
    ▼
蒙特卡洛模拟（1000 次）
    │
    ▼
达标概率 = P(模拟销售额 ≥ 目标) = 达标次数 / 1000
```

### 8.3 风险等级

| 达标概率 | 等级 | 颜色 | 建议 |
|---------|------|------|------|
| >= 80% | 低风险 | 绿 | 维持策略 |
| 60%-80% | 中风险 | 黄 | 关注并微调 |
| 40%-60% | 高风险 | 橙 | 需要干预 |
| < 40% | 极高风险 | 红 | 紧急调整 |

### 8.4 情景模拟（三场景）

| 场景 | 假设 | 用途 |
|------|------|------|
| 乐观 | 销售额 = 基线 x 1.1 | 上行空间评估 |
| 基准 | 销售额 = 基线 x 1.0 | 基准预期 |
| 悲观 | 销售额 = 基线 x 0.9 | 下行风险评估 |

每个场景分别计算利润，输出利润区间。

### 8.5 砍掉的

- ~~客流转化率风险~~ — 不引入客流数据
- ~~库存周转风险~~ — 不引入库存数据

### 8.6 保留的文件

| 文件 | 用途 | 变化 |
|------|------|------|
| `risk_assessor.py` | 风险评估主逻辑 | 改为基于销售波动 |
| `pressure_distribution.py` | 压力分布 | 无变化 |
| `reachability.py` | 达标概率 | 保留蒙特卡洛模拟 |
| `scenario_modeler.py` | 情景模拟 | 无变化 |
| `risk_report.py` | 风险报告 | 无变化 |

### 8.7 API 端点

```
POST /api/risk/assess
  输入: {
    scope: { store_no: str } | { region: str },
    date_range: [start, end],
    target: float
  }
  输出: {
    risk_level: str,
    reachability_prob: float,
    pressure_score: float,
    scenarios: {
      optimistic: { revenue: float, profit: float },
      base: { revenue: float, profit: float },
      pessimistic: { revenue: float, profit: float }
    }
  }

GET /api/risk/report
  输入: { date_range: [start, end], group_by: "region" | "brand" }
  输出: 风险汇总报告（含高风险门店清单）
```

---

## 9. Agent 编排层

### 9.1 Agent 架构

```
                    ┌─────────────┐
                    │ Orchestrator│  总调度
                    └──────┬──────┘
                           │
          ┌────────┬───────┼───────┬────────┐
          ▼        ▼       ▼       ▼        ▼
      ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
      │ Data │ │Base- │ │Profit│ │ Risk │ │Alloc-│
      │Agent │ │line  │ │Agent │ │Agent │ │ation │
      │      │ │Agent │ │      │ │      │ │Agent │
      └──────┘ └──────┘ └──────┘ └──────┘ └──────┘
```

### 9.2 各 Agent 职责

| Agent | v0.1 职责 | 输入 | 输出 |
|-------|----------|------|------|
| DataAgent | 采集 3 张销售表数据，生成统一宽表 | 3 张源表 | 统一销售 DataFrame |
| BaselineAgent | 从销售数据推算基线收入 + 折扣预测 | 统一宽表 | 基线收入 + 折扣率 |
| ProfitAgent | 计算四层利润，支持双口径对比 | 基线/目标 + 宽表 | ProfitSummary |
| RiskAgent | 蒙特卡洛模拟达标概率 + 情景分析 | 基线 + 目标 | 风险等级 + 概率 |
| AllocationAgent | 按权重分配销售目标 | 总目标 + 基线 | 单店目标 |
| Orchestrator | 编排全流程，管理 Agent 间数据传递 | 用户请求 | 最终报告 |

### 9.3 编排流程

```
用户请求（输入门店/区域/品牌 + 时间范围）
    │
    ▼
Orchestrator 接收
    │
    ├──→ Step 1: DataAgent.collect()
    │       输出: 统一销售宽表
    │
    ├──→ Step 2: BaselineAgent.estimate()
    │       输入: 统一宽表
    │       输出: 基线收入 + 折扣预测
    │
    ├──→ Step 3: AllocationAgent.allocate()（如果给了总目标）
    │       输入: 总目标 + 基线
    │       输出: 单店目标
    │
    ├──→ Step 4: ProfitAgent.calculate()
    │       输入: 基线或目标 + 宽表
    │       输出: 利润测算结果
    │
    ├──→ Step 5: RiskAgent.assess()
    │       输入: 基线 + 目标 + 历史波动
    │       输出: 风险评估
    │
    └──→ 汇总输出完整报告
```

### 9.4 与现有代码的差异

| 文件 | 变化 |
|------|------|
| `orchestrator.py` | 简化流程，去掉库存/客流相关步骤 |
| `data_agent.py` | 改为调用 SalesDataCollector |
| `baseline_agent.py` | 去掉客流/库存输入，只用销售数据 |
| `profit_agent.py` | 改为从 storeloss 表直接取损益数据 |
| `risk_agent.py` | 去掉库存周转风险，只评估销售达标风险 |
| `allocation_agent.py` | 无大变化，输入来源改变 |

### 9.5 API 端点

```
POST /api/orchestrate/full
  输入: {
    scope: { stores: [str], regions: [str], brands: [str] },
    date_range: [start, end],
    total_target: float  # 可选
  }
  输出: {
    baseline: dict,
    allocation: dict,
    profit: ProfitSummary,
    risk: dict,
    summary: dict
  }

POST /api/orchestrate/quick
  输入: { store_no: str, date_range: [start, end] }
  输出: 单店快速测算结果
```

---

## 10. 前端设计

### 10.1 页面结构

| 页面 | 功能 | 核心组件 |
|------|------|---------|
| 总览 Dashboard | 全局利润概览 | 利润四层卡片、区域地图、Top10 门店、趋势折线图 |
| 门店明细 | 单店利润下钻 | 门店损益表、成本结构饼图、销售趋势、折扣分析 |
| 预测分析 | 销售预测 + 折扣预测 | 预测折线图、模型对比、置信区间、折扣衰减曲线 |
| 风险监控 | 风险等级 + 达标概率 | 风险热力图、达标概率分布、情景对比、高风险清单 |
| Agent 监控 | Agent 状态、执行进度、数据流转 | 流程进度条、Agent 详情卡片、数据流向图、执行历史表 |

### 10.2 Dashboard 页面布局

```
┌─────────────────────────────────────────────────────────┐
│  利润测算系统 v0.1                          [日期选择]   │
├─────────┬─────────┬─────────┬───────────────────────────┤
│  总收入  │  毛利   │ 营业利润 │  店铺贡献                 │
│  ¥12.5M │ ¥6.8M  │ ¥2.1M  │  ¥1.8M                   │
│  ↑ 8.2% │ 54.5%  │ 16.8%  │  14.2%                    │
├─────────┴─────────┴─────────┴───────────────────────────┤
│                                                         │
│  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │  区域利润分布         │  │  品牌利润 Top 10         │  │
│  │  [地图/柱状图]        │  │  [横向柱状图]            │  │
│  └─────────────────────┘  └─────────────────────────┘  │
│                                                         │
│  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │  月度利润趋势         │  │  达标率 / 风险等级       │  │
│  │  [折线图，双口径]      │  │  [环形图 + 列表]        │  │
│  └─────────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 10.3 门店明细页面

```
┌─────────────────────────────────────────────────────────┐
│  门店: ST0001 滔搏运动城 XX店    [业绩口径 ▼] [日期选择] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │  损益表              │  │  成本结构                │  │
│  │  收入     ¥500,000  │  │  [饼图]                  │  │
│  │  COGS    ¥225,000  │  │  工资 35%               │  │
│  │  毛利     ¥275,000  │  │  商场 20%               │  │
│  │  经营费用  ¥120,000  │  │  装修 15%               │  │
│  │  营业利润  ¥155,000  │  │  其他 30%               │  │
│  └─────────────────────┘  └─────────────────────────┘  │
│                                                         │
│  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │  销售趋势（12 个月）  │  │  折扣分析                │  │
│  │  [折线图]            │  │  [柱状图：折扣衰减曲线]   │  │
│  └─────────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 10.4 Agent 监控页面

```
┌─────────────────────────────────────────────────────────┐
│  Agent 状态监控                              [刷新] [日志]│
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  流程进度                                         │    │
│  │  [DataAgent ✅] → [Baseline ⏳] → [Profit ⬜]    │    │
│  │                → [Risk ⬜] → [Allocation ⬜]      │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │  Agent 详情          │  │  数据流转                │  │
│  │                     │  │                         │  │
│  │  DataAgent          │  │  源表 → 宽表 → 基线      │  │
│  │  状态: 运行中        │  │  → 利润 → 风险          │  │
│  │  耗时: 2.3s         │  │  [流向图]                │  │
│  │  数据量: 1,234 行   │  │                         │  │
│  │  [查看日志]          │  │                         │  │
│  └─────────────────────┘  └─────────────────────────┘  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  执行历史                                         │    │
│  │  时间        Agent       状态    耗时    数据量    │    │
│  │  14:32:01   DataAgent   ✅     2.3s   1,234     │    │
│  │  14:32:03   Baseline    ⏳     —      —         │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 10.5 技术栈

沿用现有：
- React + TypeScript
- Ant Design 组件库
- ECharts 图表
- Vite 构建

---

## 11. Docker 编排

### 11.1 服务架构

```
docker-compose.yml
    │
    ├── app（FastAPI 后端）
    │     ├── port: 8000
    │     ├── depends_on: mysql, redis
    │     └── env: .env
    │
    ├── frontend（React 前端）
    │     ├── port: 3000
    │     └── nginx 反向代理 → app:8000
    │
    ├── mysql（元数据存储）
    │     ├── port: 3306
    │     ├── user: root
    │     ├── password: ycf0312!
    │     └── init.sql（建表）
    │
    └── redis（缓存，可选）
          └── port: 6379
```

### 11.2 环境变量

```bash
# MySQL 元数据库
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=ycf0312!
MYSQL_DATABASE=profit_forecast

# StarRocks 数据源
STARROCKS_HOST=your-starrocks-host
STARROCKS_PORT=9030

# 表名配置
TABLE_POS_ORD=ads_pub.ads_fact_pos_ord_analysis
TABLE_STORE_LOSS=proj_facana.ads_fin_fact_day_storeloss_pp
TABLE_STORE_LOSS_GJ=proj_facana.ads_fin_fact_day_storeloss_pp_gj

# 口径选择
DEFAULT_PERSPECTIVE=actual  # actual | rebate
```

### 11.3 MySQL 存储内容

| 表 | 用途 |
|------|------|
| `calculation_history` | 测算历史记录（谁、何时、算的什么） |
| `forecast_results` | 预测结果存储 |
| `risk_assessments` | 风险评估结果 |
| `allocation_plans` | 目标分配方案 |
| `system_config` | 系统配置（默认参数、阈值） |

### 11.4 代码层面变化

| 文件 | 变化 |
|------|------|
| `src/db/session.py` | `postgresql://` → `mysql+pymysql://` |
| `src/db/models.py` | SQLAlchemy 模型适配 MySQL 语法 |
| `alembic/env.py` | 迁移脚本适配 MySQL |
| `docker/init.sql` | PostgreSQL 语法 → MySQL 语法 |
| `pyproject.toml` | `psycopg2` → `pymysql` |

---

## 12. v0.1 与现有项目差异总结

| 维度 | 现有项目 | v0.1 变化 |
|------|---------|----------|
| 数据源 | 多种适配器（StarRocks/Mock/DataWorks） | 聚焦 3 张销售表，新增 SalesDataCollector |
| 基线预估 | 6 分类 + 季节指数 + 客流/库存输入 | 6 分类保留，只用销售数据 |
| 折扣预测 | 无 | 新增：同比趋势 + 品牌季节矩阵 |
| 利润测算 | 通用公式 + 默认值 | 从 storeloss 取真实损益数据，更丰富 |
| 风险评估 | 含库存周转风险 | 只评估销售达标风险 |
| 预测模型 | ARIMA/Prophet 含外生变量 | 去掉客流/库存外生变量 |
| Agent 编排 | 6 Agent | 6 Agent 保留，职责聚焦销售 |
| 前端 | 4 页面 | 5 页面（保留 Agent 监控） |
| 数据库 | PostgreSQL | MySQL |
| Docker | 含 StarRocks 本地容器 | 只保留 app + mysql + redis |

---

## 13. 新增文件清单

| 文件 | 说明 |
|------|------|
| `src/data/collectors/sales_collector.py` | 统一销售数据采集器 |
| `src/forecasting/discount/__init__.py` | 折扣预测模块初始化 |
| `src/forecasting/discount/predictor.py` | 折扣率预测器 |
| `src/forecasting/discount/brand_season_matrix.py` | 品牌季节折扣矩阵 |
| `scripts/etl_sql/09_unified_sales.sql` | 统一销售宽表 SQL |
| `scripts/etl_sql/10_discount_matrix.sql` | 折扣矩阵构建 SQL |

---

## 14. 修改文件清单

| 文件 | 变化 |
|------|------|
| `src/data/collectors/starrocks_collector.py` | 适配 3 张表 |
| `src/forecasting/models/arima_model.py` | 去掉外生变量 |
| `src/forecasting/models/prophet_model.py` | 去掉 regressor |
| `src/forecasting/models/exponential_smoothing.py` | 无变化 |
| `src/forecasting/models/ensemble_model.py` | 无变化 |
| `src/forecasting/models/model_selector.py` | 无变化 |
| `src/forecasting/baseline/outlier_detector.py` | 无变化 |
| `src/forecasting/baseline/seasonal_decompose.py` | 无变化 |
| `src/forecasting/baseline/time_series.py` | 无变化 |
| `src/forecasting/rules/baseline_engine.py` | 去掉客流/库存输入 |
| `src/forecasting/rules/store_classifier.py` | 改为用销售数据判定 |
| `src/forecasting/rules/new_store_estimator.py` | 无变化 |
| `src/forecasting/rules/large_store_estimator.py` | 无变化 |
| `src/forecasting/rules/small_store_estimator.py` | 无变化 |
| `src/forecasting/rules/temp_store_estimator.py` | 无变化 |
| `src/forecasting/rules/virtual_store_estimator.py` | 无变化 |
| `src/forecasting/rules/closing_store_estimator.py` | 无变化 |
| `src/forecasting/rules/lunar_calendar.py` | 无变化 |
| `src/forecasting/rules/spring_festival.py` | 无变化 |
| `src/forecasting/rules/seasonal_index.py` | 改为用销售额计算 |
| `src/forecasting/evaluation/backtester.py` | 无变化 |
| `src/forecasting/evaluation/accuracy_metrics.py` | 无变化 |
| `src/profit/profit_calculator.py` | 改为从 storeloss 取真实数据 |
| `src/profit/cost_estimator.py` | 适配新数据结构 |
| `src/profit/profit_report.py` | 无变化 |
| `src/profit/drill_down.py` | 无变化 |
| `src/risk/risk_assessor.py` | 改为基于销售波动 |
| `src/risk/pressure_distribution.py` | 无变化 |
| `src/risk/reachability.py` | 无变化 |
| `src/risk/scenario_modeler.py` | 无变化 |
| `src/risk/risk_report.py` | 无变化 |
| `src/allocation/target_allocator.py` | 无变化 |
| `src/allocation/weight_calculator.py` | 输入改为销售数据 |
| `src/allocation/constraint_checker.py` | 无变化 |
| `src/allocation/fairness_checker.py` | 无变化 |
| `src/allocation/scenario_simulator.py` | 无变化 |
| `src/agents/orchestrator.py` | 简化流程 |
| `src/agents/data_agent.py` | 改为调用 SalesDataCollector |
| `src/agents/baseline_agent.py` | 去掉客流/库存输入 |
| `src/agents/profit_agent.py` | 改为从 storeloss 取数据 |
| `src/agents/risk_agent.py` | 只评估销售风险 |
| `src/agents/allocation_agent.py` | 输入来源改变 |
| `src/api/routes/forecast.py` | 端点适配 |
| `src/api/routes/profit.py` | 端点适配 |
| `src/api/routes/risk.py` | 端点适配 |
| `src/api/routes/allocation.py` | 端点适配 |
| `src/api/routes/orchestrate.py` | 端点适配 |
| `src/api/routes/data_import.py` | 端点适配 |
| `src/api/routes/stores.py` | 无变化 |
| `src/api/routes/health.py` | 无变化 |
| `src/db/session.py` | PostgreSQL → MySQL |
| `src/db/models.py` | 适配 MySQL |
| `alembic/env.py` | 适配 MySQL |
| `docker/init.sql` | 适配 MySQL 语法 |
| `docker-compose.yml` | postgres → mysql |
| `docker/docker-compose.prod.yml` | postgres → mysql |
| `pyproject.toml` | psycopg2 → pymysql |
| `.env.example` | 新增表名配置 |
| `frontend/src/pages/*.tsx` | 页面内容适配 |
