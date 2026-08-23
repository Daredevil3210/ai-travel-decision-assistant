from __future__ import annotations

import json
import math
from datetime import date, timedelta
from typing import Literal

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from travel_assistant.data import get_destination, haversine_distance_km


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _error(message: str) -> str:
    return _json_text({"error": message})


# ---------------------------------------------------------------------------
# Travel dates
# ---------------------------------------------------------------------------


class TripDatesInput(BaseModel):
    start_date: date = Field(description="出发日期，格式 YYYY-MM-DD")
    end_date: date = Field(description="返程日期，格式 YYYY-MM-DD")
    travelers: int = Field(default=1, ge=1, le=20, description="出行人数")


@tool(args_schema=TripDatesInput)
def plan_trip_dates(start_date: date, end_date: date, travelers: int = 1) -> str:
    """校验旅行日期并计算行程天数、住宿晚数和人数。"""
    difference = (end_date - start_date).days
    if difference < 0:
        return _error("返程日期不能早于出发日期。")
    if difference > 30:
        return _error("教学项目只支持不超过 31 天的旅行计划。")
    return _json_text(
        {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "trip_days": difference + 1,
            "hotel_nights": difference,
            "travelers": travelers,
        }
    )


# ---------------------------------------------------------------------------
# Transport estimates
# ---------------------------------------------------------------------------

TransportMode = Literal["all", "high_speed_rail", "coach", "driving"]


def _transport_options(distance_km: float, travelers: int, round_trip: bool) -> list[dict]:
    multiplier = 2 if round_trip else 1
    rail_distance = distance_km * 1.08
    road_distance = distance_km * 1.22
    return [
        {
            "mode": "high_speed_rail",
            "estimated_one_way_hours": round(rail_distance / 240 + 0.35, 2),
            "estimated_price_per_person_one_way": round(max(25, rail_distance * 0.46), 2),
            "estimated_total_price": round(max(25, rail_distance * 0.46) * travelers * multiplier, 2),
            "note": "不含市内接驳，实际车次和票价请以铁路官方渠道为准",
        },
        {
            "mode": "coach",
            "estimated_one_way_hours": round(road_distance / 75 + 0.4, 2),
            "estimated_price_per_person_one_way": round(max(20, road_distance * 0.24), 2),
            "estimated_total_price": round(max(20, road_distance * 0.24) * travelers * multiplier, 2),
            "note": "不含候车和堵车时间，实际班次请以客运站为准",
        },
        {
            "mode": "driving",
            "estimated_road_distance_km_one_way": round(road_distance, 1),
            "estimated_one_way_hours": round(road_distance / 85 + 0.25, 2),
            "estimated_total_price": None,
            "requires_next_tool": "calculate_driving_cost",
            "note": "需要继续调用自驾成本工具计算油费、过路费和停车费",
        },
    ]


class TransportSearchInput(BaseModel):
    origin: str = Field(min_length=1, max_length=40, description="出发城市")
    destination: str = Field(min_length=1, max_length=40, description="目的地城市")
    travel_date: date = Field(description="出发日期 YYYY-MM-DD")
    travelers: int = Field(default=1, ge=1, le=20, description="出行人数")
    mode: TransportMode = Field(default="all", description="交通方式筛选")
    round_trip: bool = Field(default=True, description="是否按往返计算票价")


@tool(args_schema=TransportSearchInput)
def search_transport(
    origin: str,
    destination: str,
    travel_date: date,
    travelers: int = 1,
    mode: TransportMode = "all",
    round_trip: bool = True,
) -> str:
    """估算两个已收录城市之间的高铁、客运和自驾距离、时间及费用。"""
    origin_data = get_destination(origin)
    destination_data = get_destination(destination)
    if not origin_data:
        return _error(f"交通估算数据暂未收录出发城市：{origin}")
    if not destination_data:
        return _error(f"交通估算数据暂未收录目的地城市：{destination}")
    if origin_data[0] == destination_data[0]:
        return _error("出发城市和目的地城市不能相同。")

    direct_distance = haversine_distance_km(origin_data[1], destination_data[1])
    options = _transport_options(direct_distance, travelers, round_trip)
    if mode != "all":
        options = [item for item in options if item["mode"] == mode]

    return _json_text(
        {
            "origin": origin_data[0],
            "destination": destination_data[0],
            "travel_date": travel_date.isoformat(),
            "travelers": travelers,
            "round_trip": round_trip,
            "straight_line_distance_km": round(direct_distance, 1),
            "options": options,
            "data_quality": "教学估算，不代表实时班次、路况或票价",
        }
    )


