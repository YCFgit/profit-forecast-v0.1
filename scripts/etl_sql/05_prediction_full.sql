-- ============================================================
-- 预测完整 SQL（等价于 BaselineEngine 全流程）
-- 目标: 预测指定月份所有门店的销售额
-- 使用方式: 修改 @TARGET_YEAR / @TARGET_MONTH 后直接执行
-- 数据源: store_monthly_metrics + stores
-- ============================================================

-- ============================================================
-- 参数设置（修改这里即可切换预测目标月）
-- ============================================================
SET @TARGET_YEAR = 2026;
SET @TARGET_MONTH = 6;

-- ============================================================
-- CTE 1: 春节月标记
-- 根据春节日期表，标记每年的春节所在月份
-- ============================================================
WITH spring_festival_months AS (
    SELECT 2024 AS yr, 2 AS mo UNION ALL  -- 2024春节在2月10日
    SELECT 2025, 1 UNION ALL               -- 2025春节在1月29日
    SELECT 2026, 2                         -- 2026春节在2月17日
),

-- ============================================================
-- CTE 2: 季节指数计算（品牌×区域×月）
-- 公式: raw = 该月均值 / 全部月均值
--        damped = 1 + (raw - 1) × 0.50
-- 排除春节月后计算
-- ============================================================
monthly_with_info AS (
    SELECT
        m.store_code,
        m.`year_month`,
        m.sales_amount,
        CAST(SUBSTR(m.`year_month`, 6, 2) AS UNSIGNED) AS cal_month,
        CAST(SUBSTR(m.`year_month`, 1, 4) AS UNSIGNED) AS cal_year,
        s.brand,
        s.region
    FROM store_monthly_metrics m
    JOIN stores s ON m.store_code = s.store_code
    WHERE m.sales_amount > 0
),
non_spring_monthly AS (
    -- 排除春节月
    SELECT mwi.*
    FROM monthly_with_info mwi
    LEFT JOIN spring_festival_months sfm
        ON mwi.cal_year = sfm.yr AND mwi.cal_month = sfm.mo
    WHERE sfm.yr IS NULL
),
brand_region_monthly_avg AS (
    -- 品牌×区域×月 的平均销售额
    SELECT
        brand,
        region,
        cal_month,
        AVG(sales_amount) AS month_avg
    FROM non_spring_monthly
    GROUP BY brand, region, cal_month
),
brand_region_overall_avg AS (
    -- 品牌×区域 的全部月平均
    SELECT
        brand,
        region,
        AVG(sales_amount) AS overall_avg
    FROM non_spring_monthly
    GROUP BY brand, region
),
seasonal_index AS (
    -- 季节指数 = 该月均值 / 全部月均值，再阻尼
    SELECT
        m.brand,
        m.region,
        m.cal_month,
        m.month_avg,
        o.overall_avg,
        CASE WHEN o.overall_avg > 0
             THEN m.month_avg / o.overall_avg
             ELSE 1.0
        END AS raw_index,
        CASE WHEN o.overall_avg > 0
             THEN 1.0 + (m.month_avg / o.overall_avg - 1.0) * 0.50
             ELSE 1.0
        END AS damped_index
    FROM brand_region_monthly_avg m
    JOIN brand_region_overall_avg o
        ON m.brand = o.brand AND m.region = o.region
),

