"""
数据导出脚本

从 StarRocks 导出原始数据为 CSV 文件，方便离线分析或导入其他系统。

使用方式:
    # 导出全部数据
    python scripts/export_to_csv.py

    # 导出到指定目录
    python scripts/export_to_csv.py --output ./data/export

    # 只导出特定表
    python scripts/export_to_csv.py --tables stores,store_loss

    # 指定门店
    python scripts/export_to_csv.py --stores ST0001,ST0002
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")


async def export_data(args: argparse.Namespace):
    """导出数据"""
    from src.data.collectors.starrocks_collector import StarRocksCollector

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    store_filter = args.stores.split(",") if args.stores else None

    tables = args.tables.split(",") if args.tables else [
        "stores", "monthly_metrics", "store_loss",
        "cost_structure", "daily_target_cost", "switch_status",
    ]

    collector = StarRocksCollector()

    async with collector:
        for table in tables:
            logger.info(f"导出 {table}...")
            df = None

            if table == "stores":
                df = await collector.fetch_stores()
                if store_filter:
                    df = df[df["store_code"].isin(store_filter)]
            elif table == "monthly_metrics":
                df = await collector.fetch_monthly_metrics(store_codes=store_filter)
            elif table == "store_loss":
                df = await collector.fetch_store_loss(store_codes=store_filter)
            elif table == "cost_structure":
                df = await collector.fetch_cost_structure(store_codes=store_filter)
            elif table == "daily_target_cost":
                df = await collector.fetch_daily_target_cost(store_codes=store_filter)
            elif table == "switch_status":
                df = await collector.fetch_switch_status(store_codes=store_filter)
            else:
                logger.warning(f"未知表: {table}, 跳过")
                continue

            if df is not None and not df.empty:
                filename = f"{table}_{timestamp}.csv"
                filepath = output_dir / filename
                df.to_csv(filepath, index=False, encoding="utf-8-sig")
                logger.info(f"  -> {filepath} ({len(df)} 行)")
            else:
                logger.warning(f"  {table}: 无数据")

    logger.info(f"导出完成! 文件位于: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StarRocks 数据导出")
    parser.add_argument(
        "--output", type=str, default="./data/export",
        help="输出目录（默认: ./data/export）",
    )
    parser.add_argument(
        "--tables", type=str, default=None,
        help="要导出的表（逗号分隔: stores,monthly_metrics,store_loss,cost_structure,daily_target_cost,switch_status）",
    )
    parser.add_argument(
        "--stores", type=str, default=None,
        help="指定门店编码（逗号分隔）",
    )

    args = parser.parse_args()
    asyncio.run(export_data(args))
