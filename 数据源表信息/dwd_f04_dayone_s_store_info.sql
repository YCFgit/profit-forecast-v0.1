CREATE TABLE `proj_facana`.`dwd_f04_dayone_s_store_info` (
  `base_date` varchar(1073741824) DEFAULT NULL,
  `brand_detail_abbreviation` varchar(1073741824) DEFAULT NULL,
  `store_no` varchar(1073741824) DEFAULT NULL,
  `region_no` varchar(1073741824) DEFAULT NULL,
  `managing_city` varchar(1073741824) DEFAULT NULL,
  `company_no` varchar(1073741824) DEFAULT NULL,
  `nc_org_code` varchar(1073741824) DEFAULT NULL,
  `nc_org_name` varchar(1073741824) DEFAULT NULL,
  `pipe_nc_org_code` varchar(1073741824) DEFAULT NULL,
  `pipe_nc_org_name` varchar(1073741824) DEFAULT NULL,
  `shop_category` varchar(1073741824) DEFAULT NULL,
  `business_detail` varchar(1073741824) DEFAULT NULL,
  `store_name_short` varchar(1073741824) DEFAULT NULL,
  `shopping_mall_name` varchar(1073741824) DEFAULT NULL,
  `bsgroups_name` varchar(1073741824) DEFAULT NULL,
  `ichannel_effective_date` varchar(1073741824) DEFAULT NULL,
  `pay_method` varchar(1073741824) DEFAULT NULL,
  `self_cash_method` varchar(1073741824) DEFAULT NULL,
  `reform_complete_time` varchar(1073741824) DEFAULT NULL,
  `decoration_date` varchar(1073741824) DEFAULT NULL,
  `business_area` decimal(18, 4) DEFAULT NULL,
  `storage_area` decimal(18, 4) DEFAULT NULL,
  `outside_storage_area` decimal(18, 4) DEFAULT NULL,
  `total_area` decimal(18, 4) DEFAULT NULL,
  `contract_area` decimal(18, 4) DEFAULT NULL,
  `contract_start_date` varchar(1073741824) DEFAULT NULL,
  `contract_end_date` varchar(1073741824) DEFAULT NULL,
  `sports_city_container_code` varchar(1073741824) DEFAULT NULL,
  `business_category` varchar(1073741824) DEFAULT NULL,
  `input_time` varchar(1073741824) DEFAULT NULL,
  `input_user` varchar(1073741824) DEFAULT NULL,
  `brand_no` varchar(1073741824) DEFAULT NULL,
  `source` varchar(1073741824) DEFAULT NULL,
  `employee_qty` decimal(18, 4) DEFAULT NULL,
  `open_date` varchar(1073741824) DEFAULT NULL,
  `close_date` varchar(1073741824) DEFAULT NULL,
  `fssc_code` varchar(1073741824) DEFAULT NULL,
  `affiliation` varchar(1073741824) DEFAULT NULL,
  `brand_detail_abbreviation2` varchar(1073741824) DEFAULT NULL,
  `brand_detail_abbreviation1` varchar(1073741824) DEFAULT NULL,
  `shop_image` varchar(1073741824) DEFAULT NULL,
  `merge_orig_store_no` varchar(1073741824) DEFAULT NULL,
  `great_store_mark_month` varchar(1073741824) DEFAULT NULL,
  `great_store_can_month` varchar(1073741824) DEFAULT NULL,
  `region_top` varchar(1073741824) DEFAULT NULL,
  `affiliation_old` varchar(1073741824) DEFAULT NULL,
  `store_qty_bi` decimal(18, 4) DEFAULT NULL,
  `resurrect_date` varchar(1073741824) DEFAULT NULL,
  `store_type_ori` varchar(1073741824) DEFAULT NULL,
  `fin_year` varchar(1073741824) DEFAULT NULL,
  `fin_month` varchar(1073741824) DEFAULT NULL,
  `vat_type` varchar(1073741824) DEFAULT NULL,
  `remark` varchar(1073741824) DEFAULT NULL,
  `decoration_end_date` varchar(1073741824) DEFAULT NULL,
  `real_withdrawal_date` varchar(1073741824) DEFAULT NULL,
  `shop_category_name1` varchar(1073741824) DEFAULT NULL,
  `shop_category_name2` varchar(1073741824) DEFAULT NULL,
  `shop_category_name3` varchar(1073741824) DEFAULT NULL,
  `is_big_shop` varchar(1073741824) DEFAULT NULL,
  `city_level_no` varchar(1073741824) DEFAULT NULL,
  `sign_company_code` varchar(1073741824) DEFAULT NULL,
  `sign_company_name` varchar(1073741824) DEFAULT NULL,
  `retail_customer_no` varchar(1073741824) DEFAULT NULL,
  `retail_customer_name` varchar(1073741824) DEFAULT NULL,
  `etl_create_time` varchar(1073741824) DEFAULT NULL,
  `etl_update_time` varchar(1073741824) DEFAULT NULL,
  `etl_flag` varchar(1073741824) DEFAULT NULL,
  `business_unit` varchar(1073741824) DEFAULT NULL,
  `org_structure_classification` varchar(1073741824) DEFAULT NULL,
  `operation_mode` varchar(1073741824) DEFAULT NULL,
  `prop_cooperation_conds_new` varchar(1073741824) DEFAULT NULL,
  `store_type_new` varchar(1073741824) DEFAULT NULL,
  `platform` varchar(1073741824) DEFAULT NULL,
  `business_circle_name` varchar(1073741824) DEFAULT NULL COMMENT "所属商圈名称"
)
PRIMARY KEYS (base_date, brand_detail_abbreviation, store_no)
COMMENT ("实时-日实时扩充店铺信息")
PROPERTIES ("location" = "oss://ts-bigdata-oss-hdfs.cn-beijing.oss-dls.aliyuncs.com/user/hive/warehouse/proj_facana.db/dwd_f04_dayone_s_store_info",
 "bucket" = "1",
 "owner" = "hive",
 "sink.watermark-time-zone" = "Asia/Shanghai",
 "snapshot.watermark-idle-timeout" = "10m",
 "changelog-producer" = "input",
 "sink.parallelism" = "8");


渠道分类明细：
case
  when org_structure_classification = '线上团购' then '线上团购'
  when org_structure_classification = '线上直播' then '线上直播'
  when org_structure_classification = '线上批发' then '线上批发'
  when org_structure_classification = '线上内销' then '线上内销'
  when platform = '小红书' then '小红书'
  when platform in ('美团', '京东到家', '美团闪购', '京东秒送', '淘宝闪购') then '即时零售'
  when org_structure_classification = '线上私域' then '小程序'
  when platform in ('天猫', '天猫国际', '天猫超市', '淘宝', '淘工厂', '真酷', '有赞') then '淘天'
  else platform
end

