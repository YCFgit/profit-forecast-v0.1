-- ============================================================
-- ETL 03: 月度指标（从日损益表聚合）
-- 数据源: proj_facana.dwd_f04_dayone_countbase_pp_new
-- 用途: 按门店+月份聚合销售、成本、利润等指标
-- 输出: 门店月度汇总指标，用于基线预估
-- ============================================================

SELECT
    store_no                                   AS store_code,        -- 门店编码
    SUBSTR(base_date, 1, 7)                    AS year_month,        -- 年月 (YYYY-MM)
    brand_detail_abbreviation                  AS brand,             -- 品牌

    -- 销售汇总
    SUM(total_sal_amt)                         AS sales_amount,      -- 销售额
    SUM(total_prm_amt)                         AS tag_price_amount,  -- 吊牌额
    SUM(shoes_sal_amt)                         AS shoes_sales,       -- 鞋类销售
    SUM(clothes_sal_amt)                       AS clothes_sales,     -- 服装销售
    SUM(bag_sal_amt)                           AS bag_sales,         -- 包类销售
    SUM(parts_sal_amt)                         AS parts_sales,       -- 配件销售

    -- 成本汇总
    SUM(taxcost)                               AS tax_cost,          -- 含税成本
    SUM(hq_taxcost)                            AS hq_tax_cost,       -- 总部含税成本

    -- 毛利汇总
    SUM(hq_notax_gross_profit)                 AS hq_notax_gross_profit,  -- 总部不含税毛利
    SUM(tax_gross_profit)                      AS tax_gross_profit,       -- 含税毛利

    -- 费用汇总
    SUM(operating_exp)                         AS operating_expense,      -- 经营费用
    SUM(bmanaging_exp)                         AS b_managing_expense,     -- B管理费用
    SUM(additional_taxes)                      AS additional_taxes,       -- 附加税

    -- 利润汇总
    SUM(notax_operating_profit)                AS notax_operating_profit,     -- 不含税营业利润
    SUM(hq_notax_operating_profit)             AS hq_notax_operating_profit,  -- 总部不含税营业利润
    SUM(notax_net_profit)                      AS notax_net_profit,           -- 不含税净利润
    SUM(hq_notax_net_profit)                   AS hq_notax_net_profit,        -- 总部不含税净利润
    SUM(net_profit)                            AS net_profit,                 -- 净利润

    -- 折扣率（加权平均）
    CASE WHEN SUM(total_prm_amt) > 0
         THEN SUM(sal_dct) / SUM(total_prm_amt)
         ELSE 0 END                            AS deduction_rate,     -- 折扣率

    -- 坪效（销售额 / 面积）
    CASE WHEN MAX(store_area) > 0
         THEN SUM(total_sal_amt) / MAX(store_area)
         ELSE 0 END                            AS sales_per_sqm,      -- 坪效

    -- 人效（销售额 / 人数）
    CASE WHEN MAX(staff_number) > 0
         THEN SUM(total_sal_amt) / MAX(staff_number)
         ELSE 0 END                            AS revenue_per_staff,   -- 人效

    -- 毛利率
    CASE WHEN SUM(total_sal_amt) > 0
         THEN SUM(hq_notax_gross_profit) / SUM(total_sal_amt)
         ELSE 0 END                            AS gross_margin,        -- 毛利率

    -- 营业利润率
    CASE WHEN SUM(total_sal_amt) > 0
         THEN SUM(notax_operating_profit) / SUM(total_sal_amt)
         ELSE 0 END                            AS operating_margin,    -- 营业利润率

    -- 净利率
    CASE WHEN SUM(total_sal_amt) > 0
         THEN SUM(notax_net_profit) / SUM(total_sal_amt)
         ELSE 0 END                            AS net_margin,          -- 净利率

    -- 门店属性
    MAX(store_area)                            AS store_area,          -- 门店面积
    MAX(staff_number)                          AS staff_count          -- 员工数

FROM proj_facana.dwd_f04_dayone_countbase_pp_new
WHERE SUBSTR(base_date, 1, 7) >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 6 MONTH), '%Y-%m')
  AND SUBSTR(base_date, 1, 7) < DATE_FORMAT(CURDATE(), '%Y-%m')
GROUP BY store_no, SUBSTR(base_date, 1, 7), brand_detail_abbreviation
ORDER BY store_no, year_month
;