-- ============================================================
-- CTE 3: 门店分类
-- 优先级: 关店 → 临时/虚拟 → 新店 → 大中店 → 小店
-- ============================================================
store_stats AS (
    -- 计算近6个非春节月的月均业绩和有效月数
    SELECT
        mwi.store_code,
        mwi.brand,
        mwi.region,
        COUNT(*) AS valid_months,
        AVG(mwi.sales_amount) AS avg_sales
    FROM monthly_with_info mwi
    LEFT JOIN spring_festival_months sfm
        ON mwi.cal_year = sfm.yr AND mwi.cal_month = sfm.mo
    WHERE sfm.yr IS NULL
      -- 近6个月（从目标月往前推6个月）
      AND mwi.`year_month` >= CONCAT(
          CASE WHEN @TARGET_MONTH <= 6
               THEN @TARGET_YEAR - 1
               ELSE @TARGET_YEAR
          END,
          '-',
          LPAD(CASE WHEN @TARGET_MONTH <= 6
               THEN @TARGET_MONTH + 6
               ELSE @TARGET_MONTH - 6
          END, 2, '0')
      )
      AND mwi.`year_month` < CONCAT(@TARGET_YEAR, '-', LPAD(@TARGET_MONTH, 2, '0'))
    GROUP BY mwi.store_code, mwi.brand, mwi.region
),
store_classification AS (
    SELECT
        s.store_code,
        s.brand,
        s.region,
        s.opening_date,
        s.closing_date,
        COALESCE(ss.valid_months, 0) AS valid_months,
        COALESCE(ss.avg_sales, 0) AS avg_sales,
        CASE
            -- 1. 关店: closing_date 在目标月或之前
            WHEN s.closing_date IS NOT NULL
                 AND s.closing_date != ''
                 AND s.closing_date <= CONCAT(@TARGET_YEAR, '-', LPAD(@TARGET_MONTH, 2, '0'), '-31')
            THEN 'closing'
            -- 2. 新店: opening_date 在去年1月1日之后
            WHEN s.opening_date IS NOT NULL
                 AND s.opening_date != ''
                 AND s.opening_date >= CONCAT(@TARGET_YEAR - 1, '-01-01')
            THEN 'new'
            -- 3. 大中店: 有效月>=3 且 月均>=3万
            WHEN COALESCE(ss.valid_months, 0) >= 3
                 AND COALESCE(ss.avg_sales, 0) >= 30000
            THEN 'large_medium'
            -- 4. 小店
            ELSE 'small'
        END AS category
    FROM stores s
    LEFT JOIN store_stats ss ON s.store_code = ss.store_code
    WHERE s.status = '正常' OR s.status IS NULL
),

-- ============================================================
-- CTE 4: 大中店预估（加权近月法）
-- weights = [0.35, 0.25, 0.18, 0.12, 0.07, 0.03]
-- ============================================================

-- 获取近6个非春节月的去季节化值（按月排列，带行号）
large_store_months AS (
    SELECT
        mwi.store_code,
        mwi.`year_month`,
        mwi.sales_amount,
        mwi.cal_month,
        mwi.cal_year,
        si.damped_index,
        -- 去季节化值
        CASE WHEN si.damped_index > 0
             THEN mwi.sales_amount / si.damped_index
             ELSE mwi.sales_amount
        END AS des_sales,
        -- 按时间倒序编号（最近的=1）
        ROW_NUMBER() OVER (
            PARTITION BY mwi.store_code
            ORDER BY mwi.cal_year DESC, mwi.cal_month DESC
        ) AS rn
    FROM monthly_with_info mwi
    LEFT JOIN spring_festival_months sfm
        ON mwi.cal_year = sfm.yr AND mwi.cal_month = sfm.mo
    LEFT JOIN seasonal_index si
        ON mwi.brand = si.brand
        AND mwi.region = si.region
        AND mwi.cal_month = si.cal_month
    JOIN store_classification sc ON mwi.store_code = sc.store_code
    WHERE sc.category = 'large_medium'
      AND sfm.yr IS NULL  -- 排除春节月
      AND mwi.`year_month` < CONCAT(@TARGET_YEAR, '-', LPAD(@TARGET_MONTH, 2, '0'))
),
large_store_weighted AS (
    SELECT
        store_code,
        -- 加权平均 (按行号对应权重)
        SUM(
            des_sales * CASE rn
                WHEN 1 THEN 0.35
                WHEN 2 THEN 0.25
                WHEN 3 THEN 0.18
                WHEN 4 THEN 0.12
                WHEN 5 THEN 0.07
                WHEN 6 THEN 0.03
                ELSE 0
            END
        ) / GREATEST(
            SUM(CASE rn
                WHEN 1 THEN 0.35
                WHEN 2 THEN 0.25
                WHEN 3 THEN 0.18
                WHEN 4 THEN 0.12
                WHEN 5 THEN 0.07
                WHEN 6 THEN 0.03
                ELSE 0
            END), 0.01
        ) AS weighted_des_avg,
        COUNT(*) AS data_months
    FROM large_store_months
    WHERE rn <= 6
    GROUP BY store_code
),
large_store_prediction AS (
    SELECT
        lsw.store_code,
        sc.brand,
        sc.region,
        'large_medium' AS category,
        -- 预测值 = 加权去季节化均值 × 目标月季节指数
        lsw.weighted_des_avg * COALESCE(si.damped_index, 1.0) AS predicted_sales,
        lsw.weighted_des_avg AS des_avg,
        COALESCE(si.damped_index, 1.0) AS seasonal_index,
        lsw.data_months,
        'weighted_recent' AS mechanism
    FROM large_store_weighted lsw
    JOIN store_classification sc ON lsw.store_code = sc.store_code
    LEFT JOIN seasonal_index si
        ON sc.brand = si.brand
        AND sc.region = si.region
        AND si.cal_month = @TARGET_MONTH
),

