"""The Deal data model, plus small self-contained helpers (flag emoji, German
date formatting, Skyscanner deep-link URLs) that don't warrant their own module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone

_WEEKDAY_DE = {0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So"}
_MONTH_DE = {
    1: "Jan", 2: "Feb", 3: "Mär", 4: "Apr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dez",
}


def format_german_date(d: date) -> str:
    return f"{_WEEKDAY_DE[d.weekday()]} {d.day}. {_MONTH_DE[d.month]}."


def format_german_date_range(depart: date, return_: date) -> str:
    """e.g. 'Sa 10. – Mo 12. Okt.' -- month only shown once, on the return date,
    matching the screenshot; if months differ, show both in full."""
    if depart.month == return_.month:
        return (
            f"{_WEEKDAY_DE[depart.weekday()]} {depart.day}. – "
            f"{_WEEKDAY_DE[return_.weekday()]} {return_.day}. {_MONTH_DE[return_.month]}."
        )
    return f"{format_german_date(depart)} – {format_german_date(return_)}"


def flag_emoji(country_code: str) -> str:
    """ISO 3166-1 alpha-2 -> flag emoji via the Unicode regional-indicator trick."""
    code = country_code.strip().upper()
    if len(code) != 2 or not code.isalpha():
        return "🏳️"
    return "".join(chr(0x1F1E6 + (ord(c) - ord("A"))) for c in code)


def build_skyscanner_url(origin: str, destination: str, depart: date, return_: date) -> str:
    """Skyscanner's browse-URL pattern: lowercase IATA codes, dates as YYMMDD.
    Isolated here as a single point of maintenance if the format ever changes."""
    fmt = "%y%m%d"
    return (
        f"https://www.skyscanner.de/transport/fluge/"
        f"{origin.lower()}/{destination.lower()}/"
        f"{depart.strftime(fmt)}/{return_.strftime(fmt)}/"
    )


@dataclass
class Deal:
    origin_iata: str
    destination_iata: str
    destination_city: str
    destination_country: str
    country_code: str
    price: float
    currency: str
    depart_date: date
    return_date: date
    trip_length_days: int
    vacation_days_category: str  # "0" | "1" | "flex"
    vacation_days_count: int
    duration_minutes: int
    stops: int
    is_sunny: bool
    holidays_used: list[date]
    fetched_at: datetime

    @property
    def has_bridge_day(self) -> bool:
        return len(self.holidays_used) > 0

    @property
    def skyscanner_url(self) -> str:
        return build_skyscanner_url(
            self.origin_iata, self.destination_iata, self.depart_date, self.return_date
        )

    @property
    def flag(self) -> str:
        return flag_emoji(self.country_code)

    @property
    def date_range_label(self) -> str:
        return format_german_date_range(self.depart_date, self.return_date)

    @property
    def duration_label(self) -> str:
        h, m = divmod(self.duration_minutes, 60)
        return f"{h}:{m:02d} h"

    def dedup_key(self) -> tuple:
        return (self.origin_iata, self.destination_iata, self.depart_date, self.return_date)

    def to_json_dict(self) -> dict:
        d = asdict(self)
        d["depart_date"] = self.depart_date.isoformat()
        d["return_date"] = self.return_date.isoformat()
        d["holidays_used"] = [h.isoformat() for h in self.holidays_used]
        d["fetched_at"] = self.fetched_at.isoformat()
        d["skyscanner_url"] = self.skyscanner_url
        d["flag"] = self.flag
        d["date_range_label"] = self.date_range_label
        d["duration_label"] = self.duration_label
        d["has_bridge_day"] = self.has_bridge_day
        return d

    @staticmethod
    def from_json_dict(d: dict) -> "Deal":
        return Deal(
            origin_iata=d["origin_iata"],
            destination_iata=d["destination_iata"],
            destination_city=d["destination_city"],
            destination_country=d["destination_country"],
            country_code=d["country_code"],
            price=d["price"],
            currency=d["currency"],
            depart_date=date.fromisoformat(d["depart_date"]),
            return_date=date.fromisoformat(d["return_date"]),
            trip_length_days=d["trip_length_days"],
            vacation_days_category=d["vacation_days_category"],
            vacation_days_count=d["vacation_days_count"],
            duration_minutes=d["duration_minutes"],
            stops=d["stops"],
            is_sunny=d["is_sunny"],
            holidays_used=[date.fromisoformat(h) for h in d.get("holidays_used", [])],
            fetched_at=datetime.fromisoformat(d["fetched_at"]),
        )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
