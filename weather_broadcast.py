
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
CITY = "Киев"

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря"]

WIND_DIRECTIONS = {
    (0, 22.5): "С", (22.5, 67.5): "СВ", (67.5, 112.5): "В",
    (112.5, 157.5): "ЮВ", (157.5, 202.5): "Ю", (202.5, 247.5): "ЮЗ",
    (247.5, 292.5): "З", (292.5, 337.5): "СЗ", (337.5, 360): "С",
}

# Человеческие описания по главной категории
WEATHER_MAP = {
    "Thunderstorm": ("⛈️", "Гроза"),
    "Drizzle":      ("🌦️", "Небольшой дождь"),
    "Rain":         ("🌧️", "Дождь"),
    "Snow":         ("❄️", "Снег"),
    "Mist":         ("🌫️", "Туман"),
    "Smoke":        ("🌫️", "Дымка"),
    "Haze":         ("🌫️", "Дымка"),
    "Dust":         ("🌫️", "Пыль"),
    "Fog":          ("🌫️", "Туман"),
    "Sand":         ("🌫️", "Песчаная буря"),
    "Ash":          ("🌫️", "Пепел"),
    "Squall":       ("🌬️", "Шквал"),
    "Tornado":      ("🌪️", "Торнадо"),
    "Clear":        ("☀️", "Ясно"),
    "Clouds":       ("☁️", "Облачно"),
}


def describe(entry: dict) -> tuple:
    """Возвращает (emoji, описание) — без технических терминов типа 'рваные облака'."""
    main = entry["weather"][0]["main"]
    wid  = entry["weather"][0]["id"]

    # Облачность и ясно — детализируем по id
    if main in ("Clear", "Clouds"):
        if wid == 800:
            return "☀️", "Ясно"
        elif wid == 801:
            return "🌤️", "Малооблачно"
        elif wid == 802:
            return "⛅", "Переменная облачность"
        elif wid in (803, 804):
            return "☁️", "Пасмурно"

    # Дождь — детализируем интенсивность
    if main == "Rain":
        if wid in (500, 520):
            return "🌦️", "Небольшой дождь"
        elif wid in (501, 521):
            return "🌧️", "Умеренный дождь"
        elif wid in (502, 503, 504, 522):
            return "🌧️", "Сильный дождь"
        elif wid == 511:
            return "🌨️", "Ледяной дождь"
        return "🌧️", "Дождь"

    # Снег — детализируем
    if main == "Snow":
        if wid == 600:
            return "🌨️", "Небольшой снег"
        elif wid == 601:
            return "❄️", "Снег"
        elif wid == 602:
            return "❄️", "Сильный снег"
        elif wid in (611, 612, 613):
            return "🌨️", "Мокрый снег"
        elif wid in (615, 616):
            return "🌨️", "Дождь со снегом"
        return "❄️", "Снег"

    # Гроза
    if main == "Thunderstorm":
        if wid in (200, 210, 230):
            return "⛈️", "Гроза с небольшим дождём"
        elif wid in (201, 211, 231):
            return "⛈️", "Гроза"
        elif wid in (202, 212, 232):
            return "⛈️", "Сильная гроза"
        return "⛈️", "Гроза"

    return WEATHER_MAP.get(main, ("🌡️", "Переменная погода"))


def get_wind_dir(degrees: float) -> str:
    for (lo, hi), d in WIND_DIRECTIONS.items():
        if lo <= degrees < hi:
            return d
    return "—"


def format_date(dt) -> str:
    return f"{WEEKDAYS[dt.weekday()]}, {dt.day} {MONTHS[dt.month - 1]}"


# ── Подписчики ───────────────────────────────────────────────────────────────

def get_subscribers() -> list:
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    content = r.json()["files"]["subscribers.json"]["content"]
    return json.loads(content).get("subscribers", [])


# ── Погода ───────────────────────────────────────────────────────────────────

