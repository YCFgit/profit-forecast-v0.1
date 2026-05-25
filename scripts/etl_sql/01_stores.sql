-- ============================================================
-- ETL 01: 门店主数据
-- 数据源: dws_pub.dws_dim_org_allinfo (机构信息维表)
-- 用途: 获取所有在营实体门店的基本信息
-- 输出: 门店编码、名称、品牌、区域、城市、面积等
-- ============================================================

SELECT
    org_lno                                    AS store_code,        -- 门店编码（主键）
    org_name                                   AS store_name,        -- 门店名称
    store_abbr                                 AS store_short_name,  -- 门店简称
    brd_dtl_abbr                               AS brand,             -- 品牌
    store_type_name                            AS store_type,        -- 门店类型
    store_channel_name1                        AS channel_l1,        -- 渠道大类
    store_channel_name2                        AS channel_l2,        -- 渠道中类
    store_channel_name3                        AS channel_l3,        -- 渠道小类
    big_region_name                            AS region,            -- 大区
    region_name                                AS sub_region,        -- 小区
    mc_name                                    AS city,              -- 管理城市
    province_name                              AS province,          -- 省份
    city_name                                  AS admin_city,        -- 行政城市
    biz_attr_name                              AS business_attribute,-- 业态属性
    biz_attr_name2                             AS business_category, -- 业态分类
    biz_attr_name3                             AS business_detail,   -- 业态明细
    store_level_name                           AS store_level,       -- 门店等级
    mall_name                                  AS mall_name,         -- 商场名称
    biz_circle_name                            AS commercial_circle, -- 商圈
    city_level                                 AS city_level,        -- 城市等级
    biz_area                                   AS business_area,     -- 营业面积
    area_total                                 AS total_area,        -- 总面积
    open_date                                  AS opening_date,      -- 开业日期
    close_date                                 AS closing_date,      -- 关闭日期
    actual_open_date                           AS actual_open_date,  -- 实际开业日期
    real_withdrawal_date                       AS withdrawal_date,   -- 实际撤店日期
    store_status                               AS status,            -- 门店状态
    is_entity                                  AS is_entity,         -- 是否实体
    is_new_flag                                AS is_new_store,      -- 是否新店
    property_cooperation                       AS cooperation_mode,  -- 合作模式
    property_cooperation_cond                  AS cooperation_cond,  -- 合作条件
    settlement_mth                             AS settlement_method, -- 结算方式
    self_checking_mode                         AS self_cash_mode,    -- 自收银模式
    big_store_format                           AS big_store_format,  -- 大店形态
    org_sal_biz_type                           AS sales_biz_type,    -- 销售业务类型
    org_sal_mode                               AS sales_mode,        -- 销售模式
    fin_code                                   AS fin_code,          -- 财务编码
    virtual_shop_type                          AS virtual_shop_type, -- 虚拟店类型
    store_type                                 AS store_type_flag,   -- 门店类型标识
    etl_update_time                            AS etl_update_time    -- ETL更新时间
FROM dws_pub.dws_dim_org_allinfo
WHERE store_status = 1        -- 在营
  AND is_entity = 1           -- 实体店
ORDER BY org_lno
;
