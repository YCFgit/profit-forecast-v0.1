-- ============================================================
-- ETL 07: POS 订单聚合（门店×日期 维度）
-- 数据源: hive.ads_pub.ads_fact_pos_ord_analysis
-- 用途: 按门店+日期聚合订单数、销量、折扣率
-- 输出: 门店日度 POS 聚合指标（非明细行）
-- 注意: 分区字段 p_mon (yyyymm)，必须指定以避免全表扫描
-- 优化: 直接在 SQL 层聚合，避免拉取海量明细行
-- ============================================================

SELECT
    sy_org_lno                                 AS store_code,        -- 业绩归属店号
    period_sdate                               AS sale_date,         -- 销售日期

    -- 订单聚合
    COUNT(DISTINCT order_no)                   AS order_count,       -- 订单数
    SUM(sal_qty)                               AS sales_qty,         -- 销售数量
    SUM(sal_amt)                               AS sales_amount,      -- 销售金额
    SUM(sal_prm_amt)                           AS tag_price_amount,  -- 吊牌金额

    -- 折扣
    CASE WHEN SUM(sal_prm_amt) > 0
         THEN 1 - SUM(discount_amt) / SUM(sal_prm_amt)
         ELSE 1.0 END                          AS discount_rate,     -- 折扣率（加权）

    -- 客单价
    CASE WHEN COUNT(DISTINCT order_no) > 0
         THEN SUM(sal_amt) / COUNT(DISTINCT order_no)
         ELSE 0 END                            AS avg_ticket,        -- 客单价

    -- 进店人数（取最大值，避免重复计数）
    MAX(enter_store_qty)                       AS foot_traffic       -- 进店人数

FROM hive.ads_pub.ads_fact_pos_ord_analysis
WHERE p_mon >= '202403'
  AND p_mon < '202603'
GROUP BY sy_org_lno, period_sdate
ORDER BY store_code, sale_date;