"""Thin wrapper around the free Travelpayouts / Aviasales Data API
(/v3/prices_for_dates). Requires only a free affiliate-registration API
token (no MAU/traffic minimum, unlike Travelpayouts' real-time Search API).
Rate limit for this endpoint is 600 requests/minute (no monthly quota) --
comfortably covers one call per home airport per day. Adds retry/backoff and
a per-day on-disk cache so re-running main.py the same day costs nothing.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_PRICES_FOR_DATES_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class TravelpayoutsError(Exception):
    pass


class TravelpayoutsClient:
    def __init__(self, api_token: str, cache_dir: str | Path | None = None, max_retries: int = 3):
        if not api_token:
            raise TravelpayoutsError("TRAVELPAYOUTS_API_TOKEN must be set")
        self.api_token = api_token
        self.max_retries = max_retries
        self.cache_dir = Path(cache_dir) if cache_dir else None

    # -- caching --------------------------------------------------------

    def _cache_path(self, params: dict) -> Path | None:
        if self.cache_dir is None:
            return None
        today = date.today().isoformat()
        key_raw = json.dumps(params, sort_keys=True)
        key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()[:24]
        day_dir = self.cache_dir / today
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir / f"{key}.json"

    def _cached_get(self, params: dict) -> dict | None:
        cache_path = self._cache_path(params)
        if cache_path and cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _write_cache(self, params: dict, payload: dict) -> None:
        cache_path = self._cache_path(params)
        if cache_path:
            cache_path.write_text(json.dumps(payload), encoding="utf-8")

    # -- HTTP with retry --------------------------------------------------

    def _get(self, params: dict) -> dict:
        cached = self._cached_get(params)
        if cached is not None:
            return cached

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.get(_PRICES_FOR_DATES_URL, params=params, timeout=20)
            except requests.RequestException as exc:
                last_error = exc
                logger.warning("Travelpayouts request error (attempt %d): %s", attempt, exc)
                time.sleep(2 ** attempt)
                continue

            if resp.status_code == 200:
                payload = resp.json()
                if not payload.get("success", False):
                    raise TravelpayoutsError(f"Travelpayouts returned success=false: {payload}")
                self._write_cache(params, payload)
                return payload

            if resp.status_code in _RETRYABLE_STATUS and attempt < self.max_retries:
                logger.warning(
                    "Travelpayouts returned %d (attempt %d), retrying", resp.status_code, attempt
                )
                time.sleep(2 ** attempt)
                continue

            raise TravelpayoutsError(
                f"Travelpayouts prices_for_dates failed: {resp.status_code} {resp.text[:300]}"
            )

        raise TravelpayoutsError(f"Travelpayouts prices_for_dates failed after retries: {last_error}")

    # -- endpoint ----------------------------------------------------------

    def prices_for_dates(self, origin: str, currency: str = "eur", direct: bool = True,
                          market: str = "de", limit: int = 500) -> list[dict]:
        """Cheapest round-trip fares found by Aviasales users in the cache for
        `origin`, across whatever destinations/dates have been searched. No
        destination/date filter -- classification of which dates count as a
        'weekend trip' happens client-side (date_windows.py)."""
        params = {
            "origin": origin,
            "currency": currency,
            "direct": "true" if direct else "false",
            "one_way": "false",
            "sorting": "price",
            "market": market,
            "limit": limit,
            "token": self.api_token,
        }
        payload = self._get(params)
        return payload.get("data", [])
