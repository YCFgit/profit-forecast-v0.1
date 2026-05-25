"""农历工具单元测试"""

import pytest

from src.forecasting.rules.lunar_calendar import (
    LunarCalendar,
    SPRING_FESTIVAL_DATES,
    SpringFestivalInfo,
)


class TestLunarCalendar:
    """春节月判定测试"""

    def test_get_spring_festival(self):
        """获取春节日期"""
        cal = LunarCalendar()
        assert cal.get_spring_festival(2024) == (2, 10)
        assert cal.get_spring_festival(2025) == (1, 29)
        assert cal.get_spring_festival(2026) == (2, 17)

    def test_get_spring_festival_missing_year(self):
        """缺失年份返回 None"""
        cal = LunarCalendar()
        assert cal.get_spring_festival(2019) is None

    def test_is_spring_festival_month(self):
        """春节月判定"""
        cal = LunarCalendar()
        # 2025年春节在1月29日
        assert cal.is_spring_festival_month(2025, 1) is True
        assert cal.is_spring_festival_month(2025, 2) is False
        # 2024年春节在2月10日
        assert cal.is_spring_festival_month(2024, 2) is True
        assert cal.is_spring_festival_month(2024, 1) is False

    def test_is_spring_festival_month_missing_year(self):
        """缺失年份返回 False"""
        cal = LunarCalendar()
        assert cal.is_spring_festival_month(2019, 1) is False

    def test_get_affected_months(self):
        """受影响月份列表"""
        cal = LunarCalendar()
        # 2025年春节在1月 → 受影响月份：1月（春节月没有0月）
        affected = cal.get_affected_months(2025)
        assert 1 in affected
        assert 2 in affected
        # 2024年春节在2月 → 受影响月份：1, 2, 3
        affected = cal.get_affected_months(2024)
        assert affected == [1, 2, 3]

    def test_get_affected_months_missing_year(self):
        """缺失年份返回空列表"""
        cal = LunarCalendar()
        assert cal.get_affected_months(2019) == []

    def test_get_info(self):
        """获取春节信息"""
        cal = LunarCalendar()
        info = cal.get_info(2025, 1)
        assert info.year == 2025
        assert info.month == 1
        assert info.day == 29
        assert info.is_spring_festival_month is True
        assert isinstance(info.affected_months, list)

    def test_filter_non_spring_months(self):
        """过滤春节月"""
        cal = LunarCalendar()
        months = [(2025, 1), (2025, 2), (2025, 3), (2024, 2)]
        result = cal.filter_non_spring_months(months)
        # 2025-1 是春节月，2024-2 是春节月
        assert (2025, 1) not in result
        assert (2025, 2) in result
        assert (2025, 3) in result
        assert (2024, 2) not in result

    def test_filter_non_spring_months_empty(self):
        """空列表过滤"""
        cal = LunarCalendar()
        assert cal.filter_non_spring_months([]) == []

    def test_is_spring_festival_date(self):
        """春节当天判定"""
        cal = LunarCalendar()
        assert cal.is_spring_festival_date(2025, 1, 29) is True
        assert cal.is_spring_festival_date(2025, 1, 28) is False
        assert cal.is_spring_festival_date(2024, 2, 10) is True

    def test_custom_dates(self):
        """自定义春节日期表"""
        custom = {2030: (2, 3)}
        cal = LunarCalendar(dates=custom)
        assert cal.is_spring_festival_month(2030, 2) is True
        assert cal.is_spring_festival_month(2025, 1) is False
