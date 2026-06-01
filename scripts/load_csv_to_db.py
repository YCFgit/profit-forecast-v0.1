"""将 inputData CSV 数据灌入 MySQL 数据库

使用方式：
    python scripts/load_csv_to_db.py              # 加载全部
    python scripts/load_csv_to_db.py --stores-only # 只加载门店
    python scripts/load_csv_to_db.py --skip-daily  # 跳过日销（数据量最大）
"""

import argparse
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 加载 .env 文件
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

INPUT_DIR = ROOT / "inputData"

# ============================================================
# CSV 文件名映射
# ============================================================
CSV_FILES = {
    "stores": "机构维表dws_dim_org_allinfo数据.csv",
    "store_loss": "门店日损益数据ads_fin_fact_day_storeloss_pp近两个财年数据.csv",
    "store_loss_90d": "门店日损益数据ads_fin_fact_day_storeloss_pp近90天数据.csv",
    "monthly_metrics": "月度指标（从日损益表聚合dwd_f04_dayone_countbase_pp_new）数据.csv",
    "cost_structure": "成本结构明细（从日损益表按月聚合dwd_f04_dayone_countbase_pp_new）.csv",
    "daily_target": "店铺日月目标数据（dws_fact_day_org_target_cost）近90天数据.csv",
    "store_info": "门店扩充信息（dwd_f04_dayone_s_store_info）数据.csv",
}

BATCH_SIZE = 5000


def load_csv(name: str, usecols: list[str] | None = None) -> pd.DataFrame:
    path = INPUT_DIR / CSV_FILES[name]
    if not path.exists():
        logger.warning(f"CSV 文件不存在: {path}")
        return pd.DataFrame()
    logger.info(f"加载 {name}: {path.name}")
    if usecols:
        # 只使用 CSV 中实际存在的列
        header = pd.read_csv(path, nrows=0).columns.tolist()
        valid_cols = [c for c in usecols if c in header]
        df = pd.read_csv(path, usecols=valid_cols or None, low_memory=False)
    else:
        df = pd.read_csv(path, low_memory=False)
    logger.info(f"  → {len(df)} 行, {len(df.columns)} 列")
    return df


def bulk_insert(engine, table_name: str, records: list[dict], batch_size: int = BATCH_SIZE):
    """批量插入数据"""
    if not records:
        return
    from sqlalchemy import inspect
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    # 只保留表中存在的列
    valid_records = []
    for r in records:
        valid = {k: v for k, v in r.items() if k in columns and pd.notna(v)}
        valid_records.append(valid)

    with engine.begin() as conn:
        for i in range(0, len(valid_records), batch_size):
            batch = valid_records[i:i + batch_size]
            conn.execute(text(f"INSERT IGNORE INTO {table_name} ({', '.join(columns)}) VALUES (:placeholders)"),
                         {})  # placeholder
            # 用 pandas to_sql 更高效
    logger.info(f"  已插入 {table_name}: {len(valid_records)} 行")


def _parse_date(val):
    """解析日期值，支持 YYYYMMDD 和 YYYY-MM-DD 格式"""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) >= 10:
        return s[:10]
    return None


