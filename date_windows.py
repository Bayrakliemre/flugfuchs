"""Pure, network-free date classification logic. The Aviasales Data API returns
whatever dates real users have searched (not dates we request), so instead of
generating candidate windows to query, we classify whatever date pair comes
back -- this still matches the product's "0 / 1 / Flex / Lang" vacation-day
buckets and the "real weekend" concept from the screenshots.

NRW public holidays are subtracted before counting vacation days, so a trip
that brackets a holiday (a "Brückentag") correctly needs fewer PTO days than
its calendar length would suggest -- this is what lets the tool surface
bridge-day opportunities automatically instead of just listing raw trip length.
"""
from __future__ import annotations

from datetime import date, timedelta

CATEGORY_0 = "0"
CATEGORY_1 = "1"
CATEGORY_FLEX = "flex"
CATEGORY_LONG = "long"


def vacation_days_needed(depart: date, return_: date, holidays: frozenset[date] = frozenset()) -> int:
    """Count weekdays (Mon-Fri) in [depart, return_] inclusive, excluding any
    that fall on a public holiday -- these are the actual PTO days a trip
    would consume, since weekends and holidays are already free.
    """
    if return_ < depart:
        raise ValueError("return_ date must not be before depart date")
    days_off = 0
    d = depart
    while d <= return_:
        if d.weekday() < 5 and d not in holidays:  # Mon=0 .. Fri=4, not a holiday
            days_off += 1
        d += timedelta(days=1)
    return days_off


def classify_vacation_days(count: int, long_max_days: int = 11) -> str | None:
    """Maps a vacation-day count to a UI category, or None if it's too long
    even for the 'Lang' (long-trip, e.g. ~2 weeks) bucket."""
    if count == 0:
        return CATEGORY_0
    if count == 1:
        return CATEGORY_1
    if count in (2, 3):
        return CATEGORY_FLEX
    if count <= long_max_days:
        return CATEGORY_LONG
    return None


def spans_full_weekend(depart: date, return_: date) -> bool:
    """True if [depart, return_] contains at least one Saturday immediately
    followed by a Sunday -- i.e. it's an actual weekend trip, not just any
    short midweek hop that happens to use few vacation days."""
    d = depart
    while d <= return_:
        if d.weekday() == 5 and d + timedelta(days=1) <= return_:
            return True
        d += timedelta(days=1)
    return False


def holidays_used(depart: date, return_: date, holidays: frozenset[date]) -> list[date]:
    """Which of `holidays` (already restricted to weekdays by the caller, or
    not -- we filter here too) fall within the trip and reduce its PTO cost."""
    return sorted(h for h in holidays if depart <= h <= return_ and h.weekday() < 5)
