"""回测验证 API 路由"""

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


@router.post("/prediction")
async def backtest_prediction(
    test_months: int = Query(12, description="回测月数"),
):
    """预测回测 — 最近 N 个月滚动验证

    输出：
    - 平均 WMAPE（加权平均绝对百分比误差）
    - 平均汇总偏差
    - 平均中位误差
    - 分品类精度
    - 每月明细
    """
    from src.forecasting.backtester import PredictionBacktester
    from src.data.collectors.mysql_collector import MySQLCollector

    collector = MySQLCollector()
    stores_df = collector.collect_stores()
    monthly_metrics = collector.collect_monthly_metrics(active_only=False)

    backtester = PredictionBacktester()
    result = backtester.run(
        stores_df=stores_df,
        monthly_metrics=monthly_metrics,
        test_months=test_months,
    )

    monthly_details = []
    for r in result.monthly_results:
        monthly_details.append({
            "target_month": r.target_month,
            "store_count": r.store_count,
            "total_predicted": r.total_predicted,
            "total_actual": r.total_actual,
            "wmape": round(r.wmape, 4),
            "aggregate_bias": round(r.aggregate_bias, 4),
            "median_ape": round(r.median_ape, 4),
            "category_wmape": {k: round(v, 4) for k, v in r.category_wmape.items()},
        })

    return {
        "status": "success",
        "summary": {
            "test_months": result.test_months,
            "avg_wmape": round(result.avg_wmape, 4),
            "avg_aggregate_bias": round(result.avg_aggregate_bias, 4),
            "avg_median_ape": round(result.avg_median_ape, 4),
        },
        "category_summary": {k: round(v, 4) for k, v in result.category_summary.items()},
        "monthly_details": monthly_details,
    }


@router.post("/discount")
async def backtest_discount(
    brand: str = Query(..., description="品牌"),
    region: str = Query(..., description="区域"),
):
    """折扣率回测 — 对单个品牌×区域做 WMAE 回测选型"""
    from src.discount.backtester import DiscountBacktester
    from src.data.collectors.mysql_collector import MySQLCollector

    collector = MySQLCollector()
    stores_df = collector.collect_stores()
    monthly = collector.collect_monthly_metrics(active_only=False)

    # 获取品牌×区域的门店
    brand_region_stores = stores_df[
        (stores_df["brand"] == brand) & (stores_df["region"] == region)
    ]["store_code"].unique()

    br_monthly = monthly[monthly["store_code"].isin(brand_region_stores)]
    history = []
    weights = []
    for ym, group in br_monthly.groupby("year_month"):
        ym_int = int(ym.replace("-", ""))
        avg_rate = 0.75
        if "avg_discount" in group.columns and group["avg_discount"].notna().any():
            avg_rate = group["avg_discount"].mean() / 100
        total_rev = group["sales_amount"].sum() if "sales_amount" in group.columns else 1000000
        history.append((ym_int, avg_rate))
        weights.append((ym_int, total_rev))
    history.sort(key=lambda x: x[0])
    weights.sort(key=lambda x: x[0])

    backtester = DiscountBacktester()
    result = backtester.backtest(
        brand=brand,
        region=region,
        history=history,
        weights=weights,
    )

    method_results = {}
    for name, res in result.method_results.items():
        method_results[name] = {
            "wmae": round(res.wmae, 4),
            "mae": round(res.mae, 4),
            "coverage": round(res.coverage, 4),
            "prediction_count": res.prediction_count,
        }

    return {
        "status": "success",
        "brand": brand,
        "region": region,
        "best_method": result.best_method,
        "best_wmae": round(result.best_wmae, 4),
        "test_months": len(result.test_months),
        "method_results": method_results,
    }
