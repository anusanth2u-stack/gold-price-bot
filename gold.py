import requests
from bs4 import BeautifulSoup
import re
import os
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

URL = "https://www.keralagold.com/kerala-gold-rate-per-gram.htm"
BUDGET = 15000


def get_gold_price():
    try:
        res = requests.get(URL, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text()

        match = re.search(r"Today\s*»Rs\.\s*([\d,]+)", text)
        if match:
            return int(match.group(1).replace(",", ""))
    except Exception as e:
        print("Error fetching price:", e)

    return None


def send_telegram(message):
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    CHAT_ID = "5400949107"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.get(url, params={"chat_id": CHAT_ID, "text": message})


def setup_google_credentials():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")

    with open("credentials.json", "w") as f:
        f.write(creds_json)


def save_to_sheets(price, trend, score):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)

    sheet = client.open("Gold Tracker").sheet1

    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    sheet.append_row([date, price, trend, score])


def analyze(price, last_price):
    trend = "FLAT"

    if last_price:
        if price < last_price:
            trend = "DOWN"
        elif price > last_price:
            trend = "UP"

    score = 50

    if trend == "DOWN":
        score += 20
    elif trend == "UP":
        score -= 10

    today = datetime.now().day
    if 20 <= today <= 22:
        score += 30

    return trend, min(score, 100)


def score_bar(score):
    filled = int(score / 10)
    return "🟩" * filled + "⬜" * (10 - filled)


if __name__ == "__main__":
    setup_google_credentials()

    price = get_gold_price()

    if not price:
        print("Price not found")
        exit()

    # Simple last price tracking (temporary)
    last_price = None

    if os.path.exists("last_price.txt"):
        with open("last_price.txt", "r") as f:
            last_price = int(f.read())

    trend, score = analyze(price, last_price)

    grams = round(BUDGET / price, 2)

    message = (
        f"💰 Gold AI Advisor\n\n"
        f"Price: ₹{price}\n"
        f"Trend: {trend}\n"
        f"📊 Score: {score}/100\n"
        f"{score_bar(score)}\n\n"
        f"₹{BUDGET} → ~{grams}g\n"
        f"Advice: {'BUY' if score > 70 else 'WAIT'}"
    )

    send_telegram(message)

    save_to_sheets(price, trend, score)

    with open("last_price.txt", "w") as f:
        f.write(str(price))
