from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path


DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "destinations.json"


def normalize_city(city: str) -> str:
    normalized = city.strip()
    if normalized.endswith("市"):
        normalized = normalized[:-1]
    return normalized


@lru_cache(maxsize=1)
def load_destinations() -> dict[str, dict]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("destinations.json 顶层必须是对象。")
    return data


def get_destination(city: str) -> tuple[str, dict] | None:
    normalized = normalize_city(city)
    destination = load_destinations().get(normalized)
    return (normalized, destination) if destination else None


def haversine_distance_km(origin: dict, destination: dict) -> float:
    radius_km = 6371.0088
    lat1 = math.radians(origin["latitude"])
    lon1 = math.radians(origin["longitude"])
    lat2 = math.radians(destination["latitude"])
    lon2 = math.radians(destination["longitude"])
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(value))
