"""数据采集器测试脚本

测试所有 6 个采集方法，验证数据结构和内容。

用法:
    cd profit-forecast
    python -m tests.test_collector
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.data.collectors.factory import create_collector

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

SEPARATOR = "=" * 70


async def test_stores(collector):
    """测试门店主数据"""
    print(f"\n{SEPARATOR}")
    print("  1. 门店主数据 (fetch_stores)")
    print(SEPARATOR)
    df = await collector.fetch_stores()
    print(f"  记录数: {len(df)}")
    print(f"  字段: {list(df.columns)}")
    if not df.empty:
        print(f"\n  前 5 条:")
        print(df.head().to_string(index=False, max_colwidth=20))
        print(f"\n  统计:")
        print(f"    门店数: {len(df)}")
        if "region" in df.columns:
            print(f"    大区分布: {df['region'].value_counts().to_dict()}")
        if "store_area" in df.columns:
            print(f"    平均面积: {df['store_area'].mean():.1f} m²")
        if "staff_count" in df.columns:
            print(f"    平均人数: {df['staff_count'].mean():.1f}")
    return df


async def test_daily_sales(collector):
    """测试日销售数据"""
    print(f"\n{SEPARATOR}")
    print("  2. 日销售/损益数据 (fetch_daily_sales)")
    print(SEPARATOR)

    # 取最近 30 天
    end = date.today()
    start = end - timedelta(days=30)
    df = await collector.fetch_daily_sales(start_date=start, end_date=end)
    print(f"  查询范围: {start} ~ {end}")
    print(f"  记录数: {len(df)}")
    print(f"  字段: {list(df.columns)}")
    if not df.empty:
        print(f"\n  前 5 条:")
        print(df.head().to_string(index=False, max_colwidth=18))
        if "sales_amount" in df.columns:
            print(f"\n  统计:")
            print(f"    总销售额: {df['sales_amount'].sum():,.2f}")
            print(f"    日均销售额: {df.groupby('sale_date')['sales_amount'].sum().mean():,.2f}")
            if "brand" in df.columns:
                print(f"    品牌数: {df['brand'].nunique()}")
    return df


async def test_monthly_metrics(collector):
    """测试月度指标"""
    print(f"\n{SEPARATOR}")
    print("  3. 月度指标 (fetch_monthly_metrics)")
    print(SEPARATOR)

    df = await collector.fetch_monthly_metrics(start_month="2025-06", end_month="2026-05")
    print(f"  查询范围: 2025-06 ~ 2026-05")
    print(f"  记录数: {len(df)}")
    print(f"  字段: {list(df.columns)}")
    if not df.empty:
        print(f"\n  前 5 条:")
        print(df.head().to_string(index=False, max_colwidth=18))
        if "sales_amount" in df.columns:
            print(f"\n  统计:")
            monthly = df.groupby("year_month")["sales_amount"].sum()
            print(f"    月度销售额趋势:")
            for ym, val in monthly.items():
                print(f"      {ym}: {val:>15,.2f}")
            if "gross_margin" in df.columns:
                print(f"    平均毛利率: {df['gross_margin'].mean():.2%}")
            if "sales_per_sqm" in df.columns:
                print(f"    平均坪效: {df['sales_per_sqm'].mean():,.2f}")
    return df


async def test_targets(collector):
    """测试目标数据"""
    print(f"\n{SEPARATOR}")
    print("  4. 目标数据 (fetch_targets)")
    print(SEPARATOR)

    df = await collector.fetch_targets(target_type="monthly", target_month="2026-05")
    print(f"  目标类型: monthly")
    print(f"  目标月份: 2026-05")
    print(f"  记录数: {len(df)}")
    print(f"  字段: {list(df.columns)}")
    if not df.empty:
        print(f"\n  前 5 条:")
        print(df.head().to_string(index=False, max_colwidth=18))
        if "sales_target" in df.columns:
            print(f"\n  统计:")
            print(f"    总销售目标: {df['sales_target'].sum():,.2f}")
            print(f"    平均目标: {df['sales_target'].mean():,.2f}")
        if "profit_target" in df.columns:
            print(f"    总利润目标: {df['profit_target'].sum():,.2f}")
    return df


async def test_staff(collector):
    """测试门店人员数据"""
    print(f"\n{SEPARATOR}")
    print("  5. 门店人员数据 (fetch_staff)")
    print(SEPARATOR)

    df = await collector.fetch_staff()
    print(f"  记录数: {len(df)}")
    print(f"  字段: {list(df.columns)}")
    if not df.empty:
        print(f"\n  前 5 条:")
        print(df.head().to_string(index=False, max_colwidth=18))
        if "staff_count" in df.columns:
            print(f"\n  统计:")
            print(f"    总人数: {df['staff_count'].sum():.0f}")
            print(f"    平均人数/店: {df['staff_count'].mean():.1f}")
        if "role" in df.columns:
            print(f"    角色分布: {df['role'].value_counts().to_dict()}")
    return df


async def test_cost_structure(collector):
    """测试成本结构"""
    print(f"\n{SEPARATOR}")
    print("  6. 成本结构 (fetch_cost_structure)")
    print(SEPARATOR)

    df = await collector.fetch_cost_structure(start_month="2025-06", end_month="2026-05")
    print(f"  查询范围: 2025-06 ~ 2026-05")
    print(f"  记录数: {len(df)}")
    print(f"  字段: {list(df.columns)}")
    if not df.empty:
        print(f"\n  前 3 条:")
        print(df.head(3).to_string(index=False, max_colwidth=18))
        # 成本构成分析
        cost_fields = [c for c in df.columns if c not in ("store_code", "year_month", "brand")]
        if cost_fields:
            print(f"\n  成本构成汇总:")
            for field in cost_fields:
                total = df[field].sum()
                if total > 0:
                    print(f"    {field:30s}: {total:>15,.2f}")
    return df


async def main():
    """主测试流程"""
    print(f"\n{SEPARATOR}")
    print("  利润测算系统 — 数据采集器测试")
    print(f"  数据源: Mock (模拟数据)")
    print(f"  日期: {date.today()}")
    print(SEPARATOR)

    # 创建采集器
    collector = create_collector("mock")

    async with collector:
        # 测试全部 6 个方法
        results = {}

        results["stores"] = await test_stores(collector)
        results["daily_sales"] = await test_daily_sales(collector)
        results["monthly_metrics"] = await test_monthly_metrics(collector)
        results["targets"] = await test_targets(collector)
        results["staff"] = await test_staff(collector)
        results["cost_structure"] = await test_cost_structure(collector)

        # 汇总
        print(f"\n{SEPARATOR}")
        print("  测试汇总")
        print(SEPARATOR)
        all_pass = True
        for name, df in results.items():
            status = "PASS" if not df.empty else "FAIL"
            if df.empty:
                all_pass = False
            print(f"  [{status}] {name:20s} → {len(df)} 行, {len(df.columns)} 列")

        print(f"\n  结果: {'全部通过 ✓' if all_pass else '存在失败 ✗'}")
        print(SEPARATOR)

        # 数据关联性检查
        print(f"\n{SEPARATOR}")
        print("  数据关联性检查")
        print(SEPARATOR)
        stores = results["stores"]
        if not stores.empty:
            store_codes = set(stores["store_code"])
            for name, df in results.items():
                if name == "stores" or df.empty:
                    continue
                if "store_code" in df.columns:
                    found = set(df["store_code"]) & store_codes
                    coverage = len(found) / len(store_codes) * 100 if store_codes else 0
                    print(f"  {name:20s}: {len(found)}/{len(store_codes)} 门店有数据 ({coverage:.0f}%)")


if __name__ == "__main__":
    asyncio.run(main())
