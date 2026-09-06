"""Orchestrator: config -> fetch (Travelpayouts) -> classify/filter -> render
dashboard + email digest -> send. Each phase is isolated so a failure in one
(e.g. email) never prevents the others (e.g. the dashboard file) from being
produced. Always exits 0 unless config/required env vars are missing.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from config_loader import all_airports, load_config
from deal_builder import build_deals
from dealmodel import Deal
from email_sender import EmailSendError, send_digest
from filters import apply_all
from reference_data import load_reference_data
from render import render_dashboard, render_email_digest, write_dashboard
from selector import select_bridge_days, select_long_trips, select_perlen, sort_by_price
from travelpayouts_client import TravelpayoutsClient, TravelpayoutsError

logger = logging.getLogger("main")


def setup_logging(log_file: str | Path) -> None:
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler(sys.stdout))


def fetch_all_deals(config: dict) -> tuple[list[Deal], bool]:
    """Returns (deals, any_origin_succeeded). Partial per-origin failures are
    logged and skipped rather than aborting the whole run."""
    token = os.environ.get("TRAVELPAYOUTS_API_TOKEN", "")
    client = TravelpayoutsClient(token, cache_dir=config["paths"]["cache_dir"])
    reference = load_reference_data(
        config["paths"]["reference_dir"],
        max_age_days=config["travelpayouts"]["reference_data_refresh_days"],
    )
    sunny_countries = config.get("sunny_destinations", {}).get("countries", [])

    all_deals: list[Deal] = []
    any_success = False

    for airport in all_airports(config):
        try:
            raw = client.prices_for_dates(
                origin=airport,
                currency=config["travelpayouts"]["currency"],
                direct=config["filters"]["nonstop_only"],
                market=config["travelpayouts"]["market"],
                limit=config["travelpayouts"]["limit_per_origin"],
            )
        except TravelpayoutsError as exc:
            logger.warning("Fetching deals for %s failed, skipping this airport: %s", airport, exc)
            continue

        any_success = True
        all_deals.extend(build_deals(
            raw, airport, reference, sunny_countries,
            long_max_days=config["filters"]["max_vacation_days"],
        ))
        logger.info("Fetched %d raw candidates for %s", len(raw), airport)

    return all_deals, any_success


def load_previous_deals(latest_deals_path: str | Path) -> list[Deal]:
    path = Path(latest_deals_path)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [Deal.from_json_dict(d) for d in raw]
    except (json.JSONDecodeError, OSError, KeyError) as exc:
        logger.warning("Could not load fallback deals from %s: %s", path, exc)
        return []


def save_deals(deals: list[Deal], config: dict, generated_at: datetime) -> None:
    latest_path = Path(config["paths"]["latest_deals_json"])
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(
        json.dumps([d.to_json_dict() for d in deals]), encoding="utf-8"
    )

    history_dir = Path(config["paths"]["history_dir"])
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / f"{generated_at.date().isoformat()}.json"
    history_path.write_text(
        json.dumps([d.to_json_dict() for d in deals]), encoding="utf-8"
    )


def run() -> None:
    load_dotenv()
    config = load_config("config.yaml")
    setup_logging(config["paths"]["log_file"])

    logger.info("Starting daily flight-deal run")
    generated_at = datetime.now()

    deals, any_success = fetch_all_deals(config)
    stale = False

    if not any_success:
        logger.error("All origin airports failed -- falling back to previous day's deals")
        deals = load_previous_deals(config["paths"]["latest_deals_json"])
        stale = True
        if deals:
            generated_at = deals[0].fetched_at.astimezone().replace(tzinfo=None)

    filtered = apply_all(deals, config)
    filtered = sort_by_price(filtered)
    perlen = select_perlen(filtered)
    bridge_days = select_bridge_days(filtered)
    long_trips = select_long_trips(filtered)

    logger.info(
        "%d deals after filtering (stale=%s, bridge_days=%d, long_trips=%d)",
        len(filtered), stale, len(bridge_days), len(long_trips),
    )

    if not stale:
        save_deals(filtered, config, generated_at)

    dashboard_html = render_dashboard(
        filtered, perlen, bridge_days, long_trips, config, generated_at, stale=stale
    )
    output_path = write_dashboard(dashboard_html, config["paths"]["dashboard_output"])
    logger.info("Dashboard written to %s", output_path)

    resend_key = os.environ.get("RESEND_API_KEY", "")
    if perlen:
        email_html = render_email_digest(perlen, len(filtered), generated_at, config, stale=stale)
        subject = config["email"]["subject_template"].format(
            count=len(filtered), date=generated_at.strftime("%d.%m.%Y")
        )
        try:
            send_digest(
                api_key=resend_key,
                sender=config["email"]["sender"],
                recipient=config["email"]["recipient"],
                subject=subject,
                html_body=email_html,
                dashboard_html=dashboard_html,
            )
        except EmailSendError as exc:
            logger.error("Sending digest email failed (dashboard was still written): %s", exc)
    else:
        logger.info("No deals matched filters today; skipping email, dashboard still written")

    logger.info("Run complete")


if __name__ == "__main__":
    run()
