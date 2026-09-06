"""Sorting and highlighted-picks selection: 'Die Perlen' (weekend gems),
'Brückentage' (bridge-day opportunities) and 'Langtrips' (long-trip picks).
"""
from __future__ import annotations

from date_windows import CATEGORY_0, CATEGORY_1, CATEGORY_FLEX, CATEGORY_LONG
from dealmodel import Deal


def sort_by_price(deals: list[Deal]) -> list[Deal]:
    return sorted(deals, key=lambda d: d.price)


def _pick_cheapest_varied(by_price: list[Deal], count: int) -> list[Deal]:
    """Cheapest-first pick that skips destinations already chosen, so a top
    row shows variety instead of 4 cards for the same city."""
    picked: list[Deal] = []
    picked_destinations: set[str] = set()
    for deal in by_price:
        if deal.destination_iata not in picked_destinations:
            picked.append(deal)
            picked_destinations.add(deal.destination_iata)
        if len(picked) >= count:
            break
    return picked


def select_perlen(deals: list[Deal], count: int = 4) -> list[Deal]:
    """'Die Perlen': real-weekend gems (categories 0/1/Flex only -- long trips
    get their own section). Picks one cheapest deal per category (Flex, 0, 1
    priority -- Flex often has the deepest discounts), then backfills with
    the next-cheapest unpicked destinations."""
    weekend_deals = [d for d in deals if d.vacation_days_category != CATEGORY_LONG]
    by_price = sort_by_price(weekend_deals)
    picked: list[Deal] = []
    picked_destinations: set[str] = set()

    for category in (CATEGORY_FLEX, CATEGORY_0, CATEGORY_1):
        for deal in by_price:
            if deal.vacation_days_category == category and deal.destination_iata not in picked_destinations:
                picked.append(deal)
                picked_destinations.add(deal.destination_iata)
                break
        if len(picked) >= count:
            break

    if len(picked) < count:
        remaining = [d for d in by_price if d.destination_iata not in picked_destinations]
        picked.extend(_pick_cheapest_varied(remaining, count - len(picked)))

    return sort_by_price(picked)[:count]


def select_bridge_days(deals: list[Deal], count: int = 4) -> list[Deal]:
    """Cheapest deals that use a public holiday to cut their vacation-day
    cost, across any trip-length category -- the automatic 'use fewer
    vacation days' suggestion."""
    bridge_deals = sort_by_price([d for d in deals if d.has_bridge_day])
    return _pick_cheapest_varied(bridge_deals, count)


def select_long_trips(deals: list[Deal], count: int = 4) -> list[Deal]:
    """Cheapest picks for longer (e.g. ~2 week) trips."""
    long_deals = sort_by_price([d for d in deals if d.vacation_days_category == CATEGORY_LONG])
    return _pick_cheapest_varied(long_deals, count)
