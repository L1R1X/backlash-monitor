#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import html
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import sites

MSK = ZoneInfo("Europe/Moscow")
STATE_FILE = Path(__file__).resolve().with_name("state.json")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHATS = tuple(dict.fromkeys(
    chat.strip() for chat in os.environ.get("TELEGRAM_CHAT_ID", "").split(",")
    if chat.strip()
))


def load_state():
    try:
        with STATE_FILE.open(encoding="utf-8") as file:
            state = json.load(file)
    except FileNotFoundError:
        return {"items": {}}
    if not isinstance(state, dict):
        raise ValueError("Некорректный формат state.json")
    if "items" not in state:
        state = {"items": state}
    if not isinstance(state["items"], dict):
        raise ValueError("Некорректный список товаров в state.json")
    return state


def save_state(state):
    temporary = STATE_FILE.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
    temporary.replace(STATE_FILE)


def queue_messages(pending, heading, blocks):
    message = heading
    for block in blocks:
        if len(message) + len(block) + 2 > 3500 and message != heading:
            pending.append({"text": message, "delivered": []})
            message = heading
        message += "\n\n" + block
    if message != heading:
        pending.append({"text": message, "delivered": []})


def describe(item, price):
    return f"• {html.escape(item['name'])}\n  {price}\n  {html.escape(item['link'])}"


def scan():
    state = load_state()
    previous = state["items"]
    try:
        current = {item["uid"]: item for item in sites.fetch_backlash()}
    except (OSError, ValueError, RuntimeError) as error:
        print(f"BackLash: {error}", flush=True)
        return 1

    if not current or len(current) < len(previous) * 0.65:
        print(f"BackLash: подозрительно мало товаров ({len(current)} из {len(previous)}). "
              "Сохраняю предыдущую базу.", flush=True)
        return 1

    pending = state.setdefault("pending_notifications", [])
    if previous:
        new = [item for uid, item in current.items() if uid not in previous]
        cheaper = [
            (previous[uid]["price"], item)
            for uid, item in current.items()
            if uid in previous and previous[uid].get("price") is not None
            and item["price"] < previous[uid]["price"]
        ]
        queue_messages(pending, f"🆕 <b>BackLash — новинки TROUT ({len(new)})</b>",
                       (describe(item, f"¥{item['price']:,}") for item in new))
        queue_messages(pending, f"📉 <b>BackLash — снижение цены ({len(cheaper)})</b>",
                       (describe(item, f"¥{old_price:,} → ¥{item['price']:,}")
                        for old_price, item in cheaper))
        print(f"BackLash: новинок {len(new)}, снижений цены {len(cheaper)}")
    else:
        print("Первый запуск: сохраняю текущий ассортимент без уведомлений.")

    state.update(items=current, last_check=datetime.now(MSK).isoformat(timespec="seconds"))
    save_state(state)
    print(f"BackLash: сохранено {len(current)} товаров", flush=True)
    return 0


def send_one(chat, message):
    payload = urllib.parse.urlencode({
        "chat_id": chat, "text": message, "parse_mode": "HTML",
    }).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=payload,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response).get("ok") is True
    except urllib.error.HTTPError as error:
        print(f"Telegram: HTTP {error.code}")
    except (OSError, ValueError) as error:
        print(f"Telegram: {type(error).__name__}")
    return False


def deliver(test_message=False):
    if test_message:
        if not TOKEN or not CHATS:
            print("Задайте секреты TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID.")
            return 1
        results = [send_one(chat, "✅ BackLash: тестовое уведомление.") for chat in CHATS]
        print(f"Тестовое сообщение отправлено в {sum(results)} из {len(results)} чатов.")
        return int(not all(results))

    state = load_state()
    pending = state.get("pending_notifications", [])
    if not pending:
        return 0
    if not TOKEN or not CHATS:
        print("Задайте секреты TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID. Очередь сохранена.")
        return 1

    recipients = {
        hmac.new(TOKEN.encode(), chat.encode(), hashlib.sha256).hexdigest(): chat
        for chat in CHATS
    }
    blocked = set()
    remaining = []
    deadline = time.monotonic() + 45
    for entry in pending:
        delivered = set(entry["delivered"])
        for recipient, chat in recipients.items():
            if recipient in delivered or recipient in blocked or time.monotonic() >= deadline:
                continue
            if send_one(chat, entry["text"]):
                delivered.add(recipient)
                time.sleep(0.5)
            else:
                blocked.add(recipient)
        if not recipients.keys() <= delivered:
            remaining.append({"text": entry["text"], "delivered": sorted(delivered)})

    state["pending_notifications"] = remaining
    save_state(state)
    print(f"Telegram: в очереди осталось {len(remaining)} сообщений")
    return int(bool(blocked))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["scan", "deliver", "test-telegram"], default="scan", nargs="?")
    mode = parser.parse_args().mode
    raise SystemExit(scan() if mode == "scan" else deliver(test_message=mode == "test-telegram"))
