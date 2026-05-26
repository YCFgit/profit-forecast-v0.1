"""返利口径处理

对比业绩口径（d1_pf_）和返利口径（d2_）的差异，
计算返利对利润的影响。
"""

import pandas as pd
from loguru import logger


def compare_perspectives(
    actual_df: pd.DataFrame,
    rebate_df: pd.DataFrame,
) -> pd.DataFrame:
    """对比业绩口径和返利口径

    Args:
        actual_df: 业绩口径数据（SalesLoader.load_store_loss(perspective="actual")）
        rebate_df: 返利口径数据（SalesLoader.load_store_loss(perspective="rebate")）

    Returns:
        DataFrame，含两个口径的对比指标
    """
    if actual_df.empty or rebate_df.empty:
        logger.warning("[Rebate] 数据为空，无法对比")
        return pd.DataFrame()

    # 取关键字段
    actual_key = actual_df[["store_no", "base_date", "sales_amount", "gross_profit", "operating_profit"]].copy()
    actual_key = actual_key.rename(columns={
        "sales_amount": "actual_sales",
        "gross_profit": "actual_gross_profit",
        "operating_profit": "actual_operating_profit",
    })

    rebate_key = rebate_df[["store_no", "base_date", "sales_amount", "gross_profit", "operating_profit"]].copy()
    rebate_key = rebate_key.rename(columns={
        "sales_amount": "rebate_sales",
        "gross_profit": "rebate_gross_profit",
        "operating_profit": "rebate_operating_profit",
    })

    merged = actual_key.merge(rebate_key, on=["store_no", "base_date"], how="inner")

    # 计算差异
    merged["sales_diff"] = merged["rebate_sales"] - merged["actual_sales"]
    merged["sales_diff_pct"] = (
        merged["sales_diff"] / merged["actual_sales"].replace(0, float("nan"))
    )
    merged["gross_profit_diff"] = merged["rebate_gross_profit"] - merged["actual_gross_profit"]
    merged["operating_profit_diff"] = merged["rebate_operating_profit"] - merged["actual_operating_profit"]

    logger.info(f"[Rebate] 口径对比: {len(merged)} 条记录")
    return merged


def summarize_rebate_impact(comparison_df: pd.DataFrame) -> dict:
    """汇总返利影响

    Returns:
        {
            "total_sales_diff": float,      # 总销售额差异
            "total_gp_diff": float,          # 总毛利差异
            "total_op_diff": float,          # 总营业利润差异
            "avg_sales_diff_pct": float,     # 平均销售额差异率
            "store_count": int,
            "stores_positive": int,          # 返利>业绩的门店数
            "stores_negative": int,          # 返利<业绩的门店数
        }
    """
    if comparison_df.empty:
        return {}

    store_agg = comparison_df.groupby("store_no").agg(
        sales_diff=("sales_diff", "sum"),
        gross_profit_diff=("gross_profit_diff", "sum"),
        operating_profit_diff=("operating_profit_diff", "sum"),
        sales_diff_pct=("sales_diff_pct", "mean"),
    ).reset_index()

    return {
        "total_sales_diff": round(store_agg["sales_diff"].sum(), 2),
        "total_gp_diff": round(store_agg["gross_profit_diff"].sum(), 2),
        "total_op_diff": round(store_agg["operating_profit_diff"].sum(), 2),
        "avg_sales_diff_pct": round(store_agg["sales_diff_pct"].mean(), 4),
        "store_count": len(store_agg),
        "stores_positive": int((store_agg["sales_diff"] > 0).sum()),
        "stores_negative": int((store_agg["sales_diff"] < 0).sum()),
    }
