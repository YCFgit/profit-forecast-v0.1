CREATE TABLE dws_pub.dws_dim_org_management (
  org_lno STRING COMMENT '机构原编码',
  retail_director_code STRING COMMENT '零售主管工号',
  retail_director_name STRING COMMENT '零售主管姓名',
  retail_manager_code STRING COMMENT '零售经理工号',
  retail_manager_name STRING COMMENT '零售经理姓名',
  vsr_director_code STRING COMMENT '陈列主管工号',
  vsr_director_name STRING COMMENT '陈列主管姓名',
  vsr_manager_code STRING COMMENT '陈列经理工号',
  vsr_manager_name STRING COMMENT '陈列经理姓名',
  train_director_code STRING COMMENT '培训主管工号',
  train_director_name STRING COMMENT '培训主管姓名',
  train_manager_code STRING COMMENT '培训经理工号',
  train_manager_name STRING COMMENT '培训经理姓名',
  onlineop_director_code STRING COMMENT '线上运营主管工号',
  onlineop_director_name STRING COMMENT '线上运营主管姓名',
  onlineop_manager_code STRING COMMENT '线上运营经理工号',
  onlineop_manager_name STRING COMMENT '线上运营经理姓名',
  etl_create_time STRING COMMENT 'ETL创建时间',
  etl_update_time STRING COMMENT 'ETL更新时间',
  region_brd_manager_code STRING COMMENT '小区品牌负责人工号',
  region_brd_manager_name STRING COMMENT '小区品牌负责人名字',
  shoper_employee_code STRING COMMENT '店长工号',
  shoper_employee_name STRING COMMENT '店长名称')
USING parquet
COMMENT '店铺管理人员信息维表'
TBLPROPERTIES (
  'STATS_GENERATED' = 'TASK',
  'bucketing_version' = '2',
  'impala.lastComputeStatsTime' = '1731381391',
  'last_modified_time' = '1731983730',
  'numFilesErasureCoded' = '0',
  'transient_lastDdlTime' = '1779036068')