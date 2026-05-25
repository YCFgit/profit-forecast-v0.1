"""农历工具 — 春节月判定

提供春节日期表和春节月判定功能。
用于季节指数计算和基线预估中排除春节月数据。
"""

from dataclasses import dataclass


# 春节日期表（可扩展）
# 格式：{年份: (月, 日)}
SPRING_FESTIVAL_DATES: dict[int, tuple[int, int]] = {
    2020: (1, 25),
    2021: (2, 12),
    2022: (2, 1),
    2023: (1, 22),
    2024: (2, 10),
    2025: (1, 29),
    2026: (2, 17),
    2027: (2, 6),
    2028: (1, 26),
    2029: (2, 13),
    2030: (2, 3),
}


@dataclass
class SpringFestivalInfo:
    """春节信息"""
    year: int
    month: int
    day: int
    is_spring_festival_month: bool  # 指定月份是否为春节月
    affected_months: list[int]      # 受春节影响的月份（春节月 ± 1）


class LunarCalendar:
    """农历工具类

    使用方式：
        cal = LunarCalendar()
        cal.is_spring_festival_month(2025, 1)  # True（2025春节在1月29日）
    """

    def __init__(self, dates: dict[int, tuple[int, int]] | None = None):
        self._dates = dates or SPRING_FESTIVAL_DATES

    def get_spring_festival(self, year: int) -> tuple[int, int] | None:
        """获取指定年份的春节日期 (月, 日)

        Args:
            year: 年份

        Returns:
            (月, 日) 元组，如果该年份没有数据则返回 None
        """
        return self._dates.get(year)

    def is_spring_festival_month(self, year: int, month: int) -> bool:
        """判断指定年月是否为春节月

        春节月 = 春节所在月份

        Args:
            year: 年份
            month: 月份 (1-12)

        Returns:
            是否为春节月
        """
        sf = self.get_spring_festival(year)
        if sf is None:
            return False
        return sf[0] == month

    def get_affected_months(self, year: int) -> list[int]:
        """获取受春节影响的月份列表

        受影响月份 = 春节月及其前后各1个月（去重、排序）

        Args:
            year: 年份

        Returns:
            受影响的月份列表（已排序）
        """
        sf = self.get_spring_festival(year)
        if sf is None:
            return []

        sf_month = sf[0]
        months = set()
        for offset in (-1, 0, 1):
            m = sf_month + offset
            if 1 <= m <= 12:
                months.add(m)
        return sorted(months)

    def get_info(self, year: int, month: int) -> SpringFestivalInfo:
        """获取春节信息

        Args:
            year: 年份
            month: 月份

        Returns:
            SpringFestivalInfo
        """
        sf = self.get_spring_festival(year)
        if sf is None:
            return SpringFestivalInfo(
                year=year,
                month=month,
                day=0,
                is_spring_festival_month=False,
                affected_months=[],
            )
        return SpringFestivalInfo(
            year=year,
            month=sf[0],
            day=sf[1],
            is_spring_festival_month=(sf[0] == month),
            affected_months=self.get_affected_months(year),
        )

    def filter_non_spring_months(
        self,
        year_months: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """过滤掉春节月

        Args:
            year_months: [(年, 月), ...] 列表

        Returns:
            去除春节月后的列表
        """
        return [
            (y, m) for y, m in year_months
            if not self.is_spring_festival_month(y, m)
        ]

    def is_spring_festival_date(self, year: int, month: int, day: int) -> bool:
        """判断指定日期是否为春节当天

        Args:
            year: 年份
            month: 月份
            day: 日

        Returns:
            是否为春节当天
        """
        sf = self.get_spring_festival(year)
        if sf is None:
            return False
        return sf[0] == month and sf[1] == day
