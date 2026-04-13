import os
import requests
from datetime import datetime, time
import pytz
import json
import threading
import atexit

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

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
        print("Another instance running. Exit.")
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
    data[key] = {
        "value": value,
        "time": datetime.now().timestamp()
    }
    save_cache(data)


def get_cached(key, expiry):
    data = load_cache().get(key)
    if not data:
        return None
    if datetime.now().timestamp() - data["time"] > expiry:
        return None
    return data["value"]


# ================= PRICE =================

# GOLD (stable Kerala-style fallback)
def get_gold_price():
    try:
        url = "https://www.goodreturns.in/gold-rates/"
        res = requests.get(url, timeout=5)
        text = res.text

        import re
        matches = re.findall(r"\d{4,5}", text)

        for m in matches:
            val = float(m)
            if 5000 < val < 8000:
                set_cached("gold", val)
                return val, "LIVE"

    except Exception as e:
        print("Gold error:", e)

    cached = get_cached("gold", 1800)
    if cached:
        return cached, "CACHE"

    return 6000, "DEFAULT"


# GOLDBEES (FIXED YAHOO)
def get_goldbees_price():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GOLDBEES.NS"
        res = requests.get(url, timeout=5)
        data = res.json()

        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]

        if price and 50 < price < 500:
            set_cached("bees", price)
            return price, "LIVE"

    except Exception as e:
        print("Yahoo error:", e)

    cached = get_cached("bees", 600)
    if cached:
        return cached, "CACHE"

    return 120, "DEFAULT"


# ================= ALERT =================
def check_price_alert(name, new_price, key):
    old_data = load_cache().get(key)
    if not old_data:
        return None

    old_price = old_data["value"]
    change = ((new_price - old_price) / old_price) * 100

    if abs(change) >= 1:
        return f"""
🚨 {name} ALERT

Old: ₹{round(old_price,2)}
New: ₹{round(new_price,2)}
Change: {round(change,2)}%
"""
    return None


# ================= WINDOW =================
def is_window_open():
    return datetime.now(IST).hour in [10, 12, 14, 16, 18]


def extract_score(extra):
    try:
        return int(extra.split("Score:")[1].split("%")[0])
    except:
        return 50


# ================= DASHBOARD =================
async def send_dashboard(context: ContextTypes.DEFAULT_TYPE):

    gold_price, gold_src = get_gold_price()
    bees_price, bees_src = get_goldbees_price()

    # ALERTS
    alert1 = check_price_alert("GOLD", gold_price, "gold")
    alert2 = check_price_alert("GOLDBEES", bees_price, "bees")

    if alert1:
        await context.bot.send_message(chat_id=USER_ID, text=alert1)

    if alert2:
        await context.bot.send_message(chat_id=USER_ID, text=alert2)

    gold_history = sheets.get_gold_history()
    bees_history = sheets.get_bees_history()

    gold_trend, _ = logic.get_trend(gold_price, gold_history)
    bees_trend, reason = logic.get_trend(bees_price, bees_history)

    st_inv, st_cash, st_units, st_val, st_profit, st_pct = sheets.get_st_metrics(bees_price)
    lt_inv, lt_gold, lt_val, lt_profit, lt_pct = sheets.get_lt_metrics(gold_price)

    avg_price = sheets.get_avg_buy_price()
    bought = sheets.already_bought()

    st_data = sheets.get_st_history()
    ml_low, ml_high, ml_signal, win_rate, extra = ml.short_term_ml(bees_history, st_data)

    score = extract_score(extra)

    st_action, st_amt, st_reason, sl, tgt = logic.short_term_ai(
        st_cash, st_pct, bees_trend, score, win_rate, bees_price
    )

    lt_action, lt_amt, lt_reason = logic.long_term_ai(
        bought, gold_price, avg_price, gold_trend, gold_history
    )

    sheets.log_data(gold_price, gold_trend, score, bees_price, bees_trend, score)

    total_val = st_val + lt_val
    total_profit = total_val - (st_inv + lt_inv)

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

P/L: ₹{int(lt_profit)} ({round(lt_pct,2)}%)

━━━━━━━━━━━━━━━
🔴 SHORT TERM

Cash: ₹{int(st_cash)}
Units: {round(st_units,2)}

Value: ₹{int(st_val)}
P/L: ₹{int(st_profit)}
Return: {round(st_pct,2)}%
"""

    keyboard = []

    if lt_action == "BUY":
        keyboard.append([InlineKeyboardButton("🟢 LT BUY ₹15000", callback_data="lt_buy")])

    if st_action == "BUY":
        keyboard.append([InlineKeyboardButton(f"🟢 BUY ₹{st_amt}", callback_data=f"buy_{st_amt}")])

    if st_action == "SELL":
        keyboard.append([InlineKeyboardButton(f"🔴 SELL ₹{st_amt}", callback_data=f"sell_{st_amt}")])

    await context.bot.send_message(chat_id=USER_ID, text=msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ================= BUTTON =================
async def button(update, context):
    q = update.callback_query
    await q.answer()

    if not is_window_open():
        await q.message.reply_text("Window closed")
        return

    gold_price, _ = get_gold_price()
    bees_price, _ = get_goldbees_price()

    try:
        if q.data == "lt_buy":
            sheets.add_long(gold_price)
            await q.message.reply_text("LT BUY DONE")

        elif "buy_" in q.data:
            amt = int(q.data.split("_")[1])
            sheets.add_short("BUY", amt, bees_price)
            await q.message.reply_text(f"BUY ₹{amt}")

        elif "sell_" in q.data:
            amt = int(q.data.split("_")[1])
            sheets.add_short("SELL", amt, bees_price)
            await q.message.reply_text(f"SELL ₹{amt}")

    except Exception as e:
        await q.message.reply_text(str(e))


# ================= COMMANDS =================
async def start(update, context):
    await send_dashboard(context)


async def force(update, context):
    await update.message.reply_text("⚡ Force update")
    await send_dashboard(context)


# ================= SCHEDULER =================
async def job(context):
    await send_dashboard(context)


# ================= MAIN =================
def main():
    create_lock()

    app = ApplicationBuilder().token(TOKEN).build()

    async def post_init(app):
        await app.bot.delete_webhook(drop_pending_updates=True)

    app.post_init = post_init

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("force", force))
    app.add_handler(CallbackQueryHandler(button))

    times = [
        time(10,0,tzinfo=IST),
        time(12,0,tzinfo=IST),
        time(14,0,tzinfo=IST),
        time(16,0,tzinfo=IST),
        time(18,0,tzinfo=IST),
    ]

    if app.job_queue:
        for t in times:
            app.job_queue.run_daily(job, time=t)

    print("Bot running 🚀")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()