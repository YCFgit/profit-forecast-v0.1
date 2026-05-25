-- scripts/etl_sql/09_unified_sales.sql
-- 统一销售宽表：从 storeloss + POS 聚合

-- 门店损益基础数据（业绩口径）
CREATE TABLE IF NOT EXISTS unified_sales_daily AS
SELECT
    store_no,
    base_date,
    brand_detail_abbreviation AS brand,
    region_top AS region,
    province,
    managing_city,
    business_city,
    shop_category,
    business_attribute,
    d1_pf_total_sal_amt_pp AS sales_amount,
    d1_pf_total_sal_amt AS revenue,
    d1_pf_settlement_amt AS settlement_amt,
    d1_pf_total_prm_amt AS prm_amt,
    d1_pf_hq_taxcost AS hq_taxcost,
    d1_pf_hq_notax_gross_profit AS gross_profit,
    d1_pf_hq_notax_gross_net_profit AS gross_net_profit,
    d1_pf_additional_taxes AS additional_taxes,
    d1_pf_operating_exp AS operating_expense,
    d1_pf_bmanaging_exp AS bmanaging_exp,
    d1_pf_server_fee AS server_fee,
    d1_pf_nonoperating_in_out AS nonoperating_in_out,
    d1_pf_hq_notax_operating_profit AS operating_profit,
    d1_pf_store_contribution1 AS store_contribution,
    d1_pf_salary_fee AS salary_fee,
    d1_pf_social_fee AS social_fee,
    d1_pf_comprehensive_mall_fee AS comprehensive_mall_fee,
    d1_pf_decorate_fee AS decorate_fee,
    d1_pf_express AS express,
    d1_pf_all_other_fee AS all_other_fee
FROM proj_facana.ads_fin_fact_day_storeloss_pp;
