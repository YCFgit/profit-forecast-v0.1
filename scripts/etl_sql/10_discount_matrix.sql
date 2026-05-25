-- scripts/etl_sql/10_discount_matrix.sql
-- 品牌季节折扣矩阵

-- 按品牌、品牌季节、上市月数聚合平均折扣率
CREATE TABLE IF NOT EXISTS brand_season_discount_matrix AS
SELECT
    brd_dtl_no AS brand_code,
    brd_dtl_abbr AS brand_name,
    brd_season_type_name AS season_type,
    lsg_mon_qty AS months_since_launch,
    COUNT(DISTINCT order_no) AS order_count,
    SUM(sal_amt) AS total_sales,
    SUM(sal_qty) AS total_qty,
    AVG(discount_rate) AS avg_discount_rate,
    STDDEV(discount_rate) AS discount_stddev
FROM ads_pub.ads_fact_pos_ord_analysis
WHERE discount_rate > 0 AND discount_rate <= 1
GROUP BY brd_dtl_no, brd_dtl_abbr, brd_season_type_name, lsg_mon_qty;

-- 按品牌、月份聚合同比折扣趋势
CREATE TABLE IF NOT EXISTS brand_monthly_discount_trend AS
SELECT
    brd_dtl_no AS brand_code,
    brd_dtl_abbr AS brand_name,
    SUBSTR(period_sdate, 1, 6) AS year_month,
    AVG(discount_rate) AS avg_discount_rate,
    COUNT(DISTINCT order_no) AS order_count
FROM ads_pub.ads_fact_pos_ord_analysis
WHERE discount_rate > 0 AND discount_rate <= 1
GROUP BY brd_dtl_no, brd_dtl_abbr, SUBSTR(period_sdate, 1, 6);
