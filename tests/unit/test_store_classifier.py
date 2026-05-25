"""门店分类器单元测试"""

import pandas as pd
import pytest

from src.forecasting.rules.store_classifier import (
    StoreCategory,
    StoreClassification,
    ClassificationResult,
    StoreClassifier,
)


@pytest.fixture
def stores_df():
    """测试门店数据"""
    return pd.DataFrame([
        {"store_code": "ST0001", "store_name": "大中店A", "brand": "品牌A", "region": "华东",
         "is_virtual": False, "is_temporary": False, "opening_date": "2020-01-01",
         "planned_closing_date": None},
        {"store_code": "ST0002", "store_name": "小店B", "brand": "品牌A", "region": "华东",
         "is_virtual": False, "is_temporary": False, "opening_date": "2020-06-01",
         "planned_closing_date": None},
        {"store_code": "ST0003", "store_name": "新店C", "brand": "品牌B", "region": "华南",
         "is_virtual": False, "is_temporary": False, "opening_date": "2025-06-01",
         "planned_closing_date": None},
        {"store_code": "ST0004", "store_name": "虚拟店D", "brand": "品牌B", "region": "华南",
         "is_virtual": True, "is_temporary": False, "opening_date": "2020-01-01",
         "planned_closing_date": None},
        {"store_code": "ST0005", "store_name": "临时店E", "brand": "品牌C", "region": "华北",
         "is_virtual": False, "is_temporary": True, "opening_date": "2024-01-01",
         "planned_closing_date": None},
        {"store_code": "ST0006", "store_name": "关店F", "brand": "品牌C", "region": "华北",
         "is_virtual": False, "is_temporary": False, "opening_date": "2020-01-01",
         "planned_closing_date": "2025-03-01"},
    ])


@pytest.fixture
def monthly_metrics_df():
    """测试月度指标数据（生成 12 个月）"""
    rows = []
    for code, base_sales in [
        ("ST0001", 500_000),  # 大中店：月均 50 万
        ("ST0002", 15_000),   # 小店：月均 1.5 万
        ("ST0003", 200_000),  # 新店
        ("ST0004", 100_000),  # 虚拟店
        ("ST0005", 80_000),   # 临时店
        ("ST0006", 300_000),  # 关店
    ]:
        for month_offset in range(12):
            year = 2025
            month = month_offset + 1
            # 简单波动
            sales = base_sales * (1 + (month_offset % 3 - 1) * 0.1)
            rows.append({
                "store_code": code,
                "year_month": f"{year}-{month:02d}",
                "sales_amount": sales,
            })
    return pd.DataFrame(rows)