-- ============================================================
-- CTE 5: 小店预估（近3非春节月去季节化均值 × 目标月季节指数）
-- ============================================================
small_store_months AS (
    SELECT
        mwi.store_code,
        mwi.sales_amount,
        mwi.cal_month,
        mwi.cal_year,
        si.damped_index,
        CASE WHEN si.damped_index > 0
             THEN mwi.sales_amount / si.damped_index
             ELSE mwi.sales_amount
        END AS des_sales,
        ROW_NUMBER() OVER (
            PARTITION BY mwi.store_code
            ORDER BY mwi.cal_year DESC, mwi.cal_month DESC
        ) AS rn
    FROM monthly_with_info mwi
    LEFT JOIN spring_festival_months sfm
        ON mwi.cal_year = sfm.yr AND mwi.cal_month = sfm.mo
    LEFT JOIN seasonal_index si
        ON mwi.brand = si.brand
        AND mwi.region = si.region
        AND mwi.cal_month = si.cal_month
    JOIN store_classification sc ON mwi.store_code = sc.store_code
    WHERE sc.category = 'small'
      AND sfm.yr IS NULL
      AND mwi.`year_month` < CONCAT(@TARGET_YEAR, '-', LPAD(@TARGET_MONTH, 2, '0'))
),
small_store_avg AS (
    SELECT
        store_code,
        AVG(des_sales) AS des_avg,
        COUNT(*) AS data_months
    FROM small_store_months
    WHERE rn <= 3
    GROUP BY store_code
),
small_store_prediction AS (
    SELECT
        ssa.store_code,
        sc.brand,
        sc.region,
        'small' AS category,
        ssa.des_avg * COALESCE(si.damped_index, 1.0) AS predicted_sales,
        ssa.des_avg AS des_avg,
        COALESCE(si.damped_index, 1.0) AS seasonal_index,
        ssa.data_months,
        'deseasonalized_mean' AS mechanism
    FROM small_store_avg ssa
    JOIN store_classification sc ON ssa.store_code = sc.store_code
    LEFT JOIN seasonal_index si
        ON sc.brand = si.brand
        AND sc.region = si.region
        AND si.cal_month = @TARGET_MONTH
),

-- ============================================================
-- CTE 6: 新店预估（同品牌×区域成熟店中位数 × 爬坡系数）
-- ============================================================
new_store_ref AS (
    -- 同品牌×区域成熟店的月均业绩
    SELECT
        sc.brand,
        sc.region,
        AVG(sm.sales_amount) AS store_monthly_avg
    FROM store_classification sc
    JOIN store_monthly_metrics sm ON sc.store_code = sm.store_code
    WHERE sc.category = 'large_medium'
    GROUP BY sc.brand, sc.region, sc.store_code
    HAVING AVG(sm.sales_amount) >= 30000  -- 月均 >= 3万
),
new_store_median AS (
    -- 品牌×区域的中位数（用近似方法: AVG 代替中位数）
    SELECT
        brand,
        region,
        AVG(store_monthly_avg) AS ref_median
    FROM new_store_ref
    GROUP BY brand, region
),
new_store_prediction AS (
    SELECT
        sc.store_code,
        sc.brand,
        sc.region,
        'new' AS category,
        -- 参考中位数 × 爬坡系数
        COALESCE(nsm.ref_median, 0) *
        CASE
            WHEN TIMESTAMPDIFF(MONTH, STR_TO_DATE(sc.opening_date, '%Y-%m-%d'),
                 CONCAT(@TARGET_YEAR, '-', LPAD(@TARGET_MONTH, 2, '0'), '-01')) <= 3
            THEN 1.40
            WHEN TIMESTAMPDIFF(MONTH, STR_TO_DATE(sc.opening_date, '%Y-%m-%d'),
                 CONCAT(@TARGET_YEAR, '-', LPAD(@TARGET_MONTH, 2, '0'), '-01')) <= 6
            THEN 1.20
            WHEN TIMESTAMPDIFF(MONTH, STR_TO_DATE(sc.opening_date, '%Y-%m-%d'),
                 CONCAT(@TARGET_YEAR, '-', LPAD(@TARGET_MONTH, 2, '0'), '-01')) <= 12
            THEN 1.05
            ELSE 1.00
        END AS predicted_sales,
        COALESCE(nsm.ref_median, 0) AS des_avg,
        1.0 AS seasonal_index,
        0 AS data_months,
        'ramp_coefficient' AS mechanism
    FROM store_classification sc
    LEFT JOIN new_store_median nsm
        ON sc.brand = nsm.brand AND sc.region = nsm.region
    WHERE sc.category = 'new'
),

