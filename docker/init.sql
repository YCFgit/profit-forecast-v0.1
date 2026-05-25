-- ============================================================
-- 鞋服零售利润测算系统 — 数据库初始化脚本
-- ============================================================

-- 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. 门店主数据
-- ============================================================
CREATE TABLE stores (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code      VARCHAR(32) NOT NULL UNIQUE,         -- 门店编码（业务主键）
    store_name      VARCHAR(128) NOT NULL,                -- 门店名称
    store_type      VARCHAR(32) NOT NULL DEFAULT 'direct', -- 类型: direct(直营) / franchise(加盟) / counter(商场专柜)
    channel_code    VARCHAR(32),                          -- 渠道编码
    region          VARCHAR(64),                          -- 区域
    province        VARCHAR(32),                          -- 省份
    city            VARCHAR(32),                          -- 城市
    address         VARCHAR(256),                         -- 详细地址
    commercial_tier VARCHAR(8) NOT NULL DEFAULT 'B',      -- 商圈等级: A/B/C/D
    store_area      DECIMAL(10,2),                        -- 经营面积（平米）
    opening_date    DATE,                                 -- 开业日期
    closing_date    DATE,                                 -- 关店日期（NULL=营业中）
    status          VARCHAR(16) NOT NULL DEFAULT 'active', -- 状态: active/closed/renovating
    manager_name    VARCHAR(64),                          -- 店长姓名
    staff_count     INTEGER,                              -- 编制人数
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stores_code ON stores(store_code);
CREATE INDEX idx_stores_region ON stores(region);
CREATE INDEX idx_stores_status ON stores(status);

-- ============================================================
-- 2. 品类主数据
-- ============================================================
CREATE TABLE product_categories (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_code   VARCHAR(32) NOT NULL UNIQUE,
    category_name   VARCHAR(64) NOT NULL,
    parent_code     VARCHAR(32),                          -- 父品类编码（支持多级）
    level           INTEGER NOT NULL DEFAULT 1,           -- 层级: 1=大类 2=中类 3=小类
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 3. 渠道主数据
-- ============================================================
CREATE TABLE channels (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_code    VARCHAR(32) NOT NULL UNIQUE,
    channel_name    VARCHAR(64) NOT NULL,
    channel_type    VARCHAR(32) NOT NULL,                 -- direct/franchise/online/mall
    commission_rate DECIMAL(5,4) DEFAULT 0,               -- 渠道扣点率
    description     TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 4. 门店日销数据
-- ============================================================
CREATE TABLE store_daily_sales (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code      VARCHAR(32) NOT NULL,
    sale_date       DATE NOT NULL,
    category_code   VARCHAR(32),                          -- 品类编码（NULL=全品类汇总）
    channel_code    VARCHAR(32),                          -- 渠道编码
    sales_amount    DECIMAL(14,2) NOT NULL DEFAULT 0,     -- 销售额
    sales_qty       INTEGER NOT NULL DEFAULT 0,           -- 销量
    avg_price       DECIMAL(10,2),                        -- 客单价
    discount_rate   DECIMAL(5,4) DEFAULT 1.0,             -- 折扣率
    return_amount   DECIMAL(14,2) DEFAULT 0,              -- 退货金额
    return_qty      INTEGER DEFAULT 0,                    -- 退货量
    customer_count  INTEGER DEFAULT 0,                    -- 客流量
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(store_code, sale_date, category_code, channel_code)
);

CREATE INDEX idx_daily_sales_store ON store_daily_sales(store_code);
CREATE INDEX idx_daily_sales_date ON store_daily_sales(sale_date);
CREATE INDEX idx_daily_sales_store_date ON store_daily_sales(store_code, sale_date);

-- ============================================================
-- 5. 门店月度指标
-- ============================================================
CREATE TABLE store_monthly_metrics (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code      VARCHAR(32) NOT NULL,
    year_month      VARCHAR(7) NOT NULL,                  -- 格式: 2026-01
    sales_amount    DECIMAL(14,2),                        -- 月销售额
    gross_profit    DECIMAL(14,2),                        -- 月毛利
    gross_margin    DECIMAL(5,4),                         -- 毛利率
    sales_per_sqm   DECIMAL(10,2),                        -- 坪效（元/平米/月）
    revenue_per_staff DECIMAL(10,2),                      -- 人效（元/人/月）
    avg_ticket      DECIMAL(10,2),                        -- 客单价
    return_rate     DECIMAL(5,4),                         -- 退货率
    staff_count     INTEGER,                              -- 实际在岗人数
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(store_code, year_month)
);

CREATE INDEX idx_monthly_metrics_store ON store_monthly_metrics(store_code);
CREATE INDEX idx_monthly_metrics_month ON store_monthly_metrics(year_month);

-- ============================================================
-- 6. 成本结构
-- ============================================================
CREATE TABLE cost_structure (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code      VARCHAR(32) NOT NULL,
    year_month      VARCHAR(7) NOT NULL,                  -- 格式: 2026-01
    procurement_cost DECIMAL(14,2) DEFAULT 0,             -- 采购成本
    labor_cost      DECIMAL(14,2) DEFAULT 0,              -- 人工成本（工资+社保+福利）
    rent_cost       DECIMAL(14,2) DEFAULT 0,              -- 租金
    logistics_cost  DECIMAL(14,2) DEFAULT 0,              -- 物流仓储
    marketing_cost  DECIMAL(14,2) DEFAULT 0,              -- 营销费用
    commission_cost DECIMAL(14,2) DEFAULT 0,              -- 渠道扣点
    other_cost      DECIMAL(14,2) DEFAULT 0,              -- 其他费用
    total_cost      DECIMAL(14,2) DEFAULT 0,              -- 总成本
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(store_code, year_month)
);

CREATE INDEX idx_cost_store ON cost_structure(store_code);

-- ============================================================
-- 7. 门店人员数据
-- ============================================================
CREATE TABLE store_staff (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code      VARCHAR(32) NOT NULL,
    staff_name      VARCHAR(64) NOT NULL,
    role            VARCHAR(32) NOT NULL DEFAULT 'staff', -- role: manager/supervisor/staff/trainee
    base_salary     DECIMAL(10,2),                        -- 基本工资
    commission_rate DECIMAL(5,4) DEFAULT 0,               -- 提成比例
    hire_date       DATE,                                 -- 入职日期
    leave_date      DATE,                                 -- 离职日期（NULL=在职）
    status          VARCHAR(16) NOT NULL DEFAULT 'active', -- active/leave
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_staff_store ON store_staff(store_code);
CREATE INDEX idx_staff_status ON store_staff(status);

-- ============================================================
-- 8. 目标数据（日/月）
-- ============================================================
CREATE TABLE store_targets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code      VARCHAR(32) NOT NULL,
    target_type     VARCHAR(16) NOT NULL,                 -- daily / monthly
    target_date     DATE,                                 -- 日目标日期
    target_month    VARCHAR(7),                           -- 月目标格式: 2026-01
    category_code   VARCHAR(32),                          -- 品类（NULL=全品类）
    sales_target    DECIMAL(14,2) NOT NULL DEFAULT 0,     -- 销售目标
    profit_target   DECIMAL(14,2) NOT NULL DEFAULT 0,     -- 利润目标
    source          VARCHAR(32) NOT NULL DEFAULT 'manual', -- 来源: manual/allocated/system
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(store_code, target_type, target_date, target_month, category_code)
);

CREATE INDEX idx_targets_store ON store_targets(store_code);
CREATE INDEX idx_targets_date ON store_targets(target_date, target_month);

-- ============================================================
-- 9. 分配方案（承压分配结果）
-- ============================================================
CREATE TABLE target_allocations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id         VARCHAR(64) NOT NULL,                 -- 分配方案ID
    plan_name       VARCHAR(128),                         -- 方案名称
    total_target    DECIMAL(14,2) NOT NULL,               -- 老板总目标
    store_code      VARCHAR(32) NOT NULL,
    baseline_profit DECIMAL(14,2) NOT NULL,               -- 基线利润 B_i
    pressure_amount DECIMAL(14,2) NOT NULL DEFAULT 0,     -- 承压额 Δ_i
    allocated_target DECIMAL(14,2) NOT NULL,              -- 分配目标 T_i
    growth_rate     DECIMAL(8,4),                         -- 增幅 (T_i - B_i) / B_i
    weight_score    DECIMAL(8,4),                         -- 综合权重 W_i
    weight_detail   JSONB,                                -- 各维度权重明细
    status          VARCHAR(16) NOT NULL DEFAULT 'draft', -- draft/confirmed/locked
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_allocations_plan ON target_allocations(plan_id);
CREATE INDEX idx_allocations_store ON target_allocations(store_code);

-- ============================================================
-- 10. 风险评估记录
-- ============================================================
CREATE TABLE risk_assessments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_id         VARCHAR(64) NOT NULL,                 -- 关联分配方案
    store_code      VARCHAR(32) NOT NULL,
    reachability    DECIMAL(8,4),                         -- 可达性 = T_i / B_i
    risk_level      VARCHAR(16) NOT NULL DEFAULT 'low',   -- low/mid/high
    risk_factors    JSONB,                                -- 风险因子明细
    scenario_optimistic DECIMAL(14,2),                    -- 乐观情景利润
    scenario_neutral    DECIMAL(14,2),                    -- 中性情景利润
    scenario_pessimistic DECIMAL(14,2),                   -- 悲观情景利润
    recommendations TEXT,                                 -- 建议措施
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_risk_plan ON risk_assessments(plan_id);
CREATE INDEX idx_risk_store ON risk_assessments(store_code);
CREATE INDEX idx_risk_level ON risk_assessments(risk_level);