class TestStoreClassifier:
    """门店分类器测试"""

    def test_classify_all_categories(self, stores_df, monthly_metrics_df):
        """测试所有分类"""
        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, monthly_metrics_df,
            target_year=2026, target_month=3,
        )

        assert isinstance(result, ClassificationResult)
        assert len(result.classifications) == 6

        # 验证分类
        cats = {c.category for c in result.classifications.values()}
        assert StoreCategory.LARGE_MEDIUM in cats
        assert StoreCategory.SMALL in cats
        assert StoreCategory.NEW in cats
        assert StoreCategory.VIRTUAL in cats
        assert StoreCategory.TEMPORARY in cats
        assert StoreCategory.CLOSING in cats

    def test_classify_summary(self, stores_df, monthly_metrics_df):
        """测试分类汇总"""
        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, monthly_metrics_df,
            target_year=2026, target_month=3,
        )

        assert result.summary[StoreCategory.VIRTUAL] == 1
        assert result.summary[StoreCategory.TEMPORARY] == 1

    def test_large_store_threshold(self, stores_df, monthly_metrics_df):
        """大中店门槛测试"""
        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, monthly_metrics_df,
            target_year=2026, target_month=3,
        )

        st0001 = result.classifications["ST0001"]
        assert st0001.category == StoreCategory.LARGE_MEDIUM
        assert st0001.avg_monthly_sales >= StoreClassifier.LARGE_STORE_MIN_AVG_SALES

    def test_small_store(self, stores_df, monthly_metrics_df):
        """小店分类测试"""
        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, monthly_metrics_df,
            target_year=2026, target_month=3,
        )

        st0002 = result.classifications["ST0002"]
        assert st0002.category == StoreCategory.SMALL
        assert st0002.avg_monthly_sales < StoreClassifier.LARGE_STORE_MIN_AVG_SALES

    def test_new_store(self, stores_df, monthly_metrics_df):
        """新店分类测试"""
        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, monthly_metrics_df,
            target_year=2026, target_month=3,
        )

        st0003 = result.classifications["ST0003"]
        assert st0003.category == StoreCategory.NEW

    def test_virtual_store(self, stores_df, monthly_metrics_df):
        """虚拟店分类测试"""
        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, monthly_metrics_df,
            target_year=2026, target_month=3,
        )

        st0004 = result.classifications["ST0004"]
        assert st0004.category == StoreCategory.VIRTUAL

    def test_temporary_store(self, stores_df, monthly_metrics_df):
        """临时特卖店分类测试"""
        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, monthly_metrics_df,
            target_year=2026, target_month=3,
        )

        st0005 = result.classifications["ST0005"]
        assert st0005.category == StoreCategory.TEMPORARY

    def test_closing_store(self, stores_df, monthly_metrics_df):
        """关店分类测试"""
        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, monthly_metrics_df,
            target_year=2026, target_month=3,
        )

        st0006 = result.classifications["ST0006"]
        assert st0006.category == StoreCategory.CLOSING

    def test_closing_by_switch_status(self, stores_df, monthly_metrics_df):
        """通过开关状态矩阵判定关店"""
        switch_df = pd.DataFrame([
            {"store_code": "ST0001", "year_month": "2026-03", "status": "off"},
        ])

        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, monthly_metrics_df,
            target_year=2026, target_month=3,
            switch_status_df=switch_df,
        )

        st0001 = result.classifications["ST0001"]
        assert st0001.category == StoreCategory.CLOSING
        assert "开关状态" in st0001.reason

    def test_priority_order(self):
        """分类优先级：临时 > 虚拟 > 新店 > 大中 > 小店"""
        # 同时满足多个条件的门店
        stores_df = pd.DataFrame([
            {"store_code": "ST0001", "store_name": "测试店", "brand": "品牌A", "region": "华东",
             "is_virtual": True, "is_temporary": True, "opening_date": "2025-06-01",
             "planned_closing_date": None},
        ])
        monthly_metrics_df = pd.DataFrame([
            {"store_code": "ST0001", "year_month": "2025-01", "sales_amount": 500_000},
            {"store_code": "ST0001", "year_month": "2025-02", "sales_amount": 500_000},
            {"store_code": "ST0001", "year_month": "2025-03", "sales_amount": 500_000},
        ])

        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, monthly_metrics_df,
            target_year=2026, target_month=3,
        )

        # 临时特卖店优先于虚拟店
        assert result.classifications["ST0001"].category == StoreCategory.TEMPORARY

    def test_custom_cutoff_date(self, stores_df, monthly_metrics_df):
        """自定义新店截止日期"""
        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, monthly_metrics_df,
            target_year=2026, target_month=3,
            new_store_cutoff="2026-01-01",
        )

        # ST0003 开业日期 2025-06-01，在 2026-01-01 之前，不算新店
        st0003 = result.classifications["ST0003"]
        assert st0003.category != StoreCategory.NEW

    def test_empty_metrics(self, stores_df):
        """空月度指标"""
        classifier = StoreClassifier()
        result = classifier.classify(
            stores_df, pd.DataFrame(),
            target_year=2026, target_month=3,
        )

        # 无业绩数据时：特殊分类不变，普通门店为小店
        for code, cls in result.classifications.items():
            if cls.category in (
                StoreCategory.VIRTUAL, StoreCategory.TEMPORARY,
                StoreCategory.CLOSING, StoreCategory.NEW,
            ):
                continue  # 这些分类不依赖业绩数据
            assert cls.category == StoreCategory.SMALL