class DrivingCostInput(BaseModel):
    distance_km_one_way: float = Field(gt=0, le=10000, description="单程公路里程，千米")
    travelers: int = Field(default=1, ge=1, le=20, description="分摊人数")
    round_trip: bool = Field(default=True, description="是否计算往返")
    fuel_consumption_l_per_100km: float = Field(default=8.0, gt=0, le=30, description="百公里油耗")
    fuel_price_per_liter: float = Field(default=8.0, gt=0, le=20, description="每升燃油价格")
    toll_per_km: float = Field(default=0.45, ge=0, le=2, description="每千米高速费估算")
    parking_cost: float = Field(default=100, ge=0, description="全程停车费估算")


@tool(args_schema=DrivingCostInput)
def calculate_driving_cost(
    distance_km_one_way: float,
    travelers: int = 1,
    round_trip: bool = True,
    fuel_consumption_l_per_100km: float = 8.0,
    fuel_price_per_liter: float = 8.0,
    toll_per_km: float = 0.45,
    parking_cost: float = 100,
) -> str:
    """根据里程、油耗、油价、过路费和停车费估算自驾总成本。"""
    total_distance = distance_km_one_way * (2 if round_trip else 1)
    fuel_liters = total_distance * fuel_consumption_l_per_100km / 100
    fuel_cost = fuel_liters * fuel_price_per_liter
    toll_cost = total_distance * toll_per_km
    total = fuel_cost + toll_cost + parking_cost
    return _json_text(
        {
            "total_distance_km": round(total_distance, 1),
            "estimated_fuel_liters": round(fuel_liters, 2),
            "estimated_fuel_cost": round(fuel_cost, 2),
            "estimated_toll_cost": round(toll_cost, 2),
            "estimated_parking_cost": round(parking_cost, 2),
            "estimated_vehicle_total": round(total, 2),
            "estimated_per_person": round(total / travelers, 2),
            "data_quality": "教学估算，未包含车辆折旧和实时路况",
        }
    )


# ---------------------------------------------------------------------------
# Accommodation, food and attractions
# ---------------------------------------------------------------------------

HotelLevel = Literal["economy", "comfort", "premium", "luxury"]


class HotelCostInput(BaseModel):
    city: str = Field(description="住宿城市")
    nights: int = Field(ge=0, le=30, description="住宿晚数")
    rooms: int = Field(default=1, ge=1, le=10, description="房间数量")
    level: HotelLevel = Field(default="comfort", description="酒店档次")


@tool(args_schema=HotelCostInput)
def estimate_hotel_cost(
    city: str,
    nights: int,
    rooms: int = 1,
    level: HotelLevel = "comfort",
) -> str:
    """根据城市、晚数、房间数和档次估算住宿费用。"""
    destination = get_destination(city)
    if not destination:
        return _error(f"住宿估算数据暂未收录城市：{city}")
    nightly_rate = destination[1]["hotel_base_price"][level]
    total = nightly_rate * nights * rooms
    return _json_text(
        {
            "city": destination[0],
            "level": level,
            "nights": nights,
            "rooms": rooms,
            "estimated_rate_per_room_night": nightly_rate,
            "estimated_total": round(total, 2),
            "data_quality": "教学估算，节假日和热门日期可能显著上涨",
        }
    )


MealStyle = Literal["budget", "standard", "premium"]


