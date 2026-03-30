import requests
import os
import logging

# --- KONFIGURACJA ---
SLACK_TOKEN = os.environ["SLACK_TOKEN"]
OPENROUTER_KEY = os.environ["OPENROUTER_KEY"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

# --- PLIKI ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "logi.txt")

# --- LOGI ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

HEADERS = {"Authorization": f"Bearer {OPENROUTER_KEY}"}


def send_slack_msg(text):
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}", "Content-type": "application/json"}
    data = {"channel": CHANNEL_ID, "text": text}
    try:
        requests.post(url, headers=headers, json=data)
        logging.info("Wysłano raport na Slacka.")
    except Exception as e:
        logging.error(f"Błąd Slacka: {e}")


def get_credits():
    """Returns (total_credits, total_usage) or (None, None) on error."""
    try:
        resp = requests.get("https://openrouter.ai/api/v1/credits", headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()["data"]
            return float(data["total_credits"]), float(data["total_usage"])
        logging.error(f"Błąd credits: {resp.text}")
    except Exception as e:
        logging.error(f"Wyjątek credits: {e}")
    return None, None


def get_keys():
    """Returns list of keys with non-zero daily usage."""
    try:
        resp = requests.get("https://openrouter.ai/api/v1/keys", headers=HEADERS)
        if resp.status_code == 200:
            keys = resp.json().get("data", [])
            return [k for k in keys if (k.get("usage_daily") or 0) > 0]
        logging.error(f"Błąd keys: {resp.text}")
    except Exception as e:
        logging.error(f"Wyjątek keys: {e}")
    return []


def get_daily_usage(date_str):
    """Aggregated usage ($) for a single date across all models."""
    try:
        resp = requests.get(
            "https://openrouter.ai/api/v1/activity",
            headers=HEADERS,
            params={"date": date_str},
        )
        if resp.status_code == 200:
            entries = resp.json().get("data", [])
            return sum(e.get("usage", 0) for e in entries)
        logging.error(f"Błąd activity ({date_str}): {resp.text}")
    except Exception as e:
        logging.error(f"Wyjątek activity ({date_str}): {e}")
    return 0.0


def main():
    logging.info("=== START RAPORTU ===")

    total_credits, total_usage = get_credits()
    if total_credits is None:
        return

    remaining = total_credits - total_usage

    keys = get_keys()
    today_total = sum(k.get("usage_daily") or 0 for k in keys) if keys else 0

    key_lines = []
    for k in keys:
        name = k["name"]
        daily = k.get("usage_daily") or 0
        weekly = k.get("usage_weekly") or 0
        limit = k.get("limit")
        limit_str = f" | limit: ${limit:.2f}" if limit else " | bez limitu"
        key_lines.append(f"  • *{name}*: dziś ${daily:.4f} | tydzień ${weekly:.4f}{limit_str}")

    keys_section = "\n🔑 Zużycie per klucz (dzisiaj):\n" + "\n".join(key_lines) if key_lines else ""

    message = (
        f"📊 Raport OpenRouter\n\n"
        f"💵 Zużycie dzisiaj: *${today_total:.4f}*\n"
        + keys_section + "\n\n"
        f"💰 Pozostałe środki: *${remaining:.2f}*\n"
        f"📈 Całkowite zużycie: *${total_usage:.4f}*"
    )

    if remaining < 2.0:
        message += "\n\n🔴 *ALARM: Mało środków!*"
    print(message)
    # send_slack_msg(message)
    logging.info(f"Koniec. Pozostało: ${remaining:.2f}, Zużycie: ${total_usage:.4f}")


if __name__ == "__main__":
    main()