def load_stores(engine):
    """加载门店主数据（新版 dws_dim_org_allinfo CSV）"""
    logger.info("=" * 40 + " 门店主数据 " + "=" * 40)
    path = INPUT_DIR / CSV_FILES["stores"]
    if not path.exists():
        logger.warning(f"CSV 文件不存在: {path}")
        return
    df = pd.read_csv(path, encoding="gbk", low_memory=False)
    logger.info(f"  → {len(df)} 行, {len(df.columns)} 列")

    # status 映射: 0=未开, 1=营业中, 2=已关闭, 3=改装中
    STATUS_MAP = {0: "pre_open", 1: "active", 2: "closed", 3: "renovating"}

    records = []
    for _, row in df.iterrows():
        raw_status = int(row.get("status", 1)) if pd.notna(row.get("status")) else 1
        status = STATUS_MAP.get(raw_status, "active")

        tier = row.get("store_level") or row.get("commercial_tier") or "B"
        if pd.isna(tier):
            tier = "B"

        area = row.get("business_area")
        total_area = row.get("total_area")

        records.append({
            "id": str(uuid.uuid4()),
            "store_code": str(row.get("store_code", "")),
            "store_name": str(row.get("store_name", "")),
            "store_short_name": str(row.get("store_short_name", "")) if pd.notna(row.get("store_short_name")) else None,
            "brand": str(row.get("brand", "")) if pd.notna(row.get("brand")) else None,
            "store_type": str(row.get("store_type", "")) if pd.notna(row.get("store_type")) else None,
            "channel_l1": str(row.get("channel_l1", "")) if pd.notna(row.get("channel_l1")) else None,
            "channel_l2": str(row.get("channel_l2", "")) if pd.notna(row.get("channel_l2")) else None,
            "channel_l3": str(row.get("channel_l3", "")) if pd.notna(row.get("channel_l3")) else None,
            "region": str(row.get("region", "")) if pd.notna(row.get("region")) else None,
            "sub_region": str(row.get("sub_region", "")) if pd.notna(row.get("sub_region")) else None,
            "province": str(row.get("province", "")) if pd.notna(row.get("province")) else None,
            "city": str(row.get("city", "")) if pd.notna(row.get("city")) else None,
            "city_level": str(row.get("city_level", "")) if pd.notna(row.get("city_level")) else None,
            "business_attribute": str(row.get("business_attribute", "")) if pd.notna(row.get("business_attribute")) else None,
            "business_category": str(row.get("business_category", "")) if pd.notna(row.get("business_category")) else None,
            "commercial_tier": str(tier),
            "store_area": float(area) if pd.notna(area) else None,
            "total_area": float(total_area) if pd.notna(total_area) else None,
            "opening_date": _parse_date(row.get("opening_date")),
            "closing_date": _parse_date(row.get("closing_date")),
            "actual_open_date": _parse_date(row.get("actual_open_date")),
            "status": status,
            "is_new_store": int(row.get("is_new_store", 0)) if pd.notna(row.get("is_new_store")) else 0,
            "cooperation_mode": str(row.get("cooperation_mode", "")) if pd.notna(row.get("cooperation_mode")) else None,
            "commercial_circle": str(row.get("commercial_circle", "")) if pd.notna(row.get("commercial_circle")) else None,
        })

    with engine.begin() as conn:
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            for r in batch:
                conn.execute(text(
                    "INSERT IGNORE INTO stores (id, store_code, store_name, store_short_name, brand, "
                    "store_type, channel_l1, channel_l2, channel_l3, region, sub_region, province, city, "
                    "city_level, business_attribute, business_category, commercial_tier, store_area, total_area, "
                    "opening_date, closing_date, actual_open_date, status, is_new_store, cooperation_mode, "
                    "commercial_circle) "
                    "VALUES (:id, :store_code, :store_name, :store_short_name, :brand, "
                    ":store_type, :channel_l1, :channel_l2, :channel_l3, :region, :sub_region, :province, :city, "
                    ":city_level, :business_attribute, :business_category, :commercial_tier, :store_area, :total_area, "
                    ":opening_date, :closing_date, :actual_open_date, :status, :is_new_store, :cooperation_mode, "
                    ":commercial_circle)"
                ), r)
    logger.info(f"  已插入 stores: {len(records)} 行")


