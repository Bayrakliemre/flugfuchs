"""Server-side filtering applied to confirmed Amadeus offers before they become
Deal records. Client-side JS in the dashboard re-exposes some of these as live
toggles, but the daily email/dashboard content is always pre-filtered here."""
from __future__ import annotations

from date_windows import spans_full_weekend
from dealmodel import Deal


def is_sunny(country_code: str, sunny_countries: list[str]) -> bool:
    return country_code.strip().upper() in {c.upper() for c in sunny_countries}


def passes_filters(deal: Deal, config: dict) -> bool:
    filters = config["filters"]
    if filters["nonstop_only"] and deal.stops != 0:
        return False
    if deal.duration_minutes > filters["max_flight_duration_hours"] * 60:
        return False
    if deal.currency != "EUR":
        return False
    if deal.price > filters["max_price_eur"]:
        return False
    if deal.vacation_days_count > filters["max_vacation_days"]:
        return False
    if not spans_full_weekend(deal.depart_date, deal.return_date):
        return False
    return True


def dedup_keep_cheapest(deals: list[Deal]) -> list[Deal]:
    best: dict[tuple, Deal] = {}
    for deal in deals:
        key = deal.dedup_key()
        existing = best.get(key)
        if existing is None or deal.price < existing.price:
            best[key] = deal
    return list(best.values())


def apply_all(deals: list[Deal], config: dict) -> list[Deal]:
    filtered = [d for d in deals if passes_filters(d, config)]
    return dedup_keep_cheapest(filtered)
