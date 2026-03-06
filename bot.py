import os
import requests
from datetime import datetime, timedelta

# === Конфигурация ===
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
WEATHER_API_KEY = os.environ["OPENWEATHER_API_KEY"]

CITY = "Kyiv"
CITY_UA = "Київ"
LAT = 50.4501
LON = 30.5234
UNITS = "metric"

# Иконки для описания погоды
WEATHER_EMOJI = {
    "clear": "☀️",
    "clouds": "☁️",
    "rain": "🌧️",
    "drizzle": "🌦️",
    "thunderstorm": "⛈️",
    "snow": "❄️",
    "mist": "🌫️",
    "fog": "🌫️",
    "haze": "🌫️",
    "smoke": "🌫️",
    "dust": "🌫️",
    "sand": "🌫️",
    "ash": "🌫️",
    "squall": "🌬️",
    "tornado": "🌪️",
}

WIND_DIRECTIONS = {
    (0, 22.5): "Пн", (22.5, 67.5): "ПнСх", (67.5, 112.5): "Сх",
    (112.5, 157.5): "ПдСх", (157.5, 202.5): "Пд", (202.5, 247.5): "ПдЗх",
    (247.5, 292.5): "Зх", (292.5, 337.5): "ПнЗх", (337.5, 360): "Пн",
}

UA_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
UA_MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня",
             "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]


def get_weather_emoji(description: str) -> str:
    desc = description.lower()
    for key, emoji in WEATHER_EMOJI.items():
        if key in desc:
            return emoji
    return "🌡️"


def get_wind_direction(degrees: float) -> str:
    for (lo, hi), direction in WIND_DIRECTIONS.items():
        if lo <= degrees < hi:
            return direction
    return "—"


def format_date(dt: datetime, include_weekday=True) -> str:
    day = dt.day
    month = UA_MONTHS[dt.month - 1]
    weekday = UA_WEEKDAYS[dt.weekday()]
    if include_weekday:
        return f"{weekday}, {day} {month}"
    return f"{day} {month}"


def fetch_weather():
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": LAT,
        "lon": LON,
        "appid": WEATHER_API_KEY,
        "units": UNITS,
        "lang": "uk",
        "cnt": 40,
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def parse_forecast(data: dict) -> dict:
    """
    Групує прогноз по днях.
    Повертає dict: { date_str -> [entry, ...] }
    """
    days = {}
    for entry in data["list"]:
        dt = datetime.fromtimestamp(entry["dt"])
        date_key = dt.date()
        if date_key not in days:
            days[date_key] = []
        days[date_key].append(entry)
    return days


def summarize_day(entries: list) -> dict:
    """Зводить список погодинних записів у денне зведення."""
    temps = [e["main"]["temp"] for e in entries]
    feels = [e["main"]["feels_like"] for e in entries]
    humidity = [e["main"]["humidity"] for e in entries]
    wind_speeds = [e["wind"]["speed"] for e in entries]
    wind_deg = entries[len(entries) // 2]["wind"].get("deg", 0)

    # Знаходимо найпоширеніший опис
    descriptions = [e["weather"][0]["description"] for e in entries]
    main_weather = [e["weather"][0]["main"] for e in entries]
    desc = max(set(descriptions), key=descriptions.count)
    main = max(set(main_weather), key=main_weather.count)

    # Опади
    rain_total = sum(e.get("rain", {}).get("3h", 0) for e in entries)
    snow_total = sum(e.get("snow", {}).get("3h", 0) for e in entries)

    return {
        "temp_min": round(min(temps)),
        "temp_max": round(max(temps)),
        "feels_min": round(min(feels)),
        "feels_max": round(max(feels)),
        "humidity": round(sum(humidity) / len(humidity)),
        "wind_speed": round(max(wind_speeds)),
        "wind_dir": get_wind_direction(wind_deg),
        "description": desc.capitalize(),
        "main": main,
        "rain": round(rain_total, 1),
        "snow": round(snow_total, 1),
    }


def format_today_block(date, summary: dict) -> str:
    emoji = get_weather_emoji(summary["main"])
    date_str = format_date(date)
    lines = [
        f"📍 *{CITY_UA} — прогноз погоди*",
        "",
        f"🗓 *Сьогодні* — {date_str}",
        f"{emoji} {summary['description']}",
        f"🌡 Температура: *{summary['temp_min']}°...{summary['temp_max']}°C*",
        f"🤔 Відчувається: {summary['feels_min']}°...{summary['feels_max']}°C",
        f"💧 Вологість: {summary['humidity']}%",
        f"💨 Вітер: {summary['wind_speed']} м/с ({summary['wind_dir']})",
    ]
    if summary["rain"] > 0:
        lines.append(f"🌧 Опади (дощ): {summary['rain']} мм")
    if summary["snow"] > 0:
        lines.append(f"❄️ Опади (сніг): {summary['snow']} мм")
    return "\n".join(lines)


def format_forecast_block(date, summary: dict, label: str = None) -> str:
    emoji = get_weather_emoji(summary["main"])
    date_str = format_date(date)
    header = f"📅 *{label}* — {date_str}" if label else f"📅 *{date_str}*"
    lines = [
        header,
        f"{emoji} {summary['description']}",
        f"🌡 Температура: *{summary['temp_min']}°...{summary['temp_max']}°C*",
        f"🤔 Відчувається: {summary['feels_min']}°...{summary['feels_max']}°C",
        f"💧 Вологість: {summary['humidity']}%",
        f"💨 Вітер: {summary['wind_speed']} м/с ({summary['wind_dir']})",
    ]
    if summary["rain"] > 0:
        lines.append(f"🌧 Дощ: {summary['rain']} мм")
    if summary["snow"] > 0:
        lines.append(f"❄️ Сніг: {summary['snow']} мм")
    return "\n".join(lines)


def build_message(days_data: dict) -> str:
    today = datetime.now().date()
    sorted_days = sorted(days_data.keys())

    blocks = []
    forecast_labels = ["Завтра", "Післязавтра", "Через 3 дні"]
    forecast_count = 0

    for i, day in enumerate(sorted_days[:4]):
        entries = days_data[day]
        summary = summarize_day(entries)

        if day == today:
            blocks.append(format_today_block(day, summary))
        else:
            label = forecast_labels[forecast_count] if forecast_count < len(forecast_labels) else None
            blocks.append(format_forecast_block(day, summary, label))
            forecast_count += 1

    blocks.append("")
    blocks.append(f"🕐 Оновлено: {datetime.now().strftime('%H:%M')} | Джерело: OpenWeatherMap")

    return "\n\n".join(blocks)


def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    print("✅ Повідомлення успішно надіслано!")
    return response.json()


def main():
    print(f"🌤 Отримую прогноз погоди для {CITY}...")
    data = fetch_weather()
    days_data = parse_forecast(data)
    message = build_message(days_data)
    print("📨 Надсилаю повідомлення в Telegram...")
    print("\n--- Превью повідомлення ---")
    print(message)
    print("---------------------------\n")
    send_telegram_message(message)


if __name__ == "__main__":
    main()
