"""从 inputData CSV 加载数据并执行全流程利润测算

使用方式：
    python scripts/run_from_csv.py
    python scripts/run_from_csv.py --target 10000000
    python scripts/run_from_csv.py --stores ST0001,ST0002
    python scripts/run_from_csv.py --export result.csv
    python scripts/run_from_csv.py --perspective rebate
    python scripts/run_from_csv.py --no-90day       # 不合并90天数据
    python scripts/run_from_csv.py --no-target       # 不使用真实目标
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

pd.set_option("future.no_silent_downcasting", True)

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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
    "switch_status": "门店开关状态（dws_dim_org_on_off）.csv",
    "pos_orders": "POS订单聚合（门店×日期维度）数据.csv",
    "pos_orders_90d": "POS订单聚合（门店×日期维度）近90天数据.csv",
    "store_info": "门店扩充信息（dwd_f04_dayone_s_store_info）数据.csv",
}

# ============================================================
# 只加载需要的列（节省内存和时间）
# ============================================================
STORE_LOSS_COLS = [
    "store_code", "sale_date", "brand", "region", "managing_city", "business_city",
    "shop_category", "business_attribute",
    "actual_sales_pp", "actual_sales", "actual_cost", "actual_gross_profit",
    "actual_operating_expense", "actual_b_manage_expense", "actual_operating_profit",
    "actual_store_contribution", "actual_salary", "actual_social_fee",
    "actual_mall_fee", "actual_decorate_fee", "actual_express", "actual_other_fee",
    "rebate_sales", "rebate_gross_profit", "rebate_operating_expense",
    "rebate_operating_profit", "rebate_mall_fee", "rebate_salary",
    # 90天数据新增列：预算、同比
    "budget_sales_pp", "budget_sales", "budget_operating_profit",
    "ly_sales_pp", "ly_sales", "ly_operating_profit",
]

POS_COLS = ["store_code", "sale_date", "order_count", "sales_qty", "discount_rate"]
POS_COLS_90D = ["store_code", "sale_date", "order_count", "sales_qty", "discount_rate",
               "sales_amount", "tag_price_amount", "avg_ticket", "foot_traffic"]

TARGET_COLS = ["store_code", "target_date", "monthly_sales_target", "daily_sales_target",
               "partition_month"]

STORES_COLS = ["store_code", "store_name", "brand", "store_type", "region", "province",
               "city", "commercial_tier", "business_area", "total_area", "opening_date", "status"]

# ============================================================
# 列名映射：CSV 原始列名 → 代码期望的列名
# ============================================================

# 日损益（业绩口径 actual）→ 统一宽表
STORE_LOSS_ACTUAL_RENAME = {
    "store_code": "store_no",
    "sale_date": "base_date",
    "actual_sales_pp": "sales_amount",
    "actual_sales": "revenue",
    "actual_cost": "hq_taxcost",
    "actual_gross_profit": "gross_profit",
    "actual_operating_expense": "operating_expense",
    "actual_b_manage_expense": "bmanaging_exp",
    "actual_operating_profit": "operating_profit",
    "actual_store_contribution": "store_contribution",
    "actual_salary": "salary_fee",
    "actual_social_fee": "social_fee",
    "actual_mall_fee": "comprehensive_mall_fee",
    "actual_decorate_fee": "decorate_fee",
    "actual_express": "express",
    "actual_other_fee": "all_other_fee",
    "region": "region_top",
    # 同比 / 预算（90天数据）
    "ly_sales": "ly_sales",
    "ly_operating_profit": "ly_operating_profit",
    "budget_sales": "budget_sales",
    "budget_operating_profit": "budget_operating_profit",
}

# 日损益（返利口径 rebate）→ 统一宽表
STORE_LOSS_REBATE_RENAME = {
    "store_code": "store_no",
    "sale_date": "base_date",
    "actual_sales_pp": "sales_amount",
    "rebate_sales": "revenue",
    "actual_cost": "hq_taxcost",
    "rebate_gross_profit": "gross_profit",
    "rebate_operating_expense": "operating_expense",
    "actual_b_manage_expense": "bmanaging_exp",
    "rebate_operating_profit": "operating_profit",
    "actual_store_contribution": "store_contribution",
    "rebate_salary": "salary_fee",
    "actual_social_fee": "social_fee",
    "rebate_mall_fee": "comprehensive_mall_fee",
    "actual_decorate_fee": "decorate_fee",
    "actual_express": "express",
    "actual_other_fee": "all_other_fee",
    "region": "region_top",
    "ly_sales": "ly_sales",
    "ly_operating_profit": "ly_operating_profit",
    "budget_sales": "budget_sales",
    "budget_operating_profit": "budget_operating_profit",
}

# POS 聚合 → 统一宽表
POS_RENAME = {
    "store_code": "store_no",
    "sale_date": "base_date",
    "sales_qty": "qty_sold",
    "discount_rate": "avg_discount",
    "sales_amount": "pos_sales",
    "avg_ticket": "avg_ticket",
    "foot_traffic": "foot_traffic",
}

# 日目标 → 统一目标表
TARGET_RENAME = {
    "store_code": "store_no",
    "target_date": "base_date",
    "monthly_sales_target": "monthly_target",
    "daily_sales_target": "daily_target",
    "partition_month": "target_month",
}


def load_csv(name: str, usecols: list[str] | None = None) -> pd.DataFrame:
    """加载 inputData 中的 CSV 文件，只读取指定列"""
    path = INPUT_DIR / CSV_FILES[name]
    if not path.exists():
        logger.warning(f"CSV 文件不存在: {path}")
        return pd.DataFrame()
    logger.info(f"加载 {name}: {path.name}")
    df = pd.read_csv(path, usecols=usecols, low_memory=False)
    logger.info(f"  → {len(df)} 行, {len(df.columns)} 列")
    return df


def load_merged_loss(use_90d: bool = True) -> pd.DataFrame:
    """加载并合并全量 + 90天日损益数据（日期无重叠，直接拼接）"""
    df_full = load_csv("store_loss", usecols=STORE_LOSS_COLS)
    if df_full.empty:
        return df_full

    if use_90d:
        # 90天数据有更多列（ly_sales, budget_sales 等），额外加载
        loss_90_cols = STORE_LOSS_COLS + [
            "ly_sales", "ly_operating_profit", "budget_sales", "budget_operating_profit",
        ]
        df_90 = load_csv("store_loss_90d", usecols=loss_90_cols)
        if not df_90.empty:
            # 检查日期重叠
            full_dates = set(df_full["sale_date"].astype(str).unique())
            d90_dates = set(df_90["sale_date"].astype(str).unique())
            overlap = full_dates & d90_dates
            if overlap:
                logger.warning(f"日损益日期重叠 {len(overlap)} 天，去重后合并")
                df_90 = df_90[~df_90["sale_date"].astype(str).isin(overlap)]
            df_full = pd.concat([df_full, df_90], ignore_index=True)
            logger.info(f"合并后日损益: {len(df_full):,} 行, {df_full['store_code'].nunique():,} 家门店")
    return df_full


def load_merged_pos(use_90d: bool = True) -> pd.DataFrame:
    """加载并合并全量 + 90天 POS 数据（需去重重叠日期）"""
    df_full = load_csv("pos_orders", usecols=POS_COLS)
    if df_full.empty and not use_90d:
        return df_full

    if use_90d:
        df_90 = load_csv("pos_orders_90d", usecols=POS_COLS_90D)
        if not df_90.empty:
            if not df_full.empty:
                # POS 全量到 20260318，90天从 20260301 开始，有重叠需去重
                full_dates = set(df_full["sale_date"].astype(str).unique())
                d90_dates = set(df_90["sale_date"].astype(str).unique())
                overlap = full_dates & d90_dates
                if overlap:
                    logger.info(f"POS 日期重叠 {len(overlap)} 天，去重后合并")
                    df_90 = df_90[~df_90["sale_date"].astype(str).isin(overlap)]
                df_full = pd.concat([df_full, df_90], ignore_index=True)
            else:
                df_full = df_90
            logger.info(f"合并后 POS: {len(df_full):,} 行, {df_full['store_code'].nunique():,} 家门店")
    return df_full


def load_targets() -> pd.DataFrame:
    """加载日目标数据，提取月度目标（每月每店取一条）"""
    df = load_csv("daily_target", usecols=TARGET_COLS)
    if df.empty:
        return df
    # 每店每月取一条月度目标（用原始列名做 groupby）
    df["target_date"] = df["target_date"].astype(str).str.replace("-", "")
    df["partition_month"] = df["partition_month"].astype(str)
    targets = df.groupby(["store_code", "partition_month"]).agg({
        "monthly_sales_target": "first",
        "daily_sales_target": "sum",
    }).reset_index()
    logger.info(f"月度目标: {len(targets)} 条, {targets['store_code'].nunique()} 家门店")
    # 重命名列
    targets = targets.rename(columns={
        "store_code": "store_no",
        "partition_month": "target_month",
        "monthly_sales_target": "monthly_target",
        "daily_sales_target": "daily_target",
    })
    return targets


def build_unified_sales(
    store_loss_df: pd.DataFrame,
    pos_df: pd.DataFrame,
    perspective: str = "actual",
    store_codes: list[str] | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    min_days: int = 0,
) -> pd.DataFrame:
    """构建统一销售宽表（对应 09_unified_sales.sql 的逻辑）

    将日损益数据 + POS 聚合数据合并为一张宽表，供下游利润测算使用。
    """
    # 1. 处理日损益数据 — 根据口径选择列名映射
    rename_map = STORE_LOSS_REBATE_RENAME if perspective == "rebate" else STORE_LOSS_ACTUAL_RENAME
    sl = store_loss_df.rename(columns=rename_map)

    # 确保 base_date 为字符串格式 YYYYMMDD
    sl["base_date"] = sl["base_date"].astype(str).str.replace("-", "")

    # 过滤条件
    if store_codes:
        sl = sl[sl["store_no"].isin(store_codes)]
    if date_start:
        sl = sl[sl["base_date"] >= date_start]
    if date_end:
        sl = sl[sl["base_date"] <= date_end]

    if sl.empty:
        logger.warning("日损益数据过滤后为空")
        return pd.DataFrame()

    # 2. 处理 POS 数据
    if not pos_df.empty:
        pos = pos_df.rename(columns=POS_RENAME)
        pos["base_date"] = pos["base_date"].astype(str).str.replace("-", "")

        pos_cols = ["store_no", "base_date", "order_count", "qty_sold", "avg_discount",
                    "pos_sales", "avg_ticket", "foot_traffic"]
        available_cols = [c for c in pos_cols if c in pos.columns]
        pos_subset = pos[available_cols].copy()

        if store_codes:
            pos_subset = pos_subset[pos_subset["store_no"].isin(store_codes)]
        if date_start:
            pos_subset = pos_subset[pos_subset["base_date"] >= date_start]
        if date_end:
            pos_subset = pos_subset[pos_subset["base_date"] <= date_end]
    else:
        pos_subset = pd.DataFrame(columns=["store_no", "base_date", "order_count", "qty_sold", "avg_discount"])

    # 3. LEFT JOIN 合并：损益为主表，关联 POS 的订单数/件数/折扣
    unified = sl.merge(pos_subset, on=["store_no", "base_date"], how="left")

    # 4. 填充空值
    unified["order_count"] = unified["order_count"].fillna(0).astype(int)
    unified["qty_sold"] = unified["qty_sold"].fillna(0).astype(int)
    unified["avg_discount"] = unified["avg_discount"].fillna(1.0)
    for col in ["pos_sales", "avg_ticket", "foot_traffic"]:
        if col in unified.columns:
            unified[col] = unified[col].fillna(0)
    unified["perspective"] = perspective

    # 5. 按最少数据天数过滤门店
    if min_days > 0:
        store_day_counts = unified.groupby("store_no")["base_date"].nunique()
        valid_stores = store_day_counts[store_day_counts >= min_days].index
        before_count = unified["store_no"].nunique()
        unified = unified[unified["store_no"].isin(valid_stores)]
        after_count = unified["store_no"].nunique()
        logger.info(f"按最少 {min_days} 天过滤: {before_count} → {after_count} 家门店")

    logger.info(f"统一宽表: {len(unified)} 行, {unified['store_no'].nunique()} 家门店")
    return unified


def print_summary(result: dict, target: float, target_stores: int = 0):
    """打印测算结果摘要"""
    profit = result.get("profit_summary")
    risk = result.get("risk_result")
    alloc = result.get("allocation_result")

    if profit is None:
        logger.error("利润测算结果为空")
        return

    print("\n" + "=" * 60)
    print("  利 润 测 算 结 果")
    print("=" * 60)
    print(f"  总目标:        ¥{target:>15,.0f}")
    print(f"  总收入:        ¥{profit.total_revenue:>15,.0f}")
    print(f"  总毛利:        ¥{profit.total_gross_profit:>15,.0f}")
    print(f"  总营业利润:    ¥{profit.total_operating_profit:>15,.0f}")
    print(f"  总净利润:      ¥{profit.total_net_profit:>15,.0f}")
    print(f"  平均毛利率:     {profit.avg_gross_margin:>14.1%}")
    print(f"  平均净利率:     {profit.avg_net_margin:>14.1%}")
    print(f"  门店数:         {profit.store_count:>14}")
    print(f"  盈利门店:       {profit.profitable_count:>14}")
    print(f"  亏损门店:       {profit.loss_count:>14}")
    if target_stores > 0:
        print(f"  有真实目标门店: {target_stores:>14}")

    if risk:
        summary = risk.get("summary", {})
        print(f"\n  风险评估:")
        print(f"    低风险:       {summary.get('low_risk', 0):>14}")
        print(f"    中风险:       {summary.get('medium_risk', 0):>14}")
        print(f"    高风险:       {summary.get('high_risk', 0):>14}")
        print(f"    极高风险:     {summary.get('critical_risk', 0):>14}")

    if alloc and alloc.plan:
        print(f"\n  承压分配:")
        print(f"    分配门店数:   {alloc.plan.store_count:>14}")
        print(f"    总基线:      ¥{alloc.plan.total_baseline:>15,.0f}")
        print(f"    总分配:      ¥{alloc.plan.total_allocated:>15,.0f}")
        print(f"    平均增长率:   {alloc.plan.avg_growth_rate:>14.1%}")
        if alloc.fairness:
            print(f"    公平性等级:   {alloc.fairness.grade:>14}")

    print("=" * 60 + "\n")


def export_result(result: dict, output_path: str, target_df: pd.DataFrame | None = None):
    """导出分配明细到 CSV，如有真实目标则附加对比列"""
    alloc = result.get("allocation_result")
    if not alloc or not alloc.plan:
        logger.warning("无分配结果可导出")
        return

    rows = []
    for store_code, ar in alloc.plan.allocations.items():
        rows.append({
            "store_code": store_code,
            "baseline": round(ar.baseline, 2),
            "allocated_target": round(ar.target, 2),
            "pressure": round(ar.pressure, 2),
            "pressure_ratio": round(ar.pressure_ratio, 4),
            "growth_rate": round(ar.growth_rate, 4),
        })

    df = pd.DataFrame(rows)

    # 如有真实目标，附加对比
    if target_df is not None and not target_df.empty:
        # 取最新月目标
        latest = target_df.sort_values("target_month").groupby("store_no").last().reset_index()
        latest = latest.rename(columns={"monthly_target": "real_target"})
        df = df.merge(
            latest[["store_no", "real_target"]],
            left_on="store_code", right_on="store_no", how="left"
        ).drop(columns=["store_no"])
        df["target_diff"] = df["allocated_target"] - df["real_target"].fillna(0)
        df["target_diff_ratio"] = (df["target_diff"] / df["real_target"].replace(0, float("nan"))).round(4)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"结果已导出: {output_path} ({len(df)} 行)")


def main():
    parser = argparse.ArgumentParser(description="从 inputData CSV 执行全流程利润测算")
    parser.add_argument("--target", type=float, default=10_000_000, help="总利润目标 (默认 1000万)")
    parser.add_argument("--stores", type=str, default=None, help="指定门店编码，逗号分隔")
    parser.add_argument("--date-start", type=str, default=None, help="开始日期 YYYYMMDD")
    parser.add_argument("--date-end", type=str, default=None, help="结束日期 YYYYMMDD")
    parser.add_argument("--export", type=str, default=None, help="导出结果到 CSV 文件")
    parser.add_argument("--perspective", type=str, default="actual", choices=["actual", "rebate"],
                        help="口径: actual(业绩) | rebate(返利)")
    parser.add_argument("--min-days", type=int, default=10,
                        help="最少数据天数，低于此值的门店将被过滤 (默认 10)")
    parser.add_argument("--no-90day", action="store_true", help="不合并90天数据，仅用全量")
    parser.add_argument("--no-target", action="store_true", help="不使用真实目标数据")
    args = parser.parse_args()

    store_codes = args.stores.split(",") if args.stores else None
    use_90d = not args.no_90day

    # ----------------------------------------------------------
    # Step 1: 加载 CSV 数据（合并全量+90天）
    # ----------------------------------------------------------
    logger.info("=" * 40 + " 数据加载 " + "=" * 40)

    store_loss_df = load_merged_loss(use_90d=use_90d)
    pos_df = load_merged_pos(use_90d=use_90d)

    if store_loss_df.empty:
        logger.error("日损益数据为空，无法测算")
        sys.exit(1)

    # 加载真实目标数据
    target_df = None
    if not args.no_target:
        target_df = load_targets()

    # ----------------------------------------------------------
    # Step 2: 构建统一销售宽表
    # ----------------------------------------------------------
    logger.info("=" * 40 + " 构建宽表 " + "=" * 40)

    unified = build_unified_sales(
        store_loss_df=store_loss_df,
        pos_df=pos_df,
        perspective=args.perspective,
        store_codes=store_codes,
        date_start=args.date_start,
        date_end=args.date_end,
        min_days=args.min_days,
    )

    if unified.empty:
        logger.error("宽表为空，无法测算")
        sys.exit(1)

    # 释放原始 DataFrame 节省内存
    del store_loss_df, pos_df

    # ----------------------------------------------------------
    # Step 3: 执行全流程测算
    # ----------------------------------------------------------
    logger.info("=" * 40 + " 全流程测算 " + "=" * 38)

    from src.agents.baseline_agent import BaselineAgent
    from src.agents.profit_agent import ProfitAgent
    from src.agents.risk_agent import RiskAgent
    from src.agents.allocation_agent import AllocationAgent
    from src.allocation.weight_calculator import StoreProfile

    # Step 3a: 基线预估（使用日级数据，支持同比优化）
    baseline_agent = BaselineAgent()
    baselines = baseline_agent.estimate(unified)
    logger.info(f"基线预估完成: {len(baselines.get('store_baselines', {}))} 家门店")

    # Step 3b: 利润测算（按门店聚合后传入）
    agg_cols = {
        "revenue": "sum",
        "hq_taxcost": "sum",
        "gross_profit": "sum",
        "operating_expense": "sum",
        "bmanaging_exp": "sum",
        "operating_profit": "sum",
        "store_contribution": "sum",
        "salary_fee": "sum",
        "social_fee": "sum",
        "comprehensive_mall_fee": "sum",
        "decorate_fee": "sum",
        "express": "sum",
        "all_other_fee": "sum",
        "brand": "first",
        "region_top": "first",
        "perspective": "first",
    }
    # 如果有 POS 新增字段，也加入聚合
    for col in ["order_count", "qty_sold", "foot_traffic"]:
        if col in unified.columns:
            agg_cols[col] = "sum"
    for col in ["avg_ticket"]:
        if col in unified.columns:
            agg_cols[col] = "mean"

    store_agg = unified.groupby("store_no").agg(agg_cols).reset_index()

    profit_agent = ProfitAgent()
    profit_summary = profit_agent.calculate(store_agg)
    logger.info(f"利润测算完成: 净利润={profit_summary.total_net_profit:,.0f}")

    # Step 3c: 风险评估
    risk_agent = RiskAgent()
    risk_result = risk_agent.assess(store_agg)
    logger.info(f"风险评估完成: {risk_result['summary']}")

    # Step 3d: 承压分配（优先使用真实目标）
    allocation_result = None
    target_store_count = 0
    if baselines.get("store_baselines"):
        try:
            # 构建基线字典
            baseline_dict = baselines["store_baselines"]

            # 如有真实目标，用真实目标替代分配目标
            if target_df is not None and not target_df.empty:
                # 取最新月目标
                latest_targets = target_df.sort_values("target_month").groupby("store_no").last()
                real_targets = latest_targets["monthly_target"].to_dict()
                matched = set(baseline_dict.keys()) & set(real_targets.keys())
                target_store_count = len(matched)
                logger.info(f"真实目标匹配: {target_store_count} 家门店")

            profiles = {}
            for store_no, baseline in baseline_dict.items():
                profiles[store_no] = StoreProfile(
                    store_code=store_no,
                    historical_profit=baseline * 0.15,
                    sales_per_sqm=0,
                    commercial_tier="C",
                    city_level="二线",
                    store_area=100,
                    growth_rate=0,
                    opening_months=365,
                    baseline_sales=baseline,
                )

            allocation_agent = AllocationAgent()
            allocation_result = allocation_agent.allocate(
                total_target=args.target,
                baselines=baseline_dict,
                store_profiles=profiles,
            )
            logger.info(f"承压分配完成: {allocation_result.store_count} 家门店")

            # 如有真实目标，打印对比摘要
            if target_store_count > 0:
                alloc_targets = {c: a.target for c, a in allocation_result.plan.allocations.items()}
                diffs = []
                for store_no in matched:
                    real = real_targets[store_no]
                    alloc = alloc_targets.get(store_no, 0)
                    if real > 0:
                        diffs.append((alloc - real) / real)
                if diffs:
                    import numpy as np
                    arr = np.array(diffs)
                    logger.info(f"分配 vs 真实目标偏差: 均值={arr.mean():.1%}, 中位数={np.median(arr):.1%}, "
                                f"std={arr.std():.1%}")

        except Exception as e:
            logger.warning(f"承压分配失败: {e}")

    # ----------------------------------------------------------
    # Step 4: 输出结果
    # ----------------------------------------------------------
    result = {
        "sales_df": unified,
        "baselines": baselines,
        "profit_summary": profit_summary,
        "risk_result": risk_result,
        "allocation_result": allocation_result,
    }

    print_summary(result, args.target, target_stores=target_store_count)

    if args.export:
        export_result(result, args.export, target_df=target_df)

    return result


if __name__ == "__main__":
    main()
