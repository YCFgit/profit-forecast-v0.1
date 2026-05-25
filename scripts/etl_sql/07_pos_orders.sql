-- ============================================================
-- ETL 07: POS 订单明细
-- 数据源: spark_catalog.ads_pub.ads_fact_pos_ord_analysis
-- 用途: 获取门店订单明细，含品类/尺码/折扣/客流等维度
-- 输出: 订单级明细数据
-- 注意: 分区字段 p_mon (yyyymm)，必须指定以避免全表扫描
-- ============================================================

SELECT
    sy_org_lno                                 AS store_code,        -- 业绩归属店号
    period_sdate                               AS sale_date,         -- 销售日期
    brd_dtl_abbr                               AS brand,             -- 品牌
    brd_dtl_no                                 AS brand_code,        -- 品牌编码
    pro_no                                     AS product_code,      -- 商品编码
    pro_name                                   AS product_name,      -- 商品名称
    pro_cate_name                              AS category,          -- 品类
    size_code                                  AS size_code,         -- 尺码
    order_type                                 AS order_type,        -- 订单类型

    -- 销售数据
    sal_qty                                    AS sales_qty,         -- 销售数量
    sal_amt                                    AS sales_amount,      -- 销售金额
    sal_prm_amt                                AS tag_price_amount,  -- 吊牌金额
    sal_nos_prm_amt                            AS tag_price_no_material, -- 吊牌额(不含物料)

    -- 业绩
    sal_qty_sy                                 AS perf_qty,          -- 业绩数量
    sal_amt_sy                                 AS perf_amount,       -- 业绩金额
    sal_prm_amt_sy                             AS perf_tag_amount,   -- 业绩吊牌额

    -- 折扣
    discount_rate                              AS discount_rate,     -- 折扣率
    discount_amt                               AS discount_amount,   -- 折扣金额

    -- 客流
    enter_store_qty                            AS foot_traffic,      -- 进店人数

    -- 库存
    balance_qty                                AS stock_qty,         -- 库存数量
    balance_prm_amt                            AS stock_tag_amount,  -- 库存吊牌额
    total_inv_qty                              AS total_inv_qty,     -- 总库存

    -- 会员
    mem_id                                     AS member_id,         -- 会员ID
    level_attr                                 AS member_level,      -- 会员等级

    -- 订单信息
    order_no                                   AS order_no,          -- 订单号
    pay_time                                   AS pay_time,          -- 支付时间
    pay_name                                   AS pay_method,        -- 支付方式
    asst_no                                    AS staff_code,        -- 导购编码
    asst_name                                  AS staff_name,        -- 导购姓名

    -- 目标
    amt_target                                 AS daily_target,      -- 日目标
    mon_amt_target                             AS monthly_target,    -- 月目标

    -- 渠道
    online_offline                             AS online_flag,       -- 线上/线下
    order_source                               AS order_source,      -- 订单来源
    third_one_level_channel_name               AS channel_l1,        -- 一级渠道
    third_two_level_channel_name               AS channel_l2,        -- 二级渠道

    -- 分区
    p_mon                                      AS partition_month    -- 分区月份

FROM spark_catalog.ads_pub.ads_fact_pos_ord_analysis
WHERE p_mon >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%Y%m')
  AND p_mon <= DATE_FORMAT(CURDATE(), '%Y%m')
  AND period_sdate >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 90 DAY), '%Y%m%d')
ORDER BY sy_org_lno, period_sdate
;
