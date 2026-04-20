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


def map_lang_for_air(lang: str) -> str:
    return lang if lang in ("ru", "en", "hy") else "en"


# ------------------------
# воздух из airquality.am
# ------------------------
def get_airquality_am_data(lang="ru"):
    locale = map_lang_for_air(lang)

    url = f"https://airquality.am/{locale}/air-quality-app/v1/region/yerevan.json"

    headers = {
        "User-Agent": "AraratNowBot/1.0"
    }

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    data = response.json()

    return {
        "aqi": data.get("aqi", 0),
        "pm25": data.get("pm2.5", 0),
        "pm10": data.get("pm10", 0),
    }


# ------------------------
# получение данных
# ------------------------
def get_weather_data(lang="ru"):
    weather_lang = map_lang_for_weather(lang)

    weather_url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric&lang={weather_lang}"
    )

    weather_response = requests.get(weather_url, timeout=10)
    weather_response.raise_for_status()

    weather_data = weather_response.json()

    # погода
    temp = weather_data.get("main", {}).get("temp", 0)
    wind = weather_data.get("wind", {}).get("speed", 0)
    clouds = weather_data.get("clouds", {}).get("all", 0)
    visibility = weather_data.get("visibility", 0)

    weather_main = weather_data.get("weather", [{}])[0].get("main", "")
    weather_description = weather_data.get("weather", [{}])[0].get("description", "")

    rain_1h = weather_data.get("rain", {}).get("1h", 0) or 0
    snow_1h = weather_data.get("snow", {}).get("1h", 0) or 0

    # воздух (новый источник)
    air_data = get_airquality_am_data(lang)

    return {
        "temp": temp,
        "wind": wind,
        "clouds": clouds,
        "visibility": visibility,
        "aqi": air_data["aqi"],
        "pm25": air_data["pm25"],
        "pm10": air_data["pm10"],
        "weather_main": weather_main,
        "weather_description": weather_description,
        "rain_1h": rain_1h,
        "snow_1h": snow_1h,
    }


# ------------------------
# текст неба
# ------------------------
def get_sky_text(lang: str, clouds: int) -> str:
    sky_map = {
        "ru": {
            "clear": "ясно",
            "few": "лёгкие облака",
            "soft": "переменная облачность",
            "cloudy": "облачно",
            "dense": "плотные облака",
            "covered": "полностью закрыто облаками",
        },
        "en": {
            "clear": "clear",
            "few": "few clouds",
            "soft": "partly cloudy",
            "cloudy": "cloudy",
            "dense": "dense clouds",
            "covered": "fully covered by clouds",
        },
        "hy": {
            "clear": "պարզ է",
            "few": "թեթև ամպամածություն",
            "soft": "փոփոխական ամպամածություն",
            "cloudy": "ամպամած",
            "dense": "խիտ ամպեր",
            "covered": "ամբողջությամբ փակ է ամպերով",
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
# воздух (новая шкала)
# ------------------------
def get_air_status(data: dict) -> str:
    aqi = data["aqi"]
    pm25 = data["pm25"]

    if aqi <= 25 and pm25 <= 10:
        return "air_clean"

    if aqi <= 60 and pm25 <= 20:
        return "air_ok"

    if aqi <= 100 and pm25 <= 35:
        return "air_heavy"

    return "air_bad"


# ------------------------
# осадки штраф
# ------------------------
def get_precipitation_penalty(data: dict) -> int:
    rain_1h = data.get("rain_1h", 0) or 0
    snow_1h = data.get("snow_1h", 0) or 0
    weather_main = (data.get("weather_main") or "").lower()

    if "thunderstorm" in weather_main:
        return 45

    penalty = 0

    if rain_1h > 0:
        penalty += 20 if rain_1h >= 1 else 10

    if snow_1h > 0:
        penalty += 20 if snow_1h >= 0.5 else 10

    return penalty


# ------------------------
# SCORE
# ------------------------
def calculate_ararat_score(data: dict, crowd_bonus: int = 0) -> int:
    visibility = data["visibility"]
    clouds = data["clouds"]
    aqi = data["aqi"]
    pm25 = data["pm25"]

    air_status = get_air_status(data)

    # ------------------------
    # visibility (ОСЛАБИЛИ)
    # ------------------------
    if visibility >= 10000:
        visibility_score = 35
    elif visibility >= 8000:
        visibility_score = 25
    elif visibility >= 6000:
        visibility_score = 15
    elif visibility >= 4000:
        visibility_score = 8
    else:
        visibility_score = 3

    # ------------------------
    # воздух (УСИЛИЛИ)
    # ------------------------
    air_scores = {
        "air_clean": 30,
        "air_ok": 25,
        "air_heavy": 15,
        "air_bad": 0,
    }
    air_score = air_scores.get(air_status, 0)

    # ------------------------
    # облака
    # ------------------------
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

    # ------------------------
    # осадки
    # ------------------------
    precip_penalty = get_precipitation_penalty(data)

    # ------------------------
    # haze (дымка от воздуха)
    # ------------------------
    haze_penalty = 0

    if aqi >= 80:
        haze_penalty = 20
    elif aqi >= 60:
        haze_penalty = 12
    elif aqi >= 40:
        haze_penalty = 6

    # ------------------------
    # итог
    # ------------------------
    total = (
        visibility_score
        + air_score
        + clouds_score
        + crowd_bonus
        - precip_penalty
        - haze_penalty
    )

    return max(0, min(total, 100))

# ------------------------
# финальный статус
# ------------------------
def get_ararat_status_from_score(score: int, data: dict) -> str:
    visibility = data["visibility"]
    clouds = data["clouds"]
    aqi = data["aqi"]
    pm25 = data["pm25"]
    pm10 = data["pm10"]

    rain_1h = data.get("rain_1h", 0) or 0
    snow_1h = data.get("snow_1h", 0) or 0
    weather_main = (data.get("weather_main") or "").lower()

    # ------------------------
    # 1. жесткие стоп-факторы
    # ------------------------
    if "thunderstorm" in weather_main:
        return "bad"

    if rain_1h >= 3 or snow_1h >= 2:
        return "bad"

    # ------------------------
    # 2. СМОГ (теперь адекватный)
    # ------------------------
    if (
        aqi >= 100
        or pm25 >= 35
        or pm10 >= 50
        or (aqi >= 70 and visibility < 7000)
    ):
        return "smog"

    # ------------------------
    # 3. полностью закрыто
    # ------------------------
    if clouds >= 95:
        return "covered" if visibility >= 9000 else "bad"

    # ------------------------
    # 4. осадки
    # ------------------------
    if rain_1h > 0 or snow_1h > 0:
        if score >= 70:
            return "good"
        if score >= 50:
            return "cloudy"
        if score >= 30:
            return "medium"
        return "bad"

    # ------------------------
    # 5. если видно далеко
    # ------------------------
    if visibility >= 9000:
        if clouds < 40 and aqi < 60:
            return "excellent"
        elif clouds < 80:
            return "good"
        return "cloudy"

    # ------------------------
    # 6. fallback
    # ------------------------
    if score >= 75:
        return "excellent"
    if score >= 60:
        return "good"
    if score >= 45:
        return "cloudy"
    if score >= 30:
        return "medium"
    return "bad"

# ------------------------
# время суток
# ------------------------
def get_time_mode() -> str:
    hour = datetime.now(ZoneInfo("Asia/Yerevan")).hour

    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "day"
    if 18 <= hour < 22:
        return "evening"
    return "night"