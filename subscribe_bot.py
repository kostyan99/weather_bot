import os
import json
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GIST_ID = os.environ["GIST_ID"]

GIST_URL = f"https://api.github.com/gists/{GIST_ID}"
GIST_FILENAME = "subscribers.json"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}


def get_subscribers() -> list[int]:
    response = requests.get(GIST_URL, headers=HEADERS, timeout=10)
    response.raise_for_status()
    content = response.json()["files"][GIST_FILENAME]["content"]
    return json.loads(content).get("subscribers", [])


def save_subscribers(subscribers: list[int]):
    payload = {
        "files": {
            GIST_FILENAME: {
                "content": json.dumps({"subscribers": subscribers}, indent=2)
            }
        }
    }
    requests.patch(GIST_URL, headers=HEADERS, json=payload, timeout=10)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = get_subscribers()

    if chat_id not in subscribers:
        subscribers.append(chat_id)
        save_subscribers(subscribers)
        await update.message.reply_text(
            "✅ Вы подписаны на прогноз погоды для Киева!\n\n"
            "🕐 Буду отправлять обновления каждые 3 часа.\n"
            "Чтобы отписаться — отправьте /stop"
        )
    else:
        await update.message.reply_text(
            "👍 Вы уже подписаны!\n"
            "Чтобы отписаться — отправьте /stop"
        )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = get_subscribers()

    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_subscribers(subscribers)
        await update.message.reply_text("❌ Вы отписаны от прогноза погоды.")
    else:
        await update.message.reply_text("Вы и так не подписаны. Отправьте /start чтобы подписаться.")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    print("🤖 Бот запущено. Чекаю на /start та /stop...")
    app.run_polling()


if __name__ == "__main__":
    main()
