"""利润测算 API 路由"""

from fastapi import APIRouter, Query

from src.api.data_loader import load_stores, load_monthly_metrics
from src.api.cache import result_cache

router = APIRouter(prefix="/api/v1/profit", tags=["profit"])


@router.post("/calculate")
async def calculate_profit(
    total_target: float = Query(10000000, description="总利润目标"),
):
    """计算利润（全流程：基线→分配→利润测算）"""
    cache_key = f"profit:{total_target}"
    cached = result_cache.get(cache_key)
    if cached:
        return cached

    from src.agents.baseline_agent import BaselineAgent
    from src.agents.allocation_agent import AllocationAgent
    from src.profit.profit_calculator import ProfitCalculator

    stores_df = await load_stores()
    monthly_metrics = await load_monthly_metrics()

    # 过滤：只保留有月度数据的门店
    stores_with_metrics = monthly_metrics["store_code"].unique()
    stores_df = stores_df[stores_df["store_code"].isin(stores_with_metrics)]

    # 基线预估
    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(monthly_metrics)

    # 承压分配
    allocation_agent = AllocationAgent()
    store_profiles = allocation_agent.build_store_profiles(stores_df, monthly_metrics)
    allocation_result = allocation_agent.allocate(
        total_target=total_target,
        baselines=baseline_result.baselines,
        store_profiles=store_profiles,
        with_scenarios=False,
    )

    # 利润测算
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

    response = {
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
    result_cache.set(cache_key, response)
    return response


@router.post("/incremental")
async def calculate_incremental_profit(
    total_target: float = Query(..., description="老板总目标"),
    method: str = Query("mip", description="分配方法: mip | weight"),
):
    """增量利润推算（变动/固定成本分离）"""
    from src.agents.baseline_agent import BaselineAgent
    from src.agents.allocation_agent import AllocationAgent
    from src.profit.incremental_profit import IncrementalProfitCalculator, StoreCostRates

    stores_df = await load_stores()
    monthly_metrics = await load_monthly_metrics()

    stores_with_metrics = monthly_metrics["store_code"].unique()
    stores_df = stores_df[stores_df["store_code"].isin(stores_with_metrics)]

    # 基线预估
    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(
        monthly_metrics=monthly_metrics,
        stores_df=stores_df,
    )
    baselines = baseline_result.baselines

    # 承压分配
    allocation_agent = AllocationAgent()
    if method == "mip":
        p75_ceilings = AllocationAgent.compute_p75_ceilings(monthly_metrics)
        allocation_result = allocation_agent.allocate_mip(
            total_target=total_target,
            baselines=baselines,
            p75_sales=p75_ceilings,
        )
        targets = {c: s.target for c, s in allocation_result.mip_result.stores.items()}
        achievement_probs = {c: s.achievement_probability for c, s in allocation_result.mip_result.stores.items()}
    else:
        store_profiles = allocation_agent.build_store_profiles(stores_df, monthly_metrics)
        allocation_result = allocation_agent.allocate(
            total_target=total_target,
            baselines=baselines,
            store_profiles=store_profiles,
        )
        targets = {c: a.target for c, a in allocation_result.plan.allocations.items()}
        achievement_probs = {c: 1.0 for c in targets}

    # 增量利润推算
    calc = IncrementalProfitCalculator()
    cost_rates = {code: StoreCostRates(store_code=code) for code in baselines}
    result = calc.calculate(
        baselines=baselines,
        targets=targets,
        cost_rates=cost_rates,
        achievement_probs=achievement_probs,
    )

    # 构建门店明细
    store_details = []
    for code, detail in sorted(result.stores.items(), key=lambda x: -x[1].net_profit):
        store_details.append({
            "store_code": code,
            "baseline": detail.baseline,
            "expected_revenue": detail.expected_revenue,
            "variable_margin": detail.variable_margin,
            "net_profit": detail.net_profit,
            "m_variable": detail.m_variable,
        })

    return {
        "status": "success",
        "method": method,
        "summary": {
            "total_baseline": result.total_baseline,
            "total_expected_revenue": result.total_expected_revenue,
            "total_variable_margin": result.total_variable_margin,
            "total_net_profit": result.total_net_profit,
            "avg_m_variable": result.avg_m_variable,
            "store_count": result.store_count,
        },
        "pnl": [
            {"项目": "基线收入", "金额": round(result.total_baseline, 0)},
            {"项目": "期望收入", "金额": round(result.total_expected_revenue, 0)},
            {"项目": "变动边际利润", "金额": round(result.total_variable_margin, 0)},
            {"项目": "净利润", "金额": round(result.total_net_profit, 0)},
        ],
        "region_summary": {
            k: {kk: round(vv, 0) if isinstance(vv, float) else vv for kk, vv in v.items()}
            for k, v in result.region_summary.items()
        },
        "top_stores": store_details[:10],
        "bottom_stores": store_details[-10:],
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
