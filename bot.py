import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, time
import pytz
import json
import atexit

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

import logic
import sheets
import ml

# ================= CONFIG =================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
USER_ID = 5400949107
IST = pytz.timezone("Asia/Kolkata")

CACHE_FILE = "price_cache.json"
LOCK_FILE = "bot.lock"


# ================= LOCK =================
def create_lock():
    if os.path.exists(LOCK_FILE):
        exit()
    open(LOCK_FILE, "w").write("running")


def remove_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

atexit.register(remove_lock)


# ================= CACHE =================
def load_cache():
    try:
        return json.load(open(CACHE_FILE))
    except:
        return {}

def save_cache(data):
    json.dump(data, open(CACHE_FILE, "w"))

def set_cached(key, value):
    data = load_cache()
    data[key] = {"value": value, "time": datetime.now().timestamp()}
    save_cache(data)

def get_cached(key, expiry):
    data = load_cache().get(key)
    if not data:
        return None
    if datetime.now().timestamp() - data["time"] > expiry:
        return None
    return data["value"]


# ================= GOLD =================
def get_gold_price():
    # 1️⃣ Kerala Gold
    try:
        url = "https://www.keralagold.com/kerala-gold-rate-per-gram.htm"
        r = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text()

        matches = re.findall(r"\d{4,5}", text)

        for m in matches:
            val = float(m)
            if 12000 < val < 20000:
                set_cached("gold", val)
                return val, "LIVE"
    except:
        pass

    # 2️⃣ IndiaGoldRate fallback
    try:
        url = "https://www.indiagoldrate.co.in/22k-gold-rate.php"
        r = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")

        text = soup.get_text()
        matches = re.findall(r"\d{4,5}", text)

        for m in matches:
            val = float(m)
            if 5000 < val < 8000:
                set_cached("gold", val)
                return val, "LIVE"
    except:
        pass

    cached = get_cached("gold", 1800)
    if cached:
        return cached, "CACHE"

    return 6000, "DEFAULT"


# ================= GOLDBEES =================
def get_goldbees_price():
    # 1️⃣ Google Finance
    try:
        url = "https://www.google.com/finance/quote/GOLDBEES:NSE"
        r = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")

        text = soup.get_text()
        matches = re.findall(r"\d+\.\d+", text)

        for m in matches:
            val = float(m)
            if 50 < val < 500:
                set_cached("bees", val)
                return val, "LIVE"
    except:
        pass

    # 2️⃣ MoneyControl fallback
    try:
        url = "https://www.moneycontrol.com/india/stockpricequote/gold-etf/nipponindiaetfgoldbees/GBE"
        r = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")

        text = soup.get_text()
        matches = re.findall(r"\d+\.\d+", text)

        for m in matches:
            val = float(m)
            if 50 < val < 500:
                set_cached("bees", val)
                return val, "LIVE"
    except:
        pass

    cached = get_cached("bees", 600)
    if cached:
        return cached, "CACHE"

    return 120, "DEFAULT"


# ================= ALERT =================
def check_price_alert(name, new_price, key):
    old = load_cache().get(key)
    if not old:
        return None

    change = ((new_price - old["value"]) / old["value"]) * 100

    if abs(change) >= 1:
        return f"🚨 {name} ALERT\nOld: ₹{old['value']}\nNew: ₹{new_price}\nChange: {round(change,2)}%"

    return None


# ================= WINDOW =================
def is_window_open():
    return datetime.now(IST).hour in [10,12,14,16,18]


# ================= DASHBOARD =================
async def send_dashboard(context):

    gold_price, gold_src = get_gold_price()
    bees_price, bees_src = get_goldbees_price()

    alert = check_price_alert("GOLDBEES", bees_price, "bees")
    if alert:
        await context.bot.send_message(chat_id=USER_ID, text=alert)

    gold_history = sheets.get_gold_history()
    bees_history = sheets.get_bees_history()

    gold_trend, _ = logic.get_trend(gold_price, gold_history)
    bees_trend, reason = logic.get_trend(bees_price, bees_history)

    st_inv, st_cash, st_units, st_val, st_profit, st_pct = sheets.get_st_metrics(bees_price)
    lt_inv, lt_gold, lt_val, lt_profit, lt_pct = sheets.get_lt_metrics(gold_price)

    msg = f"""
💎 GOLD AI PORTFOLIO ENGINE

💰 Gold: ₹{gold_price} ({gold_src})
📈 GoldBees: ₹{bees_price} ({bees_src})

📊 Trend (Gold): {gold_trend}
📊 Trend (GoldBees): {bees_trend}
📉 {reason}

━━━━━━━━━━━━━━━
🟢 LONG TERM
Invested: ₹{int(lt_inv)}
Gold: {round(lt_gold,3)}g
Value: ₹{int(lt_val)}

━━━━━━━━━━━━━━━
🔴 SHORT TERM
Cash: ₹{int(st_cash)}
Units: {round(st_units,2)}
Value: ₹{int(st_val)}
"""

    await context.bot.send_message(chat_id=USER_ID, text=msg)


# ================= COMMANDS =================
async def start(update, context):
    await send_dashboard(context)

async def force(update, context):
    await send_dashboard(context)


# ================= MAIN =================
def main():
    create_lock()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("force", force))

    print("Bot running 🚀")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()