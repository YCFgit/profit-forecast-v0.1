-- ============================================================
-- ETL 04: 成本结构明细（从日损益表按月聚合）
-- 数据源: proj_facana.dwd_f04_dayone_countbase_pp_new
-- 用途: 获取门店每月的详细成本拆分（人工/租金/折旧等）
-- 输出: 门店月度成本明细，用于构建 CostStructure
-- ============================================================

SELECT
    store_no                                   AS store_code,        -- 门店编码
    SUBSTR(base_date, 1, 7)                    AS year_month,        -- 年月
    brand_detail_abbreviation                  AS brand,             -- 品牌

    -- 收入
    SUM(total_sal_amt)                         AS sales_amount,      -- 销售额
    SUM(total_prm_amt)                         AS tag_price_amount,  -- 吊牌额

    -- 销售成本
    SUM(taxcost)                               AS tax_cost,          -- 含税成本
    SUM(hq_taxcost)                            AS hq_tax_cost,       -- 总部含税成本
    SUM(notax_cost)                            AS notax_cost,        -- 不含税成本

    -- 经营费用明细
    SUM(operating_exp)                         AS total_operating_expense, -- 经营费用合计
    SUM(salary)                                AS salary,            -- 工资
    SUM(labor_service_fee)                     AS labor_service_fee, -- 劳务费
    SUM(depreciation_charge)                   AS depreciation,      -- 折旧
    SUM(property_fee)                          AS property_fee,      -- 物业费
    SUM(rental_fee)                            AS rent,              -- 租金
    SUM(social_security_fee)                   AS social_security,   -- 社保
    SUM(labor_insurance_fee)                   AS labor_insurance,   -- 劳保
    SUM(display_installation_fee)              AS display_installation, -- 陈列安装费
    SUM(promotion_fee)                         AS promotion,         -- 促销费
    SUM(packing_charge)                        AS packing,           -- 包装费
    SUM(trade_union_funds)                     AS trade_union,       -- 工会经费
    SUM(mall_charge)                           AS mall_charge,       -- 商场扣费
    SUM(office_supplies)                       AS office_supplies,   -- 办公用品
    SUM(repair_cost)                           AS repair,            -- 维修费
    SUM(communication_fee)                     AS communication,     -- 通讯费
    SUM(low_value_cons)                        AS low_value_consumption, -- 低值易耗品
    SUM(other_fee)                             AS other_fee,         -- 其他费用
    SUM(express_fee)                           AS express_fee,       -- 快递费

    -- B管理费用
    SUM(bmanaging_exp)                         AS b_managing_expense, -- B管理费用合计
    SUM(managing_exp)                          AS managing_expense,  -- 管理费用
    SUM(financial_exp)                         AS financial_expense, -- 财务费用

    -- 总部费用明细
    SUM(hq_salary)                             AS hq_salary,         -- 总部工资
    SUM(hq_depreciation_charge)                AS hq_depreciation,   -- 总部折旧
    SUM(hq_property_fee)                       AS hq_property_fee,   -- 总部物业
    SUM(hq_rental_fee)                         AS hq_rent,           -- 总部租金
    SUM(hq_promotion_fee)                      AS hq_promotion,      -- 总部促销
    SUM(hq_other_fee)                          AS hq_other_fee,      -- 总部其他

    -- 毛利与利润
    SUM(hq_notax_gross_profit)                 AS hq_notax_gross_profit,    -- 总部不含税毛利
    SUM(notax_operating_profit)                AS notax_operating_profit,   -- 不含税营业利润
    SUM(hq_notax_operating_profit)             AS hq_notax_operating_profit,-- 总部不含税营业利润
    SUM(notax_net_profit)                      AS notax_net_profit,         -- 不含税净利润
    SUM(net_profit)                            AS net_profit,               -- 净利润

    -- 附加税
    SUM(additional_taxes)                      AS additional_taxes,   -- 附加税

    -- 非经常性损益
    SUM(nonoperating_income)                   AS nonoperating_income,      -- 营业外收入
    SUM(nonoperating_expenditure)              AS nonoperating_expenditure, -- 营业外支出

    -- 所得税
    SUM(income_tax)                            AS income_tax          -- 所得税

FROM proj_facana.dwd_f04_dayone_countbase_pp_new
WHERE SUBSTR(base_date, 1, 7) >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 6 MONTH), '%Y-%m')
  AND SUBSTR(base_date, 1, 7) < DATE_FORMAT(CURDATE(), '%Y-%m')
GROUP BY store_no, SUBSTR(base_date, 1, 7), brand_detail_abbreviation
ORDER BY store_no, year_month
;
