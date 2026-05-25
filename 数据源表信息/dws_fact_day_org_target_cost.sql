CREATE TABLE dws_pub.dws_fact_day_org_target_cost (
  brd_no STRING COMMENT '品牌部编码',
  brd_dtl_no STRING COMMENT '品牌编码',
  org_lno STRING COMMENT '机构原编码',
  store_lno STRING COMMENT '店仓原编码',
  period_sdate STRING COMMENT '字符串日期(YYYYMMDD)',
  store_brd STRING COMMENT '店铺品牌',
  org_new_no STRING COMMENT '机构最新编码（新店店铺编码/货管单位编码）',
  day_amt_target DECIMAL(18,4) COMMENT '日营业目标',
  mon_amt_target DECIMAL(18,4) COMMENT '月营业目标',
  year_amt_target DECIMAL(18,4) COMMENT '年累计营业目标',
  cust_sal_nos_qty_target DECIMAL(18,4) COMMENT '客单量目标',
  cust_sal_price_target DECIMAL(18,4) COMMENT '客单价目标',
  cr_target BIGINT COMMENT 'CR目标',
  avg_price_target DECIMAL(18,4) COMMENT '平均单价目标',
  etl_create_time STRING COMMENT 'ETL创建时间',
  etl_update_time STRING COMMENT 'ETL更新时间',
  virtual_mon_amt_target DECIMAL(18,4) COMMENT '虚店销售目标',
  virtual_discount_target DECIMAL(18,4) COMMENT '虚店折扣目标',
  clg_mon_amt_target DECIMAL(18,4) COMMENT '月挑战目标',
  offline_mon_amt_target DECIMAL(18,4) COMMENT '线下月目标额',
  sy_mon_amt_target DECIMAL(18,4) COMMENT '私域月目标额',
  live_mon_amt_target DECIMAL(18,4) COMMENT '直播月目标额',
  wholesale_amt_target DECIMAL(18,4) COMMENT '团购目标',
  p_mon STRING COMMENT 'YYYYMM')
USING parquet
PARTITIONED BY (p_mon)
COMMENT '日店铺基础目标表'
TBLPROPERTIES (
  'bucketing_version' = '2',
  'last_modified_time' = '1736928444',
  'transient_lastDdlTime' = '1744634263')