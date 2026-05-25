-- ============================================================
-- ETL 02: 门店日损益数据（核心！利润测算的真实数据源）
-- 数据源: proj_facana.ads_fin_fact_day_storeloss_pp
-- 用途: 获取门店每日损益明细，含业绩/返利/预算/同期多口径
-- 输出: 完整的门店日度 P&L 数据
-- ============================================================
-- 口径说明:
--   d1_pf_ : 业绩口径（地区版）—— 默认使用此口径
--   d2_    : 返利口径
--   d4_    : 预算地区口径
--   d6_    : 预算考核口径
--   d1t_   : 同期（去年同期）
-- ============================================================

SELECT
    store_no                                   AS store_code,        -- 门店编码
    base_date                                  AS sale_date,         -- 日期
    brand_detail_abbreviation                  AS brand,             -- 品牌
    store_name                                 AS store_name,        -- 门店名称
    region_top                                 AS region,            -- 大区
    region                                     AS sub_region,        -- 小区
    managing_city                              AS managing_city,     -- 管理城市
    business_city                              AS business_city,     -- 经营城市
    business_attribute                         AS business_attribute,-- 业态属性
    shop_category                              AS shop_category,     -- 店铺分类
    business_detail                            AS business_detail,   -- 业态明细
    store_type_new                             AS store_type_new,    -- 门店类型(新)
    org_structure_classification               AS channel_type,      -- 渠道类型

    -- ========== 当期实际（业绩口径 d1_pf_）==========
    d1_pf_total_sal_amt_pp                     AS actual_sales_pp,          -- 业绩口径销售额(地区)
    d1_pf_total_sal_amt                        AS actual_sales,             -- 业绩口径销售额
    d1_pf_hq_taxcost                           AS actual_cost,              -- 含税成本
    d1_pf_hq_notax_gross_profit                AS actual_gross_profit,      -- 不含税毛利
    d1_pf_operating_exp                        AS actual_operating_expense, -- 经营费用
    d1_pf_bmanaging_exp                        AS actual_b_manage_expense,  -- B管理费用
    d1_pf_hq_notax_operating_profit            AS actual_operating_profit,  -- 不含税营业利润
    d1_pf_comprehensive_mall_fee               AS actual_mall_fee,          -- 商场综合收费
    d1_pf_salary_fee                           AS actual_salary,            -- 工资
    d1_pf_fix_salary                           AS actual_fix_salary,        -- 固定工资
    d1_pf_float_salary                         AS actual_float_salary,      -- 浮动工资
    d1_pf_social_fee                           AS actual_social_fee,        -- 社保公积金
    d1_pf_decorate_fee                         AS actual_decorate_fee,      -- 装修费
    d1_pf_express                              AS actual_express,           -- 快递物流费
    d1_pf_all_other_fee                        AS actual_other_fee,         -- 其他费用
    d1_pf_store_contribution1                  AS actual_store_contribution,-- 门店贡献
    d1_pf_b_salary_social_fee                  AS actual_b_salary_social,   -- B管理-工资社保
    d1_pf_b_rental_property                    AS actual_b_rental_property, -- B管理-租赁物业
    d1_pf_b_warehousing_service                AS actual_b_warehousing,     -- B管理-仓储服务
    d1_pf_b_travel_expense                     AS actual_b_travel,          -- B管理-差旅
    d1_pf_b_labor_insurance_benefits           AS actual_b_labor_insurance, -- B管理-劳动保险
    d1_pf_b_all_other_fee                      AS actual_b_other_fee,       -- B管理-其他

    -- ========== 返利口径 d2_ ==========
    d2_total_sal_amt                           AS rebate_sales,             -- 返利销售额
    d2_hq_notax_gross_profit                   AS rebate_gross_profit,      -- 返利毛利
    d2_operating_exp                           AS rebate_operating_expense, -- 返利经营费用
    d2_hq_notax_operating_profit               AS rebate_operating_profit,  -- 返利营业利润
    d2_comprehensive_mall_fee                  AS rebate_mall_fee,          -- 返利商场费
    d2_salary_fee                              AS rebate_salary,            -- 返利工资

    -- ========== 预算地区口径 d4_ ==========
    d4_total_sal_amt_pp                        AS budget_sales_pp,          -- 预算销售额(地区)
    d4_total_sal_amt                           AS budget_sales,             -- 预算销售额
    d4_hq_notax_gross_profit                   AS budget_gross_profit,      -- 预算毛利
    d4_operating_exp                           AS budget_operating_expense, -- 预算经营费用
    d4_hq_notax_operating_profit               AS budget_operating_profit,  -- 预算营业利润
    d4_comprehensive_mall_fee                  AS budget_mall_fee,          -- 预算商场费
    d4_salary_fee                              AS budget_salary,            -- 预算工资

    -- ========== 预算考核口径 d6_ ==========
    d6_total_sal_amt_pp                        AS budget_eval_sales_pp,     -- 考核预算销售额(地区)
    d6_total_sal_amt                           AS budget_eval_sales,        -- 考核预算销售额
    d6_hq_notax_operating_profit               AS budget_eval_operating_profit, -- 考核预算营业利润

    -- ========== 同期 d1t_ ==========
    d1t_pf_total_sal_amt_pp                    AS ly_sales_pp,              -- 去年同期销售额(地区)
    d1t_pf_total_sal_amt                       AS ly_sales,                 -- 去年同期销售额
    d1t_pf_hq_notax_gross_profit               AS ly_gross_profit,          -- 去年同期毛利
    d1t_pf_hq_notax_operating_profit           AS ly_operating_profit,      -- 去年同期营业利润

    -- ========== ETL ==========
    etl_update_time                            AS etl_update_time           -- ETL更新时间
FROM proj_facana.ads_fin_fact_day_storeloss_pp
WHERE base_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)   -- 最近90天
  AND base_date < CURDATE()                                 -- 不含今天（数据可能不完整）
ORDER BY store_no, base_date
;