-- ============================================================
-- CTE 7: 关店预估（正常月预估 × 营业天数/总天数 × 0.90）
-- ============================================================
closing_store_months AS (
    SELECT
        mwi.store_code,
        mwi.sales_amount,
        mwi.cal_month,
        mwi.cal_year,
        si.damped_index,
        CASE WHEN si.damped_index > 0
             THEN mwi.sales_amount / si.damped_index
             ELSE mwi.sales_amount
        END AS des_sales,
        ROW_NUMBER() OVER (
            PARTITION BY mwi.store_code
            ORDER BY mwi.cal_year DESC, mwi.cal_month DESC
        ) AS rn
    FROM monthly_with_info mwi
    LEFT JOIN spring_festival_months sfm
        ON mwi.cal_year = sfm.yr AND mwi.cal_month = sfm.mo
    LEFT JOIN seasonal_index si
        ON mwi.brand = si.brand
        AND mwi.region = si.region
        AND mwi.cal_month = si.cal_month
    JOIN store_classification sc ON mwi.store_code = sc.store_code
    WHERE sc.category = 'closing'
      AND sfm.yr IS NULL
      AND mwi.`year_month` < CONCAT(@TARGET_YEAR, '-', LPAD(@TARGET_MONTH, 2, '0'))
),
closing_store_avg AS (
    SELECT
        store_code,
        AVG(des_sales) AS des_avg,
        COUNT(*) AS data_months
    FROM closing_store_months
    WHERE rn <= 3
    GROUP BY store_code
),
closing_store_prediction AS (
    SELECT
        sc.store_code,
        sc.brand,
        sc.region,
        'closing' AS category,
        -- 正常月预估 × 营业天数比例 × 0.90
        COALESCE(csa.des_avg, 0) * COALESCE(si.damped_index, 1.0)
        * CASE
            WHEN sc.closing_date IS NOT NULL AND sc.closing_date != ''
                 AND YEAR(STR_TO_DATE(sc.closing_date, '%Y-%m-%d')) = @TARGET_YEAR
                 AND MONTH(STR_TO_DATE(sc.closing_date, '%Y-%m-%d')) = @TARGET_MONTH
            THEN DAY(STR_TO_DATE(sc.closing_date, '%Y-%m-%d'))
                 / DAY(LAST_DAY(CONCAT(@TARGET_YEAR, '-', LPAD(@TARGET_MONTH, 2, '0'), '-01')))
            ELSE 1.0
          END
        * 0.90 AS predicted_sales,
        COALESCE(csa.des_avg, 0) AS des_avg,
        COALESCE(si.damped_index, 1.0) AS seasonal_index,
        COALESCE(csa.data_months, 0) AS data_months,
        'closing_adjusted' AS mechanism
    FROM store_classification sc
    LEFT JOIN closing_store_avg csa ON sc.store_code = csa.store_code
    LEFT JOIN seasonal_index si
        ON sc.brand = si.brand
        AND sc.region = si.region
        AND si.cal_month = @TARGET_MONTH
    WHERE sc.category = 'closing'
),

-- ============================================================
-- CTE 8: 合并所有预估结果
-- ============================================================
all_predictions AS (
    SELECT store_code, brand, region, category, predicted_sales, des_avg, seasonal_index, data_months, mechanism
    FROM large_store_prediction
    UNION ALL
    SELECT store_code, brand, region, category, predicted_sales, des_avg, seasonal_index, data_months, mechanism
    FROM small_store_prediction
    UNION ALL
    SELECT store_code, brand, region, category, predicted_sales, des_avg, seasonal_index, data_months, mechanism
    FROM new_store_prediction
    UNION ALL
    SELECT store_code, brand, region, category, predicted_sales, des_avg, seasonal_index, data_months, mechanism
    FROM closing_store_prediction
),