class FoodCostInput(BaseModel):
    city: str = Field(description="用餐城市")
    trip_days: int = Field(ge=1, le=31, description="旅行天数")
    travelers: int = Field(default=1, ge=1, le=20, description="出行人数")
    style: MealStyle = Field(default="standard", description="餐饮标准")


@tool(args_schema=FoodCostInput)
def estimate_food_cost(
    city: str,
    trip_days: int,
    travelers: int = 1,
    style: MealStyle = "standard",
) -> str:
    """根据城市、天数、人数和消费标准估算餐饮费用。"""
    destination = get_destination(city)
    if not destination:
        return _error(f"餐饮估算数据暂未收录城市：{city}")
    daily_per_person = destination[1]["meal_daily_price"][style]
    total = daily_per_person * trip_days * travelers
    return _json_text(
        {
            "city": destination[0],
            "style": style,
            "trip_days": trip_days,
            "travelers": travelers,
            "estimated_daily_per_person": daily_per_person,
            "estimated_total": round(total, 2),
            "data_quality": "教学估算，不包含酒水和特殊宴席",
        }
    )


class AttractionSearchInput(BaseModel):
    city: str = Field(description="目的地城市")
    interests: list[str] = Field(
        default_factory=list,
        description="兴趣关键词列表，例如历史、自然、亲子、摄影、美食、夜景",
    )
    travelers: int = Field(default=1, ge=1, le=20, description="用于估算门票的出行人数")
    max_results: int = Field(default=4, ge=1, le=8, description="最多返回几个景点")


@tool(args_schema=AttractionSearchInput)
def search_attractions(
    city: str,
    interests: list[str] | None = None,
    travelers: int = 1,
    max_results: int = 4,
) -> str:
    """按城市和兴趣筛选景点，并估算所选景点门票。"""
    destination = get_destination(city)
    if not destination:
        return _error(f"景点数据暂未收录城市：{city}")
    interests = [item.strip() for item in (interests or []) if item.strip()]
    attractions = destination[1]["attractions"]
    if interests:
        matched = [
            item
            for item in attractions
            if set(interests).intersection(item.get("categories", []))
        ]
    else:
        matched = list(attractions)
    selected = matched[:max_results]
    ticket_total = sum(float(item["ticket_price"]) for item in selected) * travelers
    return _json_text(
        {
            "city": destination[0],
            "interests": interests,
            "travelers": travelers,
            "count": len(selected),
            "attractions": selected,
            "estimated_ticket_total": round(ticket_total, 2),
            "data_quality": "教学数据，开放时间和票价请以景区官方信息为准",
        }
    )


# ---------------------------------------------------------------------------
# Weather via Open-Meteo
# ---------------------------------------------------------------------------

_WEATHER_CODES = {
    0: "晴朗",
    1: "大部晴朗",
    2: "局部多云",
    3: "阴天",
    45: "有雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "中等毛毛雨",
    55: "强毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "小阵雨",
    81: "中等阵雨",
    82: "强阵雨",
    95: "雷雨",
}


def weather_code_text(code: int) -> str:
    return _WEATHER_CODES.get(code, f"未知天气代码 {code}")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(0.5),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True,
)
def _get_json(url: str, params: dict[str, object]) -> dict:
    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


class WeatherInput(BaseModel):
    city: str = Field(min_length=1, max_length=80, description="目的地城市")
    start_date: date = Field(description="天气预报开始日期 YYYY-MM-DD")
    end_date: date = Field(description="天气预报结束日期 YYYY-MM-DD，最多连续 7 天")


