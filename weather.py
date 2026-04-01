import os
from datetime import datetime
from zoneinfo import ZoneInfo

import certifi
import requests
from dotenv import load_dotenv

# SSL фикс для Render
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["CURL_CA_BUNDLE"] = certifi.where()

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")

LAT = 40.1872
LON = 44.5152


# ------------------------
# язык API
# ------------------------
def map_lang_for_weather(lang: str) -> str:
    return "ru" if lang == "ru" else "en"


# ------------------------
# получение данных
# ------------------------
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


# ------------------------
# текст неба (С COVERED)
# ------------------------
def get_sky_text(lang: str, clouds: int) -> str:
    sky_map = {
        "ru": {
            "clear": "ясно",
            "few": "лёгкие облака",
            "soft": "переменная облачность",
            "cloudy": "облачно",
            "dense": "плотные облака",
            "covered": "полностью закрыто",
        },
        "en": {
            "clear": "clear",
            "few": "few clouds",
            "soft": "partly cloudy",
            "cloudy": "cloudy",
            "dense": "dense clouds",
            "covered": "fully covered",
        },
        "hy": {
            "clear": "պարզ է",
            "few": "թեթև ամպամածություն",
            "soft": "փոփոխական ամպամածություն",
            "cloudy": "ամպամած",
            "dense": "խիտ ամպեր",
            "covered": "ամբողջությամբ փակ է",
        },
    }

    local = sky_map.get(lang, sky_map["en"])

    if clouds < 10:
        return local["clear"]
    if clouds < 30:
        return local["few"]
    if clouds < 60:
        return local["soft"]
    if clouds < 80:
        return local["cloudy"]
    if clouds < 95:
        return local["dense"]

    return local["covered"]


# ------------------------
# воздух
# ------------------------
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


# ------------------------
# SCORE система
# ------------------------
def calculate_ararat_score(data: dict, crowd_bonus: int = 0) -> int:
    visibility = data["visibility"]
    clouds = data["clouds"]
    air_status = get_air_status(data)

    # visibility
    if visibility >= 10000:
        visibility_score = 50
    elif visibility >= 8000:
        visibility_score = 40
    elif visibility >= 6000:
        visibility_score = 30
    elif visibility >= 4000:
        visibility_score = 20
    else:
        visibility_score = 5

    # air
    air_scores = {
        "air_clean": 30,
        "air_ok": 22,
        "air_heavy": 10,
        "air_bad": 0,
    }
    air_score = air_scores.get(air_status, 0)

    # clouds (НЕ убивают всё)
    if clouds <= 20:
        clouds_score = 20
    elif clouds <= 40:
        clouds_score = 16
    elif clouds <= 60:
        clouds_score = 12
    elif clouds <= 80:
        clouds_score = 8
    else:
        clouds_score = 4

    total = visibility_score + air_score + clouds_score + crowd_bonus
    return min(total, 100)


# ------------------------
# confidence
# ------------------------
def get_visibility_confidence(data: dict) -> str:
    visibility = data["visibility"]
    clouds = data["clouds"]
    air_status = get_air_status(data)

    if visibility >= 9000 and air_status in ("air_clean", "air_ok") and clouds <= 60:
        return "high"
    if visibility >= 7000 and air_status != "air_bad":
        return "medium"
    return "low"


# ------------------------
# ГЛАВНАЯ ЛОГИКА (с covered)
# ------------------------
def get_ararat_status_from_score(score: int, data: dict) -> str:
    visibility = data["visibility"]
    clouds = data["clouds"]
    aqi = data["aqi"]
    pm25 = data["pm25"]
    pm10 = data["pm10"]

    # смог
    if aqi >= 4 or pm25 >= 35 or pm10 >= 50:
        return "smog"

    # 🔥 если всё закрыто
    if clouds >= 95:
        if visibility >= 9000:
            return "covered"
        return "bad"

    # 🔥 если видно далеко — не убиваем облаками
    if visibility >= 9000:
        if clouds < 40:
            return "excellent"
        elif clouds < 80:
            return "good"
        else:
            return "cloudy"

    # fallback
    if score >= 80:
        return "excellent"
    if score >= 65:
        return "good"
    if score >= 45:
        return "cloudy"
    if score >= 25:
        return "medium"
    return "bad"


# ------------------------
# время суток
# ------------------------
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