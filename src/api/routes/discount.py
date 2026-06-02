"""折扣率预测 API 路由"""

from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/v1/discount", tags=["discount"])


@router.post("/predict")
async def predict_discount(
    brand: str = Query(..., description="品牌"),
    region: str = Query(..., description="区域"),
    target_month: str = Query(..., description="目标月份 YYYY-MM"),
):
    """预测折扣率

    使用 11 种方法自动选最优（季节修正/同比推算/近期均值等）。
    """
    from src.discount.discount_predictor import DiscountPredictor
    from src.data.collectors.mysql_collector import MySQLCollector

    collector = MySQLCollector()

    # 从数据库获取品牌×区域的历史折扣率
    # 这里用月度指标中的 sales_amount/list_price 近似
    monthly = collector.collect_monthly_metrics(active_only=False)

    # 构建历史数据（按品牌×区域聚合）
    stores_df = collector.collect_stores()
    brand_region_stores = stores_df[
        (stores_df["brand"] == brand) & (stores_df["region"] == region)
    ]["store_code"].unique()

    br_monthly = monthly[monthly["store_code"].isin(brand_region_stores)]
    history = []
    for ym, group in br_monthly.groupby("year_month"):
        ym_int = int(ym.replace("-", ""))
        avg_rate = 0.75  # 默认折扣率
        if "avg_discount" in group.columns and group["avg_discount"].notna().any():
            avg_rate = group["avg_discount"].mean() / 100  # 假设存储为百分比
        history.append((ym_int, avg_rate))
    history.sort(key=lambda x: -x[0])

    # 全国级历史
    national_history = []
    for ym, group in monthly.groupby("year_month"):
        ym_int = int(ym.replace("-", ""))
        avg_rate = 0.75
        if "avg_discount" in group.columns and group["avg_discount"].notna().any():
            avg_rate = group["avg_discount"].mean() / 100
        national_history.append((ym_int, avg_rate))
    national_history.sort(key=lambda x: -x[0])

    predictor = DiscountPredictor()
    result = predictor.predict(
        brand=brand,
        region=region,
        target_month=target_month,
        history=history,
        national_history=national_history,
    )

    return {
        "status": "success",
        "brand": brand,
        "region": region,
        "target_month": target_month,
        "predicted_rate": result.predicted_rate,
        "method": result.method,
        "confidence": result.confidence,
        "all_predictions": result.all_predictions,
    }


@router.post("/batch-predict")
async def batch_predict_discount(
    target_month: str = Query(..., description="目标月份 YYYY-MM"),
):
    """批量预测所有品牌×区域的折扣率"""
    from src.discount.discount_predictor import DiscountPredictor
    from src.data.collectors.mysql_collector import MySQLCollector

    collector = MySQLCollector()
    stores_df = collector.collect_stores()
    monthly = collector.collect_monthly_metrics(active_only=False)

    # 按品牌×区域分组
    brand_regions = stores_df.groupby(["brand", "region"])["store_code"].unique().to_dict()

    predictor = DiscountPredictor()
    results = []

    for (brand, region), store_codes in brand_regions.items():
        br_monthly = monthly[monthly["store_code"].isin(store_codes)]
        history = []
        for ym, group in br_monthly.groupby("year_month"):
            ym_int = int(ym.replace("-", ""))
            avg_rate = 0.75
            if "avg_discount" in group.columns and group["avg_discount"].notna().any():
                avg_rate = group["avg_discount"].mean() / 100
            history.append((ym_int, avg_rate))
        history.sort(key=lambda x: -x[0])

        if len(history) < 3:
            continue

        result = predictor.predict(
            brand=brand,
            region=region,
            target_month=target_month,
            history=history,
        )

        results.append({
            "brand": brand,
            "region": region,
            "predicted_rate": result.predicted_rate,
            "method": result.method,
            "confidence": result.confidence,
        })

    return {
        "status": "success",
        "target_month": target_month,
        "count": len(results),
        "results": sorted(results, key=lambda x: x["predicted_rate"]),
    }