-- ============================================================
-- CTE 9: 置信区间（基于历史变异系数 CV）
-- ============================================================
store_cv AS (
    SELECT
        mwi.store_code,
        STDDEV(mwi.sales_amount) / NULLIF(AVG(mwi.sales_amount), 0) AS cv
    FROM monthly_with_info mwi
    LEFT JOIN spring_festival_months sfm
        ON mwi.cal_year = sfm.yr AND mwi.cal_month = sfm.mo
    WHERE sfm.yr IS NULL
      AND mwi.`year_month` >= CONCAT(@TARGET_YEAR - 1, '-', LPAD(@TARGET_MONTH, 2, '0'))
    GROUP BY mwi.store_code
)

-- ============================================================
-- 最终输出: 全量门店预测结果
-- ============================================================
SELECT
    ap.store_code,
    ap.brand,
    ap.region,
    ap.category,
    ap.mechanism,
    ROUND(ap.predicted_sales, 0) AS predicted_sales,
    ROUND(ap.des_avg, 0) AS deseasonalized_avg,
    ROUND(ap.seasonal_index, 4) AS seasonal_index,
    ap.data_months,
    -- 置信区间
    ROUND(ap.predicted_sales * (1 - LEAST(COALESCE(sc.cv, 0.2), 0.5)), 0) AS ci_low,
    ROUND(ap.predicted_sales, 0) AS ci_mid,
    ROUND(ap.predicted_sales * (1 + LEAST(COALESCE(sc.cv, 0.2), 0.5)), 0) AS ci_high,
    ROUND(LEAST(COALESCE(sc.cv, 0.2), 0.5), 4) AS cv
FROM all_predictions ap
LEFT JOIN store_cv sc ON ap.store_code = sc.store_code
ORDER BY ap.predicted_sales DESC;


-- ============================================================
-- 汇总查询（可选，取消注释使用）
-- ============================================================
-- SELECT
--     CONCAT(@TARGET_YEAR, '-', LPAD(@TARGET_MONTH, 2, '0')) AS target_month,
--     COUNT(*) AS store_count,
--     ROUND(SUM(predicted_sales), 0) AS total_predicted,
--     ROUND(AVG(predicted_sales), 0) AS avg_per_store,
--     SUM(CASE WHEN category = 'large_medium' THEN 1 ELSE 0 END) AS large_medium_count,
--     SUM(CASE WHEN category = 'small' THEN 1 ELSE 0 END) AS small_count,
--     SUM(CASE WHEN category = 'new' THEN 1 ELSE 0 END) AS new_count,
--     SUM(CASE WHEN category = 'closing' THEN 1 ELSE 0 END) AS closing_count,
--     ROUND(SUM(CASE WHEN category = 'large_medium' THEN predicted_sales ELSE 0 END), 0) AS large_medium_total,
--     ROUND(SUM(CASE WHEN category = 'small' THEN predicted_sales ELSE 0 END), 0) AS small_total,
--     ROUND(SUM(CASE WHEN category = 'new' THEN predicted_sales ELSE 0 END), 0) AS new_total,
--     ROUND(SUM(CASE WHEN category = 'closing' THEN predicted_sales ELSE 0 END), 0) AS closing_total
-- FROM (
--     SELECT * FROM large_store_prediction
--     UNION ALL SELECT * FROM small_store_prediction
--     UNION ALL SELECT * FROM new_store_prediction
--     UNION ALL SELECT * FROM closing_store_prediction
-- ) all_pred;


-- ============================================================
-- 品牌汇总（可选）
-- ============================================================
-- SELECT
--     brand,
--     COUNT(*) AS store_count,
--     ROUND(SUM(predicted_sales), 0) AS total_predicted,
--     ROUND(AVG(predicted_sales), 0) AS avg_per_store
-- FROM all_predictions
-- GROUP BY brand
-- ORDER BY total_predicted DESC;


-- ============================================================
-- 区域汇总（可选）
-- ============================================================
-- SELECT
--     region,
--     COUNT(*) AS store_count,
--     ROUND(SUM(predicted_sales), 0) AS total_predicted,
--     ROUND(AVG(predicted_sales), 0) AS avg_per_store
-- FROM all_predictions
-- GROUP BY region
-- ORDER BY total_predicted DESC;
