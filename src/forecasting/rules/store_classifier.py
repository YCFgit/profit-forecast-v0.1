"""门店 6 分类器

将门店分为 6 类：大中店、小店、新店、虚拟店、临时特卖店、关店。
分类优先级（从高到低）：关店 → 临时特卖店 → 虚拟店 → 新店 → 大中店 → 小店。
"""

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class StoreCategory(Enum):
    """门店分类"""
    LARGE_MEDIUM = "large_medium"    # 大中店
    SMALL = "small"                  # 小店
    NEW = "new"                      # 新店
    VIRTUAL = "virtual"              # 虚拟店
    TEMPORARY = "temporary"          # 临时特卖店
    CLOSING = "closing"              # 关店


@dataclass
class StoreClassification:
    """单店分类结果"""
    store_code: str
    category: StoreCategory
    brand: str
    region: str
    avg_monthly_sales: float
    valid_months: int
    opening_date: str | None = None
    closing_date: str | None = None
    reason: str = ""


@dataclass
class ClassificationResult:
    """分类汇总结果"""
    classifications: dict[str, StoreClassification]
    summary: dict[StoreCategory, int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.summary:
            self.summary = {}
            for cat in StoreCategory:
                count = sum(
                    1 for c in self.classifications.values()
                    if c.category == cat
                )
                if count > 0:
                    self.summary[cat] = count


class StoreClassifier:
    """门店分类器

    分类规则：
    1. 关店：开关状态矩阵中预估月标记为关闭，或 closing_date 在预估月内
    2. 临时特卖店：is_temporary = True
    3. 虚拟店：is_virtual = True
    4. 新店：opening_date 在去年1月1日之后
    5. 大中店：近6个非春节月中，有效月份 ≥ 3 且 月均业绩 ≥ 3万
    6. 小店：不满足大中店条件的正常营业门店

    使用方式：
        classifier = StoreClassifier(lunar_calendar)
        result = classifier.classify(stores_df, monthly_metrics_df, target_month)
    """

    # 大中店门槛
    LARGE_STORE_MIN_MONTHS = 3       # 最少有效月份
    LARGE_STORE_MIN_AVG_SALES = 30_000  # 月均业绩门槛（元）
    LARGE_STORE_LOOKBACK = 6         # 回溯月数

    # 新店判定：opening_date 在此日期之后视为新店
    # 默认为去年1月1日，可在 classify() 中通过参数覆盖

    def __init__(self, lunar_calendar=None):
        from src.forecasting.rules.lunar_calendar import LunarCalendar
        self._lunar = lunar_calendar or LunarCalendar()

    def classify(
        self,
        stores_df: pd.DataFrame,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        switch_status_df: pd.DataFrame | None = None,
        new_store_cutoff: str | None = None,
    ) -> ClassificationResult:
        """对所有门店进行分类

        Args:
            stores_df: 门店主数据 DataFrame
                必需列：store_code, store_name, brand, region
                可选列：is_virtual, is_temporary, opening_date, planned_closing_date
            monthly_metrics_df: 月度指标 DataFrame
                必需列：store_code, year_month, sales_amount
            target_year: 预估年份
            target_month: 预估月份
            switch_status_df: 开关状态矩阵 DataFrame（可选）
                列：store_code, year_month, status ("on"/"off")
            new_store_cutoff: 新店截止日期（字符串，如 "2025-01-01"）

        Returns:
            ClassificationResult
        """
        if new_store_cutoff is None:
            new_store_cutoff = f"{target_year - 1}-01-01"
        cutoff_date = pd.Timestamp(new_store_cutoff)

        # 构建目标月字符串
        target_ym = f"{target_year}-{target_month:02d}"

        # 构建开关状态查询
        switch_map = self._build_switch_map(switch_status_df, target_ym)

        # 标准化字段（兼容 StarRocks 和 Mock 两种数据源）
        stores_df = self._normalize_store_fields(stores_df)

        classifications = {}

        for _, store in stores_df.iterrows():
            code = store["store_code"]
            brand = store.get("brand", "unknown")
            region = store.get("region", "unknown")

            # 获取该门店的月度数据
            if monthly_metrics_df.empty or "store_code" not in monthly_metrics_df.columns:
                store_metrics = pd.DataFrame()
            else:
                store_metrics = monthly_metrics_df[
                    monthly_metrics_df["store_code"] == code
                ]

            # 计算近6个非春节月的统计数据
            avg_sales, valid_months = self._calc_recent_stats(
                store_metrics, target_year, target_month
            )

            # 按优先级分类
            category, reason = self._classify_single(
                store=store,
                store_code=code,
                avg_sales=avg_sales,
                valid_months=valid_months,
                switch_map=switch_map,
                cutoff_date=cutoff_date,
                target_year=target_year,
                target_month=target_month,
            )

            classifications[code] = StoreClassification(
                store_code=code,
                category=category,
                brand=brand,
                region=region,
                avg_monthly_sales=avg_sales,
                valid_months=valid_months,
                opening_date=str(store.get("opening_date", "")) if store.get("opening_date") else None,
                closing_date=str(store.get("planned_closing_date", "")) if store.get("planned_closing_date") else None,
                reason=reason,
            )

        return ClassificationResult(classifications=classifications)

    def _classify_single(
        self,
        store: pd.Series,
        store_code: str,
        avg_sales: float,
        valid_months: int,
        switch_map: dict[str, str],
        cutoff_date: pd.Timestamp,
        target_year: int,
        target_month: int,
    ) -> tuple[StoreCategory, str]:
        """对单个门店进行分类（按优先级）"""

        # 1. 关店
        if switch_map.get(store_code) == "off":
            return StoreCategory.CLOSING, "开关状态为关闭"

        closing_date = store.get("planned_closing_date")
        if closing_date and pd.notna(closing_date):
            closing_ts = pd.Timestamp(closing_date)
            target_ts = pd.Timestamp(target_year, target_month, 1)
            # 关闭日期在目标月之前或当月
            if closing_ts <= target_ts:
                return StoreCategory.CLOSING, f"计划关店日期 {closing_date}"

        # 2. 临时特卖店
        if store.get("is_temporary", False):
            return StoreCategory.TEMPORARY, "临时特卖店标记"

        # 3. 虚拟店
        if store.get("is_virtual", False):
            return StoreCategory.VIRTUAL, "虚拟店标记"

        # 4. 新店
        opening_date = store.get("opening_date")
        if opening_date and pd.notna(opening_date):
            opening_ts = pd.Timestamp(opening_date)
            if opening_ts >= cutoff_date:
                return StoreCategory.NEW, f"开业日期 {opening_date} 在截止日之后"

        # 5. 大中店
        if (valid_months >= self.LARGE_STORE_MIN_MONTHS
                and avg_sales >= self.LARGE_STORE_MIN_AVG_SALES):
            return (
                StoreCategory.LARGE_MEDIUM,
                f"近{valid_months}月月均 {avg_sales:,.0f} >= {self.LARGE_STORE_MIN_AVG_SALES:,.0f}",
            )

        # 6. 小店（默认）
        return StoreCategory.SMALL, f"不满足大中店条件（{valid_months}月, 月均{avg_sales:,.0f}）"

    def _calc_recent_stats(
        self,
        store_metrics: pd.DataFrame,
        target_year: int,
        target_month: int,
    ) -> tuple[float, int]:
        """计算近 N 个非春节月的月均业绩和有效月数

        Returns:
            (月均业绩, 有效月数)
        """
        if store_metrics.empty:
            return 0.0, 0

        # 生成近 N 个月的年月列表
        recent_months = []
        y, m = target_year, target_month
        for _ in range(self.LARGE_STORE_LOOKBACK):
            m -= 1
            if m < 1:
                m = 12
                y -= 1
            recent_months.append((y, m))

        # 排除春节月
        non_spring = self._lunar.filter_non_spring_months(recent_months)

        # 提取这些月的数据
        sales_values = []
        for yr, mo in non_spring:
            ym_str = f"{yr}-{mo:02d}"
            row = store_metrics[store_metrics["year_month"] == ym_str]
            if not row.empty and "sales_amount" in row.columns:
                val = row["sales_amount"].iloc[0]
                if pd.notna(val) and val > 0:
                    sales_values.append(float(val))

        valid_months = len(sales_values)
        avg_sales = sum(sales_values) / valid_months if valid_months > 0 else 0.0

        return avg_sales, valid_months

    def _build_switch_map(
        self,
        switch_status_df: pd.DataFrame | None,
        target_ym: str,
    ) -> dict[str, str]:
        """构建门店开关状态映射

        Returns:
            {store_code: "on"/"off"}
        """
        if switch_status_df is None or switch_status_df.empty:
            return {}

        target_rows = switch_status_df[
            switch_status_df["year_month"] == target_ym
        ]
        return dict(zip(target_rows["store_code"], target_rows["status"]))

    @staticmethod
    def _normalize_store_fields(stores_df: pd.DataFrame) -> pd.DataFrame:
        """标准化门店字段，兼容 StarRocks 和 Mock 两种数据源

        StarRocks 返回: virtual_shop_type, store_type_flag
        Mock 返回: is_virtual, is_temporary
        统一映射为: is_virtual, is_temporary
        """
        df = stores_df.copy()

        # virtual_shop_type → is_virtual（非空 = 虚拟店）
        if "is_virtual" not in df.columns and "virtual_shop_type" in df.columns:
            df["is_virtual"] = df["virtual_shop_type"].apply(
                lambda x: pd.notna(x) and str(x).strip() != ""
            )

        # store_type_flag → is_temporary（包含"特卖"或"临时" = 临时店）
        if "is_temporary" not in df.columns and "store_type_flag" in df.columns:
            df["is_temporary"] = df["store_type_flag"].apply(
                lambda x: "特卖" in str(x) or "临时" in str(x) if pd.notna(x) else False
            )

        # 兼容 planned_closing_date（StarRocks 用 closing_date）
        if "planned_closing_date" not in df.columns and "closing_date" in df.columns:
            df["planned_closing_date"] = df["closing_date"]

        return df
