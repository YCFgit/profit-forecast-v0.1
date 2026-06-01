"""利润测算 API 路由"""

from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api/v1/profit", tags=["profit"])


@router.post("/calculate")
async def calculate_profit(
    total_target: float = Query(10000000, description="总利润目标"),
):
    """计算利润（全流程：基线→分配→利润测算）"""
    from src.agents.baseline_agent import BaselineAgent
    from src.agents.allocation_agent import AllocationAgent
    from src.data.collectors.mysql_collector import MySQLCollector
    from src.profit.profit_calculator import ProfitCalculator

    collector = MySQLCollector()

    # 1. 采集数据
    stores_df = collector.collect_stores()
    monthly_metrics = collector.collect_monthly_metrics(active_only=True)

    # 过滤：只保留有月度数据的门店
    stores_with_metrics = monthly_metrics["store_code"].unique()
    stores_df = stores_df[stores_df["store_code"].isin(stores_with_metrics)]

    # 2. 基线预估
    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(monthly_metrics)

    # 3. 承压分配
    allocation_agent = AllocationAgent()
    store_profiles = allocation_agent.build_store_profiles(stores_df, monthly_metrics)
    allocation_result = allocation_agent.allocate(
        total_target=total_target,
        baselines=baseline_result.baselines,
        store_profiles=store_profiles,
        with_scenarios=False,
    )

    # 4. 利润测算（用分配目标）
    calc = ProfitCalculator()
    targets = {c: a.target for c, a in allocation_result.plan.allocations.items()}
    summary = calc.calculate(targets=targets)

    # 构建 P&L 表
    pnl = [
        {"项目": "总收入", "金额": round(summary.total_revenue, 0)},
        {"项目": "采购成本", "金额": -round(summary.total_cogs, 0)},
        {"项目": "毛利", "金额": round(summary.total_gross_profit, 0)},
        {"项目": "运营费用", "金额": -round(summary.total_operating_expense, 0)},
        {"项目": "营业利润", "金额": round(summary.total_operating_profit, 0)},
        {"项目": "税费", "金额": -round(summary.total_tax, 0)},
        {"项目": "净利润", "金额": round(summary.total_net_profit, 0)},
    ]

    # 构建门店对比数据
    comparison = []
    for code, alloc in sorted(allocation_result.plan.allocations.items()):
        baseline_rev = alloc.baseline
        target_rev = alloc.target
        sp = summary.store_profits.get(code)
        baseline_profit = sp.net_profit if sp else 0
        # 按目标收入估算利润
        target_profit = target_rev * (summary.avg_net_margin if summary.avg_net_margin else 0.05)
        comparison.append({
            "门店编码": code,
            "基线收入": round(baseline_rev, 0),
            "目标收入": round(target_rev, 0),
            "收入增长": f"{alloc.growth_rate:.1%}",
            "基线净利": round(baseline_profit, 0),
            "目标净利": round(target_profit, 0),
            "净利增长": round(target_profit - baseline_profit, 0),
        })

    # Top / Bottom 排行
    store_net = [(c, sp.net_profit) for c, sp in summary.store_profits.items()]
    store_net.sort(key=lambda x: x[1], reverse=True)
    top_stores = [{"门店编码": c, "净利润": round(v, 0)} for c, v in store_net[:5]]
    bottom_stores = [{"门店编码": c, "净利润": round(v, 0)} for c, v in store_net[-5:]]

    return {
        "summary": {
            "总收入": round(summary.total_revenue, 0),
            "总毛利": round(summary.total_gross_profit, 0),
            "平均毛利率": round(summary.avg_gross_margin, 4),
            "总净利润": round(summary.total_net_profit, 0),
            "总运营费用": round(summary.total_operating_expense, 0),
            "总营业利润": round(summary.total_operating_profit, 0),
            "平均营业利润率": round(summary.avg_operating_margin, 4),
            "平均净利率": round(summary.avg_net_margin, 4),
        },
        "pnl": pnl,
        "comparison": comparison,
        "top_stores": top_stores,
        "bottom_stores": bottom_stores,
    }


@router.get("/drill-down")
async def drill_down(
    dimension: str = Query(..., description="维度: region|brand|store"),
    date_start: str = Query(None, description="开始日期"),
    date_end: str = Query(None, description="结束日期"),
    perspective: str = Query("actual", description="口径"),
):
    """按维度下钻"""
    from src.data.collectors.mysql_collector import MySQLCollector
    from src.profit.profit_calculator import ProfitCalculator

    collector = MySQLCollector()
    start_month = f"{date_start[:4]}-{date_start[4:6]}" if date_start and len(date_start) >= 6 else None
    end_month = f"{date_end[:4]}-{date_end[4:6]}" if date_end and len(date_end) >= 6 else None
    df = collector.collect_unified_sales(start_month=start_month, end_month=end_month)

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
