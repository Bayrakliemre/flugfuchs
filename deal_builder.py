"""Converts raw Aviasales /v3/prices_for_dates records into Deal objects:
resolves destination city/country names, classifies the vacation-day
category (NRW-holiday-aware, so bridge days reduce the PTO cost), and
derives duration/stops/sunny flags. Records that don't parse cleanly or
don't fit a short/long-trip category are silently dropped (logged at debug
level) rather than failing the whole run.
"""
from __future__ import annotations

import logging
from datetime import datetime

from date_windows import classify_vacation_days, holidays_used as compute_holidays_used, vacation_days_needed
from dealmodel import Deal, now_utc
from filters import is_sunny
from holidays_nrw import holidays_in_range
from reference_data import ReferenceData

logger = logging.getLogger(__name__)


def build_deal(raw: dict, queried_origin: str, reference: ReferenceData,
               sunny_countries: list[str], long_max_days: int) -> Deal | None:
    return_at = raw.get("return_at")
    if not return_at:
        return None  # one-way result; we only classify round trips

    try:
        origin_iata = raw.get("origin_airport") or raw.get("origin") or queried_origin
        destination_iata = raw.get("destination_airport") or raw["destination"]
        depart_date = datetime.fromisoformat(raw["departure_at"]).date()
        return_date = datetime.fromisoformat(return_at).date()
        price = float(raw["price"])
    except (KeyError, ValueError, TypeError) as exc:
        logger.debug("Skipping malformed Aviasales record %s: %s", raw, exc)
        return None

    holidays = holidays_in_range(depart_date, return_date)
    vac_count = vacation_days_needed(depart_date, return_date, holidays)
    category = classify_vacation_days(vac_count, long_max_days)
    if category is None:
        return None

    city_name, country_name, country_code = reference.resolve(destination_iata)

    return Deal(
        origin_iata=origin_iata,
        destination_iata=destination_iata,
        destination_city=city_name,
        destination_country=country_name,
        country_code=country_code,
        price=price,
        currency="EUR",
        depart_date=depart_date,
        return_date=return_date,
        trip_length_days=(return_date - depart_date).days,
        vacation_days_category=category,
        vacation_days_count=vac_count,
        duration_minutes=int(raw.get("duration_to") or raw.get("duration") or 0),
        stops=max(int(raw.get("transfers", 0)), int(raw.get("return_transfers", 0))),
        is_sunny=is_sunny(country_code, sunny_countries),
        holidays_used=compute_holidays_used(depart_date, return_date, holidays),
        fetched_at=now_utc(),
    )


def build_deals(raw_records: list[dict], queried_origin: str, reference: ReferenceData,
                 sunny_countries: list[str], long_max_days: int = 11) -> list[Deal]:
    deals = []
    for raw in raw_records:
        deal = build_deal(raw, queried_origin, reference, sunny_countries, long_max_days)
        if deal is not None:
            deals.append(deal)
    return deals
