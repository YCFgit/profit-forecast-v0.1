-- ============================================================
-- ETL 06: 门店开关状态
-- 数据源: dws_pub.dws_dim_org_on_off (店铺开改关表)
-- 用途: 获取门店的开业/关店/改造事件，构建月度状态矩阵
-- 输出: 门店状态事件表
-- ============================================================

SELECT
    org_lno                                    AS store_code,        -- 门店编码
    org_name                                   AS store_name,        -- 门店名称
    brd_dtl_no                                 AS brand_code,        -- 品牌编码
    on_off_type                                AS event_type,        -- 事件类型(开店/关店/改造)
    plan_time                                  AS plan_time,         -- 计划时间
    real_time                                  AS actual_time,       -- 实际时间
    region_name                                AS region,            -- 区域
    biz_city_name                              AS city,              -- 城市
    biz_area                                   AS store_area,        -- 门店面积
    mon_avg_sal_amt                            AS avg_monthly_sales, -- 月均销售
    diff_status                                AS diff_status,       -- 差异状态
    last_plan_time                             AS latest_plan_time   -- 最近计划时间
FROM dws_pub.dws_dim_org_on_off
ORDER BY org_lno, plan_time
;
