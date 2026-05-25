"""基线预估模型端到端测试

用 Mock 数据验证完整的 预处理 → 规则引擎 → 精度评估 流程。

用法:
    cd profit-forecast
    python3 -m tests.test_baseline
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

SEPARATOR = "=" * 70


async def main():
    print(f"\n{SEPARATOR}")
    print("  基线预估模型 — 端到端测试")
    print(f"  日期: {date.today()}")
    print(SEPARATOR)

    # Step 1: 获取 Mock 数据
    from src.data.collectors.factory import create_collector

    collector = create_collector("mock")
    async with collector:
        stores_df = await collector.fetch_stores()
        sales_df = await collector.fetch_daily_sales()
        monthly_metrics = await collector.fetch_monthly_metrics()
        switch_status = await collector.fetch_switch_status()

    print(f"\n  数据准备:")
    print(f"    门店数: {len(stores_df)}")
    print(f"    销售记录: {len(sales_df)}")
    print(f"    月度指标: {len(monthly_metrics)} 条")

    # Step 2: 测试预处理
    from src.forecasting.baseline.time_series import (
        TimeSeriesPreprocessor,
        prepare_store_monthly_data,
    )
    from src.forecasting.baseline.outlier_detector import OutlierDetector
    from src.forecasting.baseline.seasonal_decompose import (
        SeasonalDecomposer,
        get_shoe_seasonal_default,
    )

    test_store = stores_df["store_code"].iloc[0]
    store_sales = sales_df[sales_df["store_code"] == test_store].copy()

    print(f"\n{SEPARATOR}")
    print(f"  测试门店: {test_store}")
    print(f"  销售记录: {len(store_sales)} 条")
    print(SEPARATOR)

    # 2a. 月度聚合
    monthly = prepare_store_monthly_data(sales_df, test_store)
    print(f"\n  月度数据: {len(monthly)} 个月")
    print(f"  月度销售额:")
    for dt, val in monthly.items():
        print(f"    {dt.strftime('%Y-%m')}: {val:>12,.0f}")

    # 2b. 异常检测
    print(f"\n{SEPARATOR}")
    print("  异常值检测")
    print(SEPARATOR)
    detector = OutlierDetector(iqr_factor=1.5)
    clean, outlier_result = detector.detect(monthly)
    print(f"  总数据点: {outlier_result.total_points}")
    print(f"  异常值数: {outlier_result.outlier_count}")
    print(f"  异常率: {outlier_result.outlier_rate:.1%}")

    # 2c. 季节性分解
    print(f"\n{SEPARATOR}")
    print("  季节性分解")
    print(SEPARATOR)
    decomposer = SeasonalDecomposer(method="multiplicative")
    seasonal = decomposer.decompose(clean.dropna())
    print(f"  季节强度: {seasonal.strength:.2f}")
    print(f"  季节因子:")
    for month, factor in sorted(seasonal.seasonal_index.items()):
        bar = "█" * int(factor * 20)
        print(f"    {month:2d}月: {factor:.3f} {bar}")

    # 行业默认因子
    default_factors = get_shoe_seasonal_default()
    print(f"\n  行业默认因子 vs 实际因子:")
    for month in range(1, 13):
        d = default_factors[month]
        a = seasonal.seasonal_index.get(month, 1.0)
        print(f"    {month:2d}月: 默认={d:.3f}, 实际={a:.3f}, 差异={abs(d-a):.3f}")

    # Step 3: v2 业务规则引擎预估
    print(f"\n{SEPARATOR}")
    print("  v2 业务规则引擎预估")
    print(SEPARATOR)

    from src.forecasting.rules.baseline_engine import BaselineEngine

    engine = BaselineEngine()
    engine_result = engine.run(
        stores_df=stores_df,
        monthly_metrics_df=monthly_metrics,
        switch_status_df=switch_status,
        target_year=date.today().year,
        target_month=date.today().month,
    )

    print(f"\n  门店数: {engine_result.store_count}")
    print(f"  分类分布:")
    for cat, count in engine_result.category_summary.items():
        print(f"    {cat}: {count} 家")

    # 查看单店详情
    store_info = engine_result.model_info.get(test_store, {})
    print(f"\n  测试门店 {test_store}:")
    print(f"    分类: {store_info.get('category', 'N/A')}")
    print(f"    机制: {store_info.get('mechanism', 'N/A')}")
    print(f"    基线预估: {engine_result.baselines.get(test_store, 0):,.0f}")

    # Step 4: 精度评估（用历史月对比）
    print(f"\n{SEPARATOR}")
    print("  精度评估（最近 3 个月回测）")
    print(SEPARATOR)

    from src.forecasting.evaluation.accuracy_metrics import evaluate
    import numpy as np

    # 取最近 3 个月的实际值与预估值对比
    recent_months = sorted(monthly_metrics["year_month"].unique())[-3:]
    actual_vals = []
    pred_vals = []

    for ym in recent_months:
        month_data = monthly_metrics[
            (monthly_metrics["year_month"] == ym)
            & (monthly_metrics["store_code"] == test_store)
        ]
        if not month_data.empty:
            actual_vals.append(month_data["sales_amount"].values[0])
            # 用引擎对该月做预估
            try:
                y, m = int(ym[:4]), int(ym[5:7])
                tmp_result = engine.run(
                    stores_df=stores_df,
                    monthly_metrics_df=monthly_metrics[monthly_metrics["year_month"] < ym],
                    target_year=y,
                    target_month=m,
                )
                pred_vals.append(tmp_result.baselines.get(test_store, 0))
            except Exception:
                pred_vals.append(0)

    if actual_vals and pred_vals:
        acc = evaluate(np.array(actual_vals), np.array(pred_vals))
        print(f"  MAPE: {acc.mape:.2%}")
        print(f"  RMSE: {acc.rmse:,.0f}")
        print(f"  R²: {acc.r2:.4f}")
    else:
        print("  数据不足，跳过精度评估")

    # Step 5: 批量测试（全量门店）
    print(f"\n{SEPARATOR}")
    print("  全量门店基线预估")
    print(SEPARATOR)

    batch_results = []
    for code, baseline_val in engine_result.baselines.items():
        info = engine_result.model_info.get(code, {})
        batch_results.append({
            "store": code,
            "category": info.get("category", "unknown"),
            "mechanism": info.get("mechanism", "N/A"),
            "baseline": baseline_val,
        })

    # 按分类汇总
    from collections import defaultdict
    cat_stats = defaultdict(list)
    for r in batch_results:
        cat_stats[r["category"]].append(r["baseline"])

    print(f"\n  分类基线汇总:")
    for cat, vals in sorted(cat_stats.items()):
        total = sum(vals)
        avg = total / len(vals) if vals else 0
        print(f"    {cat:15s}: {len(vals):3d} 家, 总额={total:>14,.0f}, 均值={avg:>12,.0f}")

    total_baseline = sum(r["baseline"] for r in batch_results)
    print(f"\n  全部门店基线总额: {total_baseline:,.0f}")

    print(f"\n{SEPARATOR}")
    print("  基线预估端到端测试完成 ✓（v2 业务规则引擎）")
    print(SEPARATOR)


if __name__ == "__main__":
    asyncio.run(main())
