CREATE TABLE dws_pub.dws_dim_brd_allinfo (
  brd_dtl_no STRING COMMENT '品牌编码',
  brd_no STRING COMMENT '品牌部编码',
  brd_ename STRING COMMENT '品牌部英文名',
  brd_cname STRING COMMENT '品牌部中文名',
  brd_abbr STRING COMMENT '品牌部简称',
  brd_order INT COMMENT '品牌部排序',
  brd_dtl_cname STRING COMMENT '品牌中文名',
  brd_dtl_ename STRING COMMENT '品牌英文名',
  brd_dtl_abbr STRING COMMENT '品牌简称',
  brd_dtl_order INT COMMENT '品牌排序',
  brd_group_no STRING COMMENT '品牌组编码',
  brd_group_name STRING COMMENT '品牌组名称',
  brd_group_order INT COMMENT '品牌组排序',
  etl_create_time STRING COMMENT 'ETL创建时间',
  etl_update_time STRING COMMENT 'ETL更新时间',
  business_unit_no STRING COMMENT '事业部编码',
  business_unit_name STRING COMMENT '事业部名称')
USING parquet
COMMENT 'dim_品牌信息'
TBLPROPERTIES (
  'STATS_GENERATED' = 'TASK',
  'bucketing_version' = '2',
  'impala.events.catalogServiceId' = '4c9a2107d7e2468a:9908249de77a7752',
  'impala.events.catalogVersion' = '407843',
  'impala.lastComputeStatsTime' = '1731342162',
  'last_modified_time' = '1731983711',
  'numFilesErasureCoded' = '0',
  'transient_lastDdlTime' = '1779035994')