@tool(args_schema=WeatherInput)
def get_travel_weather(city: str, start_date: date, end_date: date) -> str:
    """查询未来 16 天内、连续最多 7 天的目的地天气预报。"""
    today = date.today()
    if end_date < start_date:
        return _error("天气结束日期不能早于开始日期。")
    if (end_date - start_date).days > 6:
        return _error("一次最多查询连续 7 天的天气。")
    if start_date < today:
        return _error("该工具只提供今天及未来天气，不查询历史天气。")
    if end_date > today + timedelta(days=15):
        return _error("Open-Meteo 可靠预报窗口有限，请在出发前 16 天内再次查询。")

    try:
        locations = _get_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": city, "count": 1, "language": "zh", "format": "json"},
        ).get("results", [])
        if not locations:
            return _error(f"没有找到城市：{city}")
        location = locations[0]
        data = _get_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "timezone": "auto",
            },
        )
        daily = data.get("daily", {})
        forecasts = []
        for index, forecast_date in enumerate(daily.get("time", [])):
            forecasts.append(
                {
                    "date": forecast_date,
                    "weather": weather_code_text(daily["weather_code"][index]),
                    "min_temperature_c": daily["temperature_2m_min"][index],
                    "max_temperature_c": daily["temperature_2m_max"][index],
                    "max_precipitation_probability_percent": daily[
                        "precipitation_probability_max"
                    ][index],
                    "max_wind_speed_kmh": daily["wind_speed_10m_max"][index],
                }
            )
        return _json_text(
            {
                "resolved_city": location.get("name"),
                "administrative_area": location.get("admin1"),
                "country": location.get("country"),
                "timezone": data.get("timezone"),
                "forecasts": forecasts,
                "data_source": "Open-Meteo 实时预报接口",
            }
        )
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        return _error(f"天气查询失败：{exc}")


# ---------------------------------------------------------------------------
# Final budget
# ---------------------------------------------------------------------------


class TotalBudgetInput(BaseModel):
    transport_cost: float = Field(default=0, ge=0, description="全体人员往返交通费用")
    hotel_cost: float = Field(default=0, ge=0, description="全部住宿费用")
    food_cost: float = Field(default=0, ge=0, description="全部餐饮费用")
    attraction_cost: float = Field(default=0, ge=0, description="全部景点门票费用")
    local_transport_cost: float = Field(default=0, ge=0, description="目的地市内交通费用")
    other_cost: float = Field(default=0, ge=0, description="购物之外的其他必要费用")
    travelers: int = Field(default=1, ge=1, le=20, description="出行人数")
    contingency_percent: float = Field(default=10, ge=0, le=50, description="预备金百分比")
    budget_limit: float | None = Field(default=None, gt=0, description="用户预算上限，可不填")


@tool(args_schema=TotalBudgetInput)
def calculate_total_budget(
    transport_cost: float = 0,
    hotel_cost: float = 0,
    food_cost: float = 0,
    attraction_cost: float = 0,
    local_transport_cost: float = 0,
    other_cost: float = 0,
    travelers: int = 1,
    contingency_percent: float = 10,
    budget_limit: float | None = None,
) -> str:
    """汇总旅行各项费用、预备金、人均预算，并与预算上限比较。"""
    items = {
        "transport": transport_cost,
        "hotel": hotel_cost,
        "food": food_cost,
        "attractions": attraction_cost,
        "local_transport": local_transport_cost,
        "other": other_cost,
    }
    subtotal = sum(items.values())
    contingency = subtotal * contingency_percent / 100
    total = subtotal + contingency
    result = {
        "items": {name: round(value, 2) for name, value in items.items()},
        "subtotal": round(subtotal, 2),
        "contingency_percent": contingency_percent,
        "contingency_amount": round(contingency, 2),
        "estimated_total": round(total, 2),
        "travelers": travelers,
        "estimated_per_person": round(total / travelers, 2),
        "currency": "CNY",
        "data_quality": "基于各工具输出的教学估算",
    }
    if budget_limit is not None:
        result["budget_limit"] = round(budget_limit, 2)
        result["remaining_or_over"] = round(budget_limit - total, 2)
        result["within_budget"] = total <= budget_limit
    return _json_text(result)


TOOLS = [
    plan_trip_dates,
    search_transport,
    calculate_driving_cost,
    estimate_hotel_cost,
    estimate_food_cost,
    search_attractions,
    get_travel_weather,
    calculate_total_budget,
]
TOOL_MAP = {item.name: item for item in TOOLS}
