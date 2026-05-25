"""数据质量检查"""

import pandas as pd
from loguru import logger


class DataQualityReport:
    """数据质量检查报告"""

    def __init__(self, name: str):
        self.name = name
        self.total_rows = 0
        self.null_counts: dict[str, int] = {}
        self.duplicate_count = 0
        self.outlier_counts: dict[str, int] = {}
        self.errors: list[str] = []

    @property
    def is_clean(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [
            f"=== 数据质量报告: {self.name} ===",
            f"总行数: {self.total_rows}",
            f"重复行: {self.duplicate_count}",
        ]
        if self.null_counts:
            lines.append("空值统计:")
            for col, count in self.null_counts.items():
                if count > 0:
                    lines.append(f"  {col}: {count} ({count/self.total_rows*100:.1f}%)")
        if self.outlier_counts:
            lines.append("异常值统计:")
            for col, count in self.outlier_counts.items():
                if count > 0:
                    lines.append(f"  {col}: {count} 条")
        if self.errors:
            lines.append(f"错误: {len(self.errors)} 项")
            for err in self.errors[:10]:
                lines.append(f"  - {err}")
        return "\n".join(lines)


def check_nulls(df: pd.DataFrame, critical_cols: list[str] | None = None) -> dict[str, int]:
    """检查空值"""
    null_counts = df.isnull().sum().to_dict()
    if critical_cols:
        for col in critical_cols:
            if col in null_counts and null_counts[col] > 0:
                logger.warning(f"[质量] 关键字段 {col} 存在 {null_counts[col]} 个空值")
    return null_counts


def check_duplicates(df: pd.DataFrame, subset: list[str] | None = None) -> int:
    """检查重复数据"""
    dup_count = df.duplicated(subset=subset).sum()
    if dup_count > 0:
        logger.warning(f"[质量] 发现 {dup_count} 条重复数据")
    return dup_count


def check_value_range(
    df: pd.DataFrame,
    column: str,
    min_val: float | None = None,
    max_val: float | None = None,
) -> int:
    """检查数值范围"""
    outlier_count = 0
    if min_val is not None:
        outlier_count += (df[column] < min_val).sum()
    if max_val is not None:
        outlier_count += (df[column] > max_val).sum()
    if outlier_count > 0:
        logger.warning(f"[质量] {column} 有 {outlier_count} 条超出范围 [{min_val}, {max_val}]")
    return outlier_count


def run_quality_check(
    df: pd.DataFrame,
    name: str = "data",
    critical_cols: list[str] | None = None,
    duplicate_subset: list[str] | None = None,
) -> DataQualityReport:
    """执行完整数据质量检查"""
    report = DataQualityReport(name)
    report.total_rows = len(df)
    report.null_counts = check_nulls(df, critical_cols)
    report.duplicate_count = check_duplicates(df, duplicate_subset)

    if report.duplicate_count > 0:
        report.errors.append(f"存在 {report.duplicate_count} 条重复数据")

    for col in critical_cols or []:
        if col in report.null_counts and report.null_counts[col] > 0:
            report.errors.append(f"关键字段 {col} 存在空值")

    logger.info(f"\n{report.summary()}")
    return report
