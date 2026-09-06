"""Statutory public holidays for North Rhine-Westphalia (NRW), computed
locally -- no external API/dependency needed. Moveable feasts are derived
from the Gauss/Meeus algorithm for the date of Easter Sunday.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache


@lru_cache(maxsize=None)
def easter_sunday(year: int) -> date:
    """Meeus/Jones/Butcher Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


@lru_cache(maxsize=None)
def nrw_holidays(year: int) -> frozenset[date]:
    """All 12 statutory public holidays observed in NRW for `year`."""
    easter = easter_sunday(year)
    return frozenset({
        date(year, 1, 1),                    # Neujahr
        easter - timedelta(days=2),           # Karfreitag
        easter + timedelta(days=1),           # Ostermontag
        date(year, 5, 1),                     # Tag der Arbeit
        easter + timedelta(days=39),          # Christi Himmelfahrt
        easter + timedelta(days=50),          # Pfingstmontag
        easter + timedelta(days=60),          # Fronleichnam
        date(year, 10, 3),                    # Tag der Deutschen Einheit
        date(year, 10, 31),                   # Reformationstag (NRW seit 2018)
        date(year, 11, 1),                    # Allerheiligen
        date(year, 12, 25),                   # 1. Weihnachtsfeiertag
        date(year, 12, 26),                   # 2. Weihnachtsfeiertag
    })


def holidays_in_range(start: date, end: date) -> frozenset[date]:
    """All NRW holidays falling within [start, end], across a year boundary."""
    holidays: set[date] = set()
    for year in range(start.year, end.year + 1):
        holidays |= nrw_holidays(year)
    return frozenset(d for d in holidays if start <= d <= end)
