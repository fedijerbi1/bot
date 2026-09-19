import os
import time
import requests
from datetime import datetime, date
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")

notion = Client(auth=NOTION_TOKEN)
last_update_id = 0
data_source_id = None


def send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })


def get_updates():
    global last_update_id
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    response = requests.get(url, params={
        "offset": last_update_id + 1,
        "timeout": 30
    })
    return response.json().get("result", [])


def get_data_source_id():
    global data_source_id
    if data_source_id:
        return data_source_id
    db = notion.databases.retrieve(database_id=NOTION_DB_ID)
    data_source_id = db["data_sources"][0]["id"]
    return data_source_id


def count_rows():
    ds_id = get_data_source_id()
    result = notion.data_sources.query(data_source_id=ds_id)
    return len(result["results"])


def create_sleep_row(sleep_iso):
    ds_id = get_data_source_id()
    n = count_rows() + 1
    page = notion.pages.create(
        parent={"type": "data_source_id", "data_source_id": ds_id},
        properties={
            "day": {"title": [{"text": {"content": f"day {n}"}}]},
            "date": {"date": {"start": date.today().isoformat()}},
            "sleep Time": {"date": {"start": sleep_iso}},
        }
    )
    return page["id"]


def find_open_row():
    ds_id = get_data_source_id()
    result = notion.data_sources.query(data_source_id=ds_id)
    rows = sorted(result["results"], key=lambda r: r.get("created_time", ""), reverse=True)
    for row in rows:
        props = row["properties"]
        sleep_t = props.get("sleep Time", {}).get("date")
        wake_up = props.get("wakeUp", {}).get("date")
        if sleep_t and not wake_up:
            return row["id"], props
    return None, None


def update_property(page_id, prop_name, value):
    notion.pages.update(
        page_id=page_id,
        properties={prop_name: {"date": {"start": value}}}
    )


def format_time(iso_string):
    if not iso_string:
        return "—"
    return iso_string[11:16]


def format_duration(sleep_iso, wake_iso):
    if not sleep_iso or not wake_iso:
        return "—"
    s = datetime.fromisoformat(sleep_iso)
    w = datetime.fromisoformat(wake_iso)
    diff = w - s
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    return f"{hours}h {minutes}min"


def handle_sleep():
    page_id, _ = find_open_row()
    if page_id:
        send("⚠️ You already logged sleep and haven't logged wake yet.")
        return
    now = datetime.now().astimezone().isoformat()
    try:
        create_sleep_row(now)
        send(f"😴 New row created.\nSleep logged: *{format_time(now)}*\nGood night.")
    except Exception as e:
        send(f"❌ Failed to create row: {e}")


def handle_wake():
    page_id, props = find_open_row()
    if not page_id:
        send("❌ No open sleep row. Send `/sleep` first tonight.")
        return
    now = datetime.now().astimezone().isoformat()
    update_property(page_id, "wakeUp", now)
    sleep_iso = props.get("sleep Time", {}).get("date", {})
    sleep_iso = sleep_iso.get("start") if sleep_iso else None
    duration = format_duration(sleep_iso, now)
    send(f"☀️ Wake logged: *{format_time(now)}*\n🛏 Sleep: *{duration}*")


def handle_today():
    page_id, props = find_open_row()
    if not page_id:
        send("No open row. Nothing logged yet tonight.")
        return
    sleep_iso = props.get("sleep Time", {}).get("date", {})
    sleep_iso = sleep_iso.get("start") if sleep_iso else None
    send(f"📅 *Open row*\n🛏 Sleep: {format_time(sleep_iso)}\n☀️ Wake: not yet")


def handle_help():
    send(
        "*Commands:*\n\n"
        "`/sleep` — create a new row, log sleep time\n"
        "`/wake` — fill in wake time on the open row\n"
        "`/today` — show open row\n"
        "`/help` — this message"
    )


def handle(text):
    text = text.strip().lower()
    if text == "/sleep":
        handle_sleep()
    elif text == "/wake":
        handle_wake()
    elif text == "/today":
        handle_today()
    elif text in ("/help", "/start"):
        handle_help()
    else:
        send("Unknown command. Try `/help`.")


def main():
    print("Bot is running. Press Ctrl+C to stop.")
    send("🤖 Bot online. Send `/help`.")
    while True:
        try:
            for update in get_updates():
                global last_update_id
                last_update_id = update["update_id"]
                message = update.get("message", {})
                text = message.get("text", "")
                if text:
                    print(f"Received: {text}")
                    handle(text)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()