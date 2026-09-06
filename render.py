"""Renders the self-contained dashboard.html and the shorter email digest HTML
from the Jinja2 templates in templates/."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from dealmodel import Deal, format_german_date

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=False)


def render_dashboard(deals: list[Deal], perlen: list[Deal], bridge_days: list[Deal],
                      long_trips: list[Deal], config: dict, generated_at: datetime,
                      stale: bool = False) -> str:
    template = _env().get_template("dashboard.html.j2")
    deals_json = json.dumps([d.to_json_dict() for d in deals])
    perlen_json = json.dumps([d.to_json_dict() for d in perlen])
    bridge_days_json = json.dumps([d.to_json_dict() for d in bridge_days])
    long_trips_json = json.dumps([d.to_json_dict() for d in long_trips])

    label = format_german_date(generated_at.date())
    if stale:
        label += " — Live-Abruf fehlgeschlagen, zeige letzten erfolgreichen Stand"

    return template.render(
        product_name=config["product"]["name"],
        product_emoji=config["product"]["emoji"],
        region_label=config.get("region_label", ""),
        season_year=generated_at.year,
        generated_at_label=label,
        max_vacation_days=config["filters"]["max_vacation_days"],
        max_flight_duration_hours=config["filters"]["max_flight_duration_hours"],
        max_price_eur=config["filters"]["max_price_eur"],
        primary_airports=config["airports"]["primary"],
        secondary_airports=config["airports"]["secondary"],
        deal_count=len(deals),
        cheapest_price=round(min((d.price for d in deals), default=0)),
        avg_price=round(sum(d.price for d in deals) / len(deals)) if deals else 0,
        deals_json=deals_json,
        perlen_json=perlen_json,
        bridge_days_json=bridge_days_json,
        long_trips_json=long_trips_json,
    )


def render_email_digest(perlen: list[Deal], deal_count: int, generated_at: datetime,
                         config: dict, stale: bool = False) -> str:
    template = _env().get_template("email_digest.html.j2")
    label = format_german_date(generated_at.date())
    if stale:
        label += " — Live-Abruf fehlgeschlagen, zeige letzten erfolgreichen Stand"
    return template.render(
        product_name=config["product"]["name"],
        product_emoji=config["product"]["emoji"],
        generated_at_label=label,
        deal_count=deal_count,
        perlen=[
            {
                "flag": d.flag,
                "destination_city": d.destination_city,
                "destination_country": d.destination_country,
                "price": d.price,
                "date_range_label": d.date_range_label,
                "origin_iata": d.origin_iata,
                "duration_label": d.duration_label,
                "skyscanner_url": d.skyscanner_url,
                "has_bridge_day": d.has_bridge_day,
            }
            for d in perlen
        ],
    )


def write_dashboard(html: str, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