def load_daily_sales(engine, use_90d: bool = True):
    """加载日销数据（从日损益 CSV）"""
    logger.info("=" * 40 + " 日销数据 " + "=" * 40)
    cols = ["store_code", "sale_date", "actual_sales_pp", "actual_sales",
            "actual_gross_profit", "actual_operating_profit"]
    df_full = load_csv("store_loss", usecols=cols)

    if use_90d:
        df_90 = load_csv("store_loss_90d", usecols=cols)
        if not df_90.empty:
            full_dates = set(df_full["sale_date"].astype(str).unique())
            d90_dates = set(df_90["sale_date"].astype(str).unique())
            overlap = full_dates & d90_dates
            if overlap:
                df_90 = df_90[~df_90["sale_date"].astype(str).isin(overlap)]
            df_full = pd.concat([df_full, df_90], ignore_index=True)

    # 转换日期格式
    df_full["sale_date"] = pd.to_datetime(df_full["sale_date"]).dt.date

    records = []
    for _, row in df_full.iterrows():
        sales = float(row.get("actual_sales_pp", 0) or 0)
        records.append({
            "id": str(uuid.uuid4()),
            "store_code": str(row["store_code"]),
            "sale_date": row["sale_date"],
            "sales_amount": sales,
            "sales_qty": 0,
            "discount_rate": 1.0,
        })

    with engine.begin() as conn:
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            for r in batch:
                conn.execute(text(
                    "INSERT IGNORE INTO store_daily_sales "
                    "(id, store_code, sale_date, sales_amount, sales_qty, discount_rate) "
                    "VALUES (:id, :store_code, :sale_date, :sales_amount, :sales_qty, :discount_rate)"
                ), r)
            if i % 50000 == 0 and i > 0:
                logger.info(f"  进度: {i}/{len(records)}")
    logger.info(f"  已插入 store_daily_sales: {len(records)} 行")


def load_monthly_metrics(engine):
    """加载月度指标"""
    logger.info("=" * 40 + " 月度指标 " + "=" * 40)
    df = load_csv("monthly_metrics")
    if df.empty:
        return

    # year_month 格式: 2024011 = YYYYMM + period_type, 取前6位得 YYYYMM
    df["year_month"] = df["year_month"].astype(str).str[:6]
    # 转为 2024-01 格式
    df["year_month"] = df["year_month"].str[:4] + "-" + df["year_month"].str[4:]

    # 找到可用的金额列
    sales_col = "sales_amount" if "sales_amount" in df.columns else None
    # 毛利列：优先 gross_profit，其次 actual_gross_profit，最后 hq_notax_gross_profit
    gross_col = None
    for candidate in ["gross_profit", "actual_gross_profit", "hq_notax_gross_profit"]:
        if candidate in df.columns:
            gross_col = candidate
            break

    agg_dict = {}
    if sales_col:
        agg_dict[sales_col] = "sum"
    if gross_col:
        agg_dict[gross_col] = "sum"

    if not agg_dict:
        logger.warning("月度指标 CSV 中无可用金额列")
        return

    agg = df.groupby(["store_code", "year_month"]).agg(agg_dict).reset_index()

    records = []
    for _, row in agg.iterrows():
        revenue = float(row.get(sales_col, 0) or 0) if sales_col else 0
        gross = float(row.get(gross_col, 0) or 0) if gross_col else 0
        records.append({
            "id": str(uuid.uuid4()),
            "store_code": str(row["store_code"]),
            "year_month": str(row["year_month"]),
            "sales_amount": revenue,
            "gross_profit": gross,
            "gross_margin": round(gross / revenue, 4) if revenue > 0 else 0,
        })

    with engine.begin() as conn:
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            for r in batch:
                conn.execute(text(
                    "INSERT IGNORE INTO store_monthly_metrics "
                    "(id, store_code, `year_month`, sales_amount, gross_profit, gross_margin) "
                    "VALUES (:id, :store_code, :year_month, :sales_amount, :gross_profit, :gross_margin)"
                ), r)
    logger.info(f"  已插入 store_monthly_metrics: {len(records)} 行")


