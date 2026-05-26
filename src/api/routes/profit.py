"""利润测算 API 路由"""

from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/profit", tags=["profit"])


@router.post("/calculate")
async def calculate_profit(
    store_no: Optional[str] = Query(None, description="门店编码"),
    region: Optional[str] = Query(None, description="区域"),
    brand: Optional[str] = Query(None, description="品牌"),
    date_start: str = Query(..., description="开始日期 YYYYMMDD"),
    date_end: str = Query(..., description="结束日期 YYYYMMDD"),
    perspective: str = Query("actual", description="口径: actual|rebate"),
):
    """计算利润"""
    from src.agents.data_agent import DataAgent
    from src.profit.profit_calculator import ProfitCalculator

    agent = DataAgent()
    df = agent.collect(store_no=store_no, date_range=(date_start, date_end), perspective=perspective)

    if region:
        df = df[df["region_top"] == region]
    if brand:
        df = df[df["brand"] == brand]

    calc = ProfitCalculator()
    summary = calc.calculate_from_sales(df)

    return {
        "total_revenue": summary.total_revenue,
        "total_gross_profit": summary.total_gross_profit,
        "total_operating_profit": summary.total_operating_profit,
        "total_net_profit": summary.total_net_profit,
        "avg_gross_margin": summary.avg_gross_margin,
        "store_count": summary.store_count,
        "profitable_count": summary.profitable_count,
        "loss_count": summary.loss_count,
    }


@router.get("/drill-down")
async def drill_down(
    dimension: str = Query(..., description="维度: region|brand|store"),
    date_start: str = Query(..., description="开始日期"),
    date_end: str = Query(..., description="结束日期"),
    perspective: str = Query("actual", description="口径"),
):
    """按维度下钻"""
    from src.agents.data_agent import DataAgent
    from src.profit.profit_calculator import ProfitCalculator

    agent = DataAgent()
    df = agent.collect(date_range=(date_start, date_end), perspective=perspective)

    calc = ProfitCalculator()

    if dimension == "store":
        summary = calc.calculate_from_sales(df)
        rows = []
        for code, sp in summary.store_profits.items():
            rows.append({
                "store_no": code,
                "revenue": sp.revenue,
                "gross_profit": sp.gross_profit,
                "operating_profit": sp.operating_profit,
                "net_profit": sp.net_profit,
            })
        return {"dimension": "store", "data": rows}
    else:
        col = "region_top" if dimension == "region" else "brand"
        results = []
        for group_name, group_df in df.groupby(col):
            summary = calc.calculate_from_sales(group_df)
            results.append({
                "name": group_name,
                "revenue": summary.total_revenue,
                "gross_profit": summary.total_gross_profit,
                "operating_profit": summary.total_operating_profit,
                "net_profit": summary.total_net_profit,
                "store_count": summary.store_count,
            })
        return {"dimension": dimension, "data": results}
