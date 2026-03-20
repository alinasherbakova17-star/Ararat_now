import os
from datetime import datetime
from zoneinfo import ZoneInfo

import certifi
import requests
from dotenv import load_dotenv

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["CURL_CA_BUNDLE"] = certifi.where()

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")

LAT = 40.1872
LON = 44.5152


def map_lang_for_weather(lang: str) -> str:
    if lang == "ru":
        return "ru"
    return "en"


def get_weather_data(lang="ru"):
    weather_lang = map_lang_for_weather(lang)

    weather_url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric&lang={weather_lang}"
    )

    air_url = (
        f"https://api.openweathermap.org/data/2.5/air_pollution"
        f"?lat={LAT}&lon={LON}&appid={API_KEY}"
    )

    weather_response = requests.get(weather_url, timeout=10)
    air_response = requests.get(air_url, timeout=10)

    weather_response.raise_for_status()
    air_response.raise_for_status()

    weather_data = weather_response.json()
    air_data = air_response.json()

    temp = weather_data.get("main", {}).get("temp", 0)
    wind = weather_data.get("wind", {}).get("speed", 0)
    clouds = weather_data.get("clouds", {}).get("all", 0)
    visibility = weather_data.get("visibility", 0)

    air_list = air_data.get("list", [{}])
    air_main = air_list[0].get("main", {})
    air_components = air_list[0].get("components", {})

    aqi = air_main.get("aqi", 0)
    pm25 = air_components.get("pm2_5", 0)
    pm10 = air_components.get("pm10", 0)

    return {
        "temp": temp,
        "wind": wind,
        "clouds": clouds,
        "visibility": visibility,
        "aqi": aqi,
        "pm25": pm25,
        "pm10": pm10,
    }


def get_sky_text(lang: str, clouds: int) -> str:
    sky_map = {
        "ru": {
            "clear": "ясно",
            "few": "небольшая облачность",
            "cloudy": "облачно",
            "overcast": "пасмурно",
        },
        "en": {
            "clear": "clear",
            "few": "few clouds",
            "cloudy": "cloudy",
            "overcast": "overcast",
        },
        "hy": {
            "clear": "պարզ է",
            "few": "թեթև ամպամածություն",
            "cloudy": "ամպամած",
            "overcast": "մռայլ է",
        },
    }

    local = sky_map.get(lang, sky_map["en"])

    if clouds < 15:
        return local["clear"]
    if clouds < 40:
        return local["few"]
    if clouds < 75:
        return local["cloudy"]
    return local["overcast"]


def get_ararat_status(data: dict) -> str:
    visibility = data["visibility"]
    clouds = data["clouds"]
    aqi = data["aqi"]
    pm25 = data["pm25"]
    pm10 = data["pm10"]

    if aqi >= 4 or pm25 >= 35 or pm10 >= 50:
        return "smog"

    if visibility < 4000:
        return "bad"

    if visibility >= 9000 and clouds <= 35:
        return "excellent"

    if visibility >= 9000 and clouds <= 65:
        return "good"

    if visibility >= 9000 and clouds > 65:
        return "cloudy"

    if 4000 <= visibility < 9000:
        return "medium"

    return "medium"


def get_air_status(data: dict) -> str:
    aqi = data["aqi"]
    pm25 = data["pm25"]

    if aqi <= 2 and pm25 <= 15:
        return "air_clean"

    if aqi == 3 and pm25 <= 35:
        return "air_ok"

    if aqi == 4 or pm25 <= 55:
        return "air_heavy"

    return "air_bad"


def get_time_mode() -> str:
    now = datetime.now(ZoneInfo("Asia/Yerevan"))
    hour = now.hour

    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "day"
    if 18 <= hour < 22:
        return "evening"
    return "night"