def load_cost_structure(engine):
    """加载成本结构"""
    logger.info("=" * 40 + " 成本结构 " + "=" * 40)
    df = load_csv("cost_structure")
    if df.empty:
        return

    # 确保 year_month 格式正确 (YYYYMM+period → YYYY-MM)
    if "year_month" in df.columns:
        df["year_month"] = df["year_month"].astype(str).str[:6]
        df["year_month"] = df["year_month"].str[:4] + "-" + df["year_month"].str[4:]
    elif "sale_date" in df.columns:
        df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
        df = df.dropna(subset=["sale_date"])
        df["year_month"] = df["sale_date"].dt.strftime("%Y-%m")
    else:
        logger.warning("成本结构 CSV 中无 year_month 或 sale_date 列")
        return

    # 找到可用的成本列（排除标识列）
    exclude = {"store_code", "sale_date", "year_month", "brand", "region", "etl_update_time", "pt_mon"}
    cost_cols = [c for c in df.columns if c not in exclude and df[c].dtype in ("float64", "int64", "float32", "int32")]

    agg = df.groupby(["store_code", "year_month"])[cost_cols].sum().reset_index()

    records = []
    for _, row in agg.iterrows():
        total = sum(float(row.get(c, 0) or 0) for c in cost_cols)
        records.append({
            "id": str(uuid.uuid4()),
            "store_code": str(row["store_code"]),
            "year_month": str(row["year_month"]),
            "total_cost": total,
        })

    with engine.begin() as conn:
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            for r in batch:
                conn.execute(text(
                    "INSERT IGNORE INTO cost_structure "
                    "(id, store_code, `year_month`, total_cost) "
                    "VALUES (:id, :store_code, :year_month, :total_cost)"
                ), r)
    logger.info(f"  已插入 cost_structure: {len(records)} 行")


def load_targets(engine):
    """加载目标数据"""
    logger.info("=" * 40 + " 目标数据 " + "=" * 40)
    cols = ["store_code", "target_date", "monthly_sales_target", "daily_sales_target", "partition_month"]
    df = load_csv("daily_target", usecols=cols)
    if df.empty:
        return

    df["target_date"] = pd.to_datetime(df["target_date"], errors="coerce")
    df["partition_month"] = df["partition_month"].astype(str)

    # 月度目标（每店每月一条）
    monthly = df.groupby(["store_code", "partition_month"]).agg({
        "monthly_sales_target": "first",
    }).reset_index()

    records = []
    for _, row in monthly.iterrows():
        target = float(row.get("monthly_sales_target", 0) or 0)
        if target <= 0:
            continue
        records.append({
            "id": str(uuid.uuid4()),
            "store_code": str(row["store_code"]),
            "target_type": "monthly",
            "target_month": str(row["partition_month"]),
            "sales_target": target,
            "profit_target": 0,
            "source": "real_data",
        })

    with engine.begin() as conn:
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            for r in batch:
                conn.execute(text(
                    "INSERT IGNORE INTO store_targets "
                    "(id, store_code, target_type, target_month, sales_target, profit_target, source) "
                    "VALUES (:id, :store_code, :target_type, :target_month, :sales_target, :profit_target, :source)"
                ), r)
    logger.info(f"  已插入 store_targets: {len(records)} 行")


def main():
    parser = argparse.ArgumentParser(description="将 CSV 数据灌入 MySQL")
    parser.add_argument("--stores-only", action="store_true", help="只加载门店数据")
    parser.add_argument("--skip-daily", action="store_true", help="跳过日销数据（数据量最大）")
    parser.add_argument("--skip-cost", action="store_true", help="跳过成本结构")
    args = parser.parse_args()

    from src.db.session import get_engine

    engine = get_engine()
    logger.info("数据库连接成功")

    # 创建表
    from src.db.session import Base
    from src.db import models  # noqa: F401 — 触发模型注册
    Base.metadata.create_all(engine)
    logger.info("数据表已创建/确认")

    load_stores(engine)

    if args.stores_only:
        logger.info("门店数据加载完成（--stores-only）")
        return

    load_targets(engine)
    load_monthly_metrics(engine)

    if not args.skip_cost:
        load_cost_structure(engine)

    if not args.skip_daily:
        load_daily_sales(engine)

    # 统计
    with engine.connect() as conn:
        for table in ["stores", "store_daily_sales", "store_monthly_metrics", "cost_structure", "store_targets"]:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            logger.info(f"  {table}: {count} 行")

    logger.info("数据加载完成！")


if __name__ == "__main__":
    main()
