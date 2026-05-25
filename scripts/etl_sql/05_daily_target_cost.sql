-- ============================================================
-- ETL 05: 日目标数据
-- 数据源: dws_pub.dws_fact_day_org_target_cost (日店铺基础目标表)
-- 用途: 获取门店日度/月度销售目标
-- 输出: 门店目标数据，用于承压分配
-- 注意: 分区字段 p_mon (YYYYMM)，建议指定以避免全表扫描
-- ============================================================

SELECT
    org_lno                                    AS store_code,             -- 门店编码
    period_sdate                               AS target_date,            -- 目标日期
    brd_dtl_no                                 AS brand_code,             -- 品牌编码
    store_brd                                  AS store_brand,            -- 门店品牌
    day_amt_target                             AS daily_sales_target,     -- 日营业目标
    mon_amt_target                             AS monthly_sales_target,   -- 月营业目标
    year_amt_target                            AS yearly_sales_target,    -- 年营业目标
    cust_sal_nos_qty_target                    AS customer_qty_target,    -- 客件数目标
    cust_sal_price_target                      AS customer_price_target,  -- 客单价目标
    avg_price_target                           AS avg_price_target,       -- 均价目标
    virtual_mon_amt_target                     AS virtual_monthly_target, -- 虚拟月目标
    clg_mon_amt_target                         AS challenge_monthly_target, -- 挑战月目标
    offline_mon_amt_target                     AS offline_monthly_target, -- 线下月目标
    sy_mon_amt_target                          AS private_domain_target,  -- 私域月目标
    live_mon_amt_target                        AS live_stream_target,     -- 直播月目标
    wholesale_amt_target                       AS wholesale_target,       -- 批发目标
    p_mon                                      AS partition_month         -- 分区月份
FROM dws_pub.dws_fact_day_org_target_cost
WHERE p_mon >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%Y%m')
  AND p_mon <= DATE_FORMAT(CURDATE(), '%Y%m')
  AND period_sdate >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 90 DAY), '%Y%m%d')
ORDER BY org_lno, period_sdate
;
