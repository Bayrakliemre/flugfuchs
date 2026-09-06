"""Loads and validates config.yaml into a plain dict, failing fast on missing keys."""
from __future__ import annotations

from pathlib import Path

import yaml

_REQUIRED_PATHS = [
    ("product", "name"),
    ("product", "emoji"),
    ("airports", "primary"),
    ("airports", "secondary"),
    ("filters", "nonstop_only"),
    ("filters", "max_flight_duration_hours"),
    ("filters", "max_price_eur"),
    ("filters", "max_vacation_days"),
    ("travelpayouts", "market"),
    ("travelpayouts", "currency"),
    ("travelpayouts", "limit_per_origin"),
    ("travelpayouts", "reference_data_refresh_days"),
    ("email", "recipient"),
    ("email", "sender"),
    ("email", "subject_template"),
    ("paths", "dashboard_output"),
    ("paths", "cache_dir"),
    ("paths", "history_dir"),
    ("paths", "latest_deals_json"),
    ("paths", "reference_dir"),
    ("paths", "log_file"),
]


def load_config(config_path: str | Path = "config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Config file {path} did not parse to a mapping")

    missing = []
    for section, key in _REQUIRED_PATHS:
        section_val = config.get(section)
        if not isinstance(section_val, dict) or key not in section_val:
            missing.append(f"{section}.{key}")

    if missing:
        raise ValueError(
            "Config is missing required keys: " + ", ".join(missing)
        )

    config.setdefault("sunny_destinations", {}).setdefault("countries", [])
    config.setdefault("region_label", "")

    return config


def all_airports(config: dict) -> list[str]:
    return list(config["airports"]["primary"]) + list(config["airports"]["secondary"])
