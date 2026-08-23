import json
from datetime import date, timedelta

import pytest

from travel_assistant import tools


def call(tool, payload: dict):
    return json.loads(tool.invoke(payload))


def test_plan_trip_dates_counts_days_and_nights():
    result = call(
        tools.plan_trip_dates,
        {"start_date": "2026-09-01", "end_date": "2026-09-03", "travelers": 2},
    )

    assert result["trip_days"] == 3
    assert result["hotel_nights"] == 2
    assert result["travelers"] == 2


def test_plan_trip_dates_rejects_reversed_dates():
    result = call(
        tools.plan_trip_dates,
        {"start_date": "2026-09-03", "end_date": "2026-09-01", "travelers": 1},
    )

    assert "error" in result


def test_transport_returns_estimated_options():
    result = call(
        tools.search_transport,
        {
            "origin": "杭州",
            "destination": "上海市",
            "travel_date": "2026-09-01",
            "travelers": 2,
            "mode": "all",
            "round_trip": True,
        },
    )

    assert result["origin"] == "杭州"
    assert result["destination"] == "上海"
    assert {item["mode"] for item in result["options"]} == {
        "high_speed_rail",
        "coach",
        "driving",
    }
    assert result["options"][0]["estimated_total_price"] > 0


def test_driving_cost_has_vehicle_and_per_person_totals():
    result = call(
        tools.calculate_driving_cost,
        {"distance_km_one_way": 200, "travelers": 2, "round_trip": True},
    )

    assert result["total_distance_km"] == 400
    assert result["estimated_vehicle_total"] == pytest.approx(536)
    assert result["estimated_per_person"] == pytest.approx(268)


def test_hotel_and_food_costs_use_curated_city_data():
    hotel = call(
        tools.estimate_hotel_cost,
        {"city": "上海", "nights": 2, "rooms": 1, "level": "comfort"},
    )
    food = call(
        tools.estimate_food_cost,
        {"city": "上海", "trip_days": 2, "travelers": 2, "style": "standard"},
    )

    assert hotel["estimated_total"] == 1040
    assert food["estimated_total"] == 920


def test_attractions_match_interests_and_sum_tickets():
    result = call(
        tools.search_attractions,
        {
            "city": "上海",
            "interests": ["历史", "摄影"],
            "travelers": 2,
            "max_results": 4,
        },
    )

    names = {item["name"] for item in result["attractions"]}
    assert names == {"外滩", "上海博物馆", "豫园"}
    assert result["estimated_ticket_total"] == 80


def test_total_budget_adds_contingency_and_checks_limit():
    result = call(
        tools.calculate_total_budget,
        {
            "transport_cost": 320,
            "hotel_cost": 1040,
            "food_cost": 920,
            "attraction_cost": 80,
            "local_transport_cost": 200,
            "travelers": 2,
            "contingency_percent": 10,
            "budget_limit": 3000,
        },
    )

    assert result["subtotal"] == 2560
    assert result["estimated_total"] == 2816
    assert result["estimated_per_person"] == 1408
    assert result["within_budget"] is True


def test_weather_rejects_dates_outside_forecast_window():
    start = date.today() + timedelta(days=16)
    result = call(
        tools.get_travel_weather,
        {"city": "上海", "start_date": start.isoformat(), "end_date": start.isoformat()},
    )

    assert "error" in result
    assert "16 天" in result["error"]


def test_weather_uses_open_meteo_response(monkeypatch: pytest.MonkeyPatch):
    today = date.today()
    responses = iter(
        [
            {
                "results": [
                    {
                        "name": "上海",
                        "admin1": "上海",
                        "country": "中国",
                        "latitude": 31.23,
                        "longitude": 121.47,
                    }
                ]
            },
            {
                "timezone": "Asia/Shanghai",
                "daily": {
                    "time": [today.isoformat()],
                    "weather_code": [61],
                    "temperature_2m_max": [28.0],
                    "temperature_2m_min": [21.0],
                    "precipitation_probability_max": [70],
                    "wind_speed_10m_max": [18.0],
                },
            },
        ]
    )
    monkeypatch.setattr(tools, "_get_json", lambda _url, _params: next(responses))

    result = call(
        tools.get_travel_weather,
        {
            "city": "上海",
            "start_date": today.isoformat(),
            "end_date": today.isoformat(),
        },
    )

    assert result["data_source"] == "Open-Meteo 实时预报接口"
    assert result["forecasts"][0]["weather"] == "小雨"
    assert result["forecasts"][0]["max_precipitation_probability_percent"] == 70
