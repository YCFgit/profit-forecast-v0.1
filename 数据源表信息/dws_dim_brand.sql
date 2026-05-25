CREATE TABLE proj_facana.dws_dim_brand (
  `brd_dtl_abbr` varchar(1073741824) DEFAULT NULL,
  `brd_no` varchar(1073741824) DEFAULT NULL,
  `brd_ename` varchar(1073741824) DEFAULT NULL,
  `brd_cname` varchar(1073741824) DEFAULT NULL,
  `brd_abbr` varchar(1073741824) DEFAULT NULL,
  `brd_order` int(11) DEFAULT NULL,
  `brd_dtl_no` varchar(1073741824) DEFAULT NULL,
  `brd_dtl_cname` varchar(1073741824) DEFAULT NULL,
  `brd_dtl_ename` varchar(1073741824) DEFAULT NULL,
  `brd_dtl_order` int(11) DEFAULT NULL,
  `brd_group` varchar(1073741824) DEFAULT NULL,
  `bu_no` varchar(1073741824) DEFAULT NULL,
  `bu_name` varchar(1073741824) DEFAULT NULL,
  `etl_create_time` varchar(1073741824) DEFAULT NULL,
  `etl_update_time` varchar(1073741824) DEFAULT NULL,
  `etl_flag` varchar(1073741824) DEFAULT NULL,
  `affiliation` varchar(1073741824) DEFAULT NULL,
  `affiliation2` varchar(1073741824) DEFAULT NULL,
  `brand_unit` varchar(1073741824) DEFAULT NULL,
  `brand_no_new` varchar(1073741824) DEFAULT NULL COMMENT "品牌部编码"
)
PRIMARY KEYS (brd_dtl_abbr)
COMMENT ("DWS_品牌信息")
PROPERTIES ("location" = "oss://ts-bigdata-oss-hdfs.cn-beijing.oss-dls.aliyuncs.com/user/hive/warehouse/proj_facana.db/dws_dim_brand",
 "bucket" = "1",
 "owner" = "emr-user",
 "sink.watermark-time-zone" = "Asia/Shanghai",
 "snapshot.watermark-idle-timeout" = "10m",
 "changelog-producer" = "input",
 "sink.parallelism" = "8");