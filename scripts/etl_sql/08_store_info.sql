-- ============================================================
-- ETL 08: 门店扩充信息（人员/面积/合同等）
-- 数据源: proj_facana.dwd_f04_dayone_s_store_info
-- 用途: 获取门店的人员数量、面积、合同等补充信息
-- 输出: 门店维度的扩充属性
-- ============================================================

SELECT
    store_no                                   AS store_code,        -- 门店编码
    store_name_short                           AS store_name,        -- 门店简称
    brand_detail_abbreviation                  AS brand,             -- 品牌
    employee_qty                               AS staff_count,       -- 员工数
    business_area                              AS business_area,     -- 营业面积
    storage_area                               AS storage_area,      -- 仓储面积
    total_area                                 AS total_area,        -- 总面积
    contract_area                              AS contract_area,     -- 合同面积
    open_date                                  AS opening_date,      -- 开业日期
    close_date                                 AS closing_date,      -- 关闭日期
    shop_category                              AS shop_category,     -- 店铺分类
    business_detail                            AS business_detail,   -- 业态明细
    business_circle_name                       AS commercial_circle, -- 商圈
    shopping_mall_name                         AS mall_name,         -- 商场名称
    region_top                                 AS region,            -- 大区
    managing_city                              AS managing_city,     -- 管理城市
    pay_method                                 AS pay_method,        -- 支付方式
    self_cash_method                           AS self_cash_mode,    -- 自收银模式
    reform_complete_time                       AS reform_date,       -- 改造完成时间
    decoration_date                            AS decoration_date,   -- 装修开始日期
    decoration_end_date                        AS decoration_end_date, -- 装修结束日期
    contract_start_date                        AS contract_start,    -- 合同开始日期
    contract_end_date                          AS contract_end,      -- 合同结束日期
    affiliation                                AS affiliation,       -- 隶属关系
    org_structure_classification               AS org_structure,     -- 组织架构
    operation_mode                             AS operation_mode,    -- 经营模式
    platform                                   AS platform,          -- 平台
    store_type_new                             AS store_type_new,    -- 门店类型(新)
    business_unit                              AS business_unit,     -- 业务单元
    etl_update_time                            AS etl_update_time    -- ETL更新时间
FROM proj_facana.dwd_f04_dayone_s_store_info
ORDER BY store_no
;
