"""
weather_broadcast.py — запускається GitHub Actions кожні 3 години
Бере список підписників з JSONBin і надсилає погоду всім
"""

import os
import json
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
WEATHER_API_KEY = os.environ["OPENWEATHER_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GIST_ID = os.environ["GIST_ID"]

LAT = 50.4501
LON = 30.5234
CITY_UA = "Київ"

WEATHER_EMOJI = {
    "clear": "☀️", "clouds": "☁️", "rain": "🌧️", "drizzle": "🌦️",
    "thunderstorm": "⛈️", "snow": "❄️", "mist": "🌫️", "fog": "🌫️",
    "haze": "🌫️", "smoke": "🌫️", "dust": "🌫️", "tornado": "🌪️",
}

WIND_DIRECTIONS = {
    (0, 22.5): "Пн", (22.5, 67.5): "ПнСх", (67.5, 112.5): "Сх",
    (112.5, 157.5): "ПдСх", (157.5, 202.5): "Пд", (202.5, 247.5): "ПдЗх",
    (247.5, 292.5): "Зх", (292.5, 337.5): "ПнЗх", (337.5, 360): "Пн",
}

UA_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
UA_MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня",
             "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]


# ── Підписники ──────────────────────────────────────────────────────────────

def get_subscribers() -> list[int]:
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    content = response.json()["files"]["subscribers.json"]["content"]
    return json.loads(content).get("subscribers", [])


# ── Погода ───────────────────────────────────────────────────────────────────

def get_weather_emoji(main: str) -> str:
    return WEATHER_EMOJI.get(main.lower(), "🌡️")


def get_wind_direction(degrees: float) -> str:
    for (lo, hi), direction in WIND_DIRECTIONS.items():
        if lo <= degrees < hi:
            return direction
    return "—"


def format_date(dt) -> str:
    day = dt.day
    month = UA_MONTHS[dt.month - 1]
    weekday = UA_WEEKDAYS[dt.weekday()]
    return f"{weekday}, {day} {month}"


def fetch_forecast() -> dict:
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": LAT, "lon": LON,
        "appid": WEATHER_API_KEY,
        "units": "metric", "lang": "uk", "cnt": 40,
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def group_by_day(data: dict) -> dict:
    days = {}
    for entry in data["list"]:
        dt = datetime.fromtimestamp(entry["dt"])
        key = dt.date()
        days.setdefault(key, []).append(entry)
    return days


def summarize(entries: list) -> dict:
    temps = [e["main"]["temp"] for e in entries]
    feels = [e["main"]["feels_like"] for e in entries]
    humidity = [e["main"]["humidity"] for e in entries]
    winds = [e["wind"]["speed"] for e in entries]
    wind_deg = entries[len(entries) // 2]["wind"].get("deg", 0)
    mains = [e["weather"][0]["main"] for e in entries]
    descs = [e["weather"][0]["description"] for e in entries]
    rain = sum(e.get("rain", {}).get("3h", 0) for e in entries)
    snow = sum(e.get("snow", {}).get("3h", 0) for e in entries)
    return {
        "temp_min": round(min(temps)), "temp_max": round(max(temps)),
        "feels_min": round(min(feels)), "feels_max": round(max(feels)),
        "humidity": round(sum(humidity) / len(humidity)),
        "wind": round(max(winds)),
        "wind_dir": get_wind_direction(wind_deg),
        "main": max(set(mains), key=mains.count),
        "desc": max(set(descs), key=descs.count).capitalize(),
        "rain": round(rain, 1), "snow": round(snow, 1),
    }


def day_block(date, s: dict, header: str) -> str:
    emoji = get_weather_emoji(s["main"])
    lines = [
        f"{header} — {format_date(date)}",
        f"{emoji} {s['desc']}",
        f"🌡 Температура: *{s['temp_min']}°...{s['temp_max']}°C*",
        f"🤔 Відчувається: {s['feels_min']}°...{s['feels_max']}°C",
        f"💧 Вологість: {s['humidity']}%",
        f"💨 Вітер: {s['wind']} м/с ({s['wind_dir']})",
    ]
    if s["rain"] > 0:
        lines.append(f"🌧 Дощ: {s['rain']} мм")
    if s["snow"] > 0:
        lines.append(f"❄️ Сніг: {s['snow']} мм")
    return "\n".join(lines)


def build_message() -> str:
    data = fetch_forecast()
    days = group_by_day(data)
    today = datetime.now().date()
    sorted_days = sorted(days.keys())[:4]

    headers = {0: f"📍 *{CITY_UA} — сьогодні*", 1: "📅 *Завтра*",
               2: "📅 *Післязавтра*", 3: "📅 *Через 3 дні*"}

    blocks = []
    idx = 0
    for day in sorted_days:
        if day >= today:
            s = summarize(days[day])
            blocks.append(day_block(day, s, headers.get(idx, "📅")))
            idx += 1

    blocks.append(f"🕐 Оновлено: {datetime.now().strftime('%H:%M')} | OpenWeatherMap")
    return "\n\n".join(blocks)


# ── Розсилка ─────────────────────────────────────────────────────────────────

def send_to(chat_id: int, text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    return r.ok


def main():
    subscribers = get_subscribers()
    if not subscribers:
        print("⚠️  Немає підписників — нікому надсилати.")
        return

    print(f"👥 Підписників: {len(subscribers)}")
    message = build_message()

    ok, fail = 0, 0
    for chat_id in subscribers:
        if send_to(chat_id, message):
            ok += 1
        else:
            fail += 1

    print(f"✅ Надіслано: {ok} | ❌ Помилок: {fail}")


if __name__ == "__main__":
    main()
