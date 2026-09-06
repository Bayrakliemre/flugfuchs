"""Resolves IATA codes to German city/country display names + country codes,
using Travelpayouts' free static reference dumps (no API token required):
https://api.travelpayouts.com/data/de/{airports,cities,countries}.json

These barely change, so they're downloaded once and cached on disk for
`max_age_days` (default 30) -- this is a bulk one-time download, not a
per-run API call, so it doesn't count against the daily request budget.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.travelpayouts.com/data/de/{name}.json"


class ReferenceData:
    def __init__(self, airports: list[dict], cities: list[dict], countries: list[dict]):
        self._airport_to_city = {a["code"]: a.get("city_code") for a in airports if a.get("code")}
        self._airport_to_country = {a["code"]: a.get("country_code") for a in airports if a.get("code")}
        self._city_names = {
            c["code"]: (c.get("name") or c.get("name_translations", {}).get("en") or c["code"])
            for c in cities if c.get("code")
        }
        self._city_to_country = {c["code"]: c.get("country_code") for c in cities if c.get("code")}
        self._country_names = {
            c["code"]: (c.get("name") or c.get("name_translations", {}).get("en") or c["code"])
            for c in countries if c.get("code")
        }

    def resolve(self, iata_code: str) -> tuple[str, str, str]:
        """Returns (city_name, country_name, country_code) for an airport or
        city IATA code. Falls back to the raw code if unknown."""
        city_code = self._airport_to_city.get(iata_code, iata_code)
        country_code = (
            self._airport_to_country.get(iata_code)
            or self._city_to_country.get(city_code)
            or self._city_to_country.get(iata_code)
            or "XX"
        )
        city_name = self._city_names.get(city_code, city_code)
        country_name = self._country_names.get(country_code, country_code)
        return city_name, country_name, country_code


class _StubReferenceData(ReferenceData):
    """Used when the reference dumps can't be loaded (offline, first run with
    no cache yet) -- falls back to raw IATA codes rather than crashing."""

    def __init__(self):
        pass

    def resolve(self, iata_code: str) -> tuple[str, str, str]:
        return iata_code, iata_code, "XX"


def _load_or_download(path: Path, name: str, max_age_days: int) -> list[dict]:
    if path.exists():
        age_days = (time.time() - path.stat().st_mtime) / 86400
        if age_days < max_age_days:
            return json.loads(path.read_text(encoding="utf-8"))

    resp = requests.get(_BASE_URL.format(name=name), timeout=60)
    resp.raise_for_status()
    data = resp.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def load_reference_data(cache_dir: str | Path, max_age_days: int = 30) -> ReferenceData:
    cache_dir = Path(cache_dir)
    try:
        airports = _load_or_download(cache_dir / "airports.json", "airports", max_age_days)
        cities = _load_or_download(cache_dir / "cities.json", "cities", max_age_days)
        countries = _load_or_download(cache_dir / "countries.json", "countries", max_age_days)
        return ReferenceData(airports, cities, countries)
    except (requests.RequestException, json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load Travelpayouts reference data (%s); falling back to raw IATA codes", exc)
        return _StubReferenceData()