def fetch_forecast() -> dict:
    r = requests.get(
        "https://api.openweathermap.org/data/2.5/forecast",
        params={"lat": LAT, "lon": LON, "appid": WEATHER_API_KEY,
                "units": "metric", "lang": "ru", "cnt": 40},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def group_by_day(data: dict) -> dict:
    days = {}
    for entry in data["list"]:
        key = datetime.fromtimestamp(entry["dt"]).date()
        days.setdefault(key, []).append(entry)
    return days


def today_block(date, entries: list) -> str:
    """Сегодня: подробная сводка + температура по часам."""
    now = datetime.now()

    temps  = [e["main"]["temp"] for e in entries]
    feels  = [e["main"]["feels_like"] for e in entries]
    humid  = [e["main"]["humidity"] for e in entries]
    winds  = [e["wind"]["speed"] for e in entries]
    wind_d = entries[len(entries) // 2]["wind"].get("deg", 0)
    rain   = sum(e.get("rain", {}).get("3h", 0) for e in entries)
    snow   = sum(e.get("snow", {}).get("3h", 0) for e in entries)

    # Самое частое явление за день
    mains = [e["weather"][0]["main"] for e in entries]
    dominant = max(entries, key=lambda e: mains.count(e["weather"][0]["main"]))
    emoji, desc = describe(dominant)

    lines = [
        f"📍 *{CITY} — {format_date(date)}*",
        f"{emoji} {desc}",
        f"🌡 Температура: *{round(min(temps))}°...{round(max(temps))}°C*",
        f"🤔 Ощущается: {round(min(feels))}°...{round(max(feels))}°C",
        f"💧 Влажность: {round(sum(humid) / len(humid))}%",
        f"💨 Ветер: {round(max(winds))} м/с ({get_wind_dir(wind_d)})",
    ]
    if rain > 0:
        lines.append(f"🌧 Осадки (дождь): {round(rain, 1)} мм")
    if snow > 0:
        lines.append(f"❄️ Осадки (снег): {round(snow, 1)} мм")

    # Почасовой — только будущие слоты сегодня
    hourly = [e for e in entries if datetime.fromtimestamp(e["dt"]) >= now]
    if hourly:
        lines.append("")
        lines.append("🕐 *По часам сегодня:*")
        for e in hourly:
            dt_h  = datetime.fromtimestamp(e["dt"])
            t     = round(e["main"]["temp"])
            hr_emoji, _ = describe(e)
            sign  = "+" if t > 0 else ""
            lines.append(f"  {dt_h.strftime('%H:00')}  {hr_emoji}  {sign}{t}°C")

    return "\n".join(lines)


def future_block(date, entries: list, label: str) -> str:
    """Следующие дни: только сводка без почасовки."""
    temps  = [e["main"]["temp"] for e in entries]
    feels  = [e["main"]["feels_like"] for e in entries]
    humid  = [e["main"]["humidity"] for e in entries]
    winds  = [e["wind"]["speed"] for e in entries]
    wind_d = entries[len(entries) // 2]["wind"].get("deg", 0)
    rain   = sum(e.get("rain", {}).get("3h", 0) for e in entries)
    snow   = sum(e.get("snow", {}).get("3h", 0) for e in entries)

    mains = [e["weather"][0]["main"] for e in entries]
    dominant = max(entries, key=lambda e: mains.count(e["weather"][0]["main"]))
    emoji, desc = describe(dominant)

    lines = [
        f"📅 *{label}* — {format_date(date)}",
        f"{emoji} {desc}",
        f"🌡 Температура: *{round(min(temps))}°...{round(max(temps))}°C*",
        f"🤔 Ощущается: {round(min(feels))}°...{round(max(feels))}°C",
        f"💧 Влажность: {round(sum(humid) / len(humid))}%",
        f"💨 Ветер: {round(max(winds))} м/с ({get_wind_dir(wind_d)})",
    ]
    if rain > 0:
        lines.append(f"🌧 Дождь: {round(rain, 1)} мм")
    if snow > 0:
        lines.append(f"❄️ Снег: {round(snow, 1)} мм")
    return "\n".join(lines)


def build_message() -> str:
    data = fetch_forecast()
    days = group_by_day(data)
    today = datetime.now().date()
    sorted_days = sorted(d for d in days if d >= today)[:4]

    labels = ["Завтра", "Послезавтра", "Через 3 дня"]
    blocks = []

    for i, day in enumerate(sorted_days):
        if i == 0:
            blocks.append(today_block(day, days[day]))
        else:
            blocks.append(future_block(day, days[day], labels[i - 1]))

    blocks.append(f"🕐 Обновлено: {datetime.now().strftime('%H:%M')} | OpenWeatherMap")
    return "\n\n".join(blocks)


# ── Рассылка ─────────────────────────────────────────────────────────────────

def send_to(chat_id: int, text: str) -> bool:
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )
    return r.ok


def main():
    subscribers = get_subscribers()
    if not subscribers:
        print("⚠️  Нет подписчиков — некому отправлять.")
        return

    print(f"👥 Подписчиков: {len(subscribers)}")
    message = build_message()
    print(message)

    ok, fail = 0, 0
    for chat_id in subscribers:
        if send_to(chat_id, message):
            ok += 1
        else:
            fail += 1

    print(f"✅ Отправлено: {ok} | ❌ Ошибок: {fail}")


if __name__ == "__main__":
    main()
