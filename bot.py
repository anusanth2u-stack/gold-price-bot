import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, time
import pytz
import json
import atexit
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import logic
import sheets
import ml

# ================= CONFIG =================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
USER_ID = 5400949107
IST = pytz.timezone("Asia/Kolkata")

CACHE_FILE = "price_cache.json"
LOCK_FILE = "bot.lock"


# ================= LOCK (PREVENT DUPLICATE) =================
def create_lock():
    if os.path.exists(LOCK_FILE):
        print("⚠️ Another bot instance already running. Exiting.")
        exit()

    with open(LOCK_FILE, "w") as f:
        f.write("running")


def remove_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)


atexit.register(remove_lock)


# ================= HEALTH CHECK =================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")


def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Health server running on port {port}")
    server.serve_forever()


# ================= CACHE =================
def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)


def get_cached(key):
    return load_cache().get(key)


def set_cached(key, value):
    data = load_cache()
    data[key] = value
    save_cache(data)


# ================= PRICE ENGINE =================
def get_gold_price():
    try:
        url = "https://www.keralagold.com/kerala-gold-rate-per-gram.htm"
        res = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) == 2:
                match = re.search(r"\d{1,3}(?:,\d{3})*", cols[1].text)
                if match:
                    price = float(match.group().replace(",", ""))
                    set_cached("gold", price)
                    return price
    except:
        pass

    try:
        url = "https://timesofindia.indiatimes.com/business/gold-rates-today/gold-price-in-bangalore.cms"
        res = requests.get(url, timeout=10)
        text = BeautifulSoup(res.text, "html.parser").get_text()

        matches = re.findall(r"₹?\s?\d{2,3},\d{3}", text)
        for m in matches:
            val = float(m.replace("₹", "").replace(",", ""))
            if 12000 < val < 20000:
                set_cached("gold", val)
                return val
    except:
        pass

    return get_cached("gold") or 14000


def get_goldbees_price():
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=GOLDBEES.NS"
        res = requests.get(url, timeout=10)
        data = res.json()
        price = data["quoteResponse"]["result"][0]["regularMarketPrice"]

        if price:
            set_cached("bees", price)
            return price
    except:
        pass

    try:
        url = "https://www.nseindia.com/get-quotes/equity?symbol=GOLDBEES"
        res = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=10)

        match = re.search(r"\d+\.\d+", res.text)
        if match:
            price = float(match.group())
            set_cached("bees", price)
            return price
    except:
        pass

    return get_cached("bees") or 60


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

    gold_price = get_gold_price()
    goldbees_price = get_goldbees_price()

    gold_history = sheets.get_gold_history()
    bees_history = sheets.get_bees_history()

    gold_trend, _ = logic.get_trend(gold_price, gold_history)
    bees_trend, reason = logic.get_trend(goldbees_price, bees_history)

    st_inv, st_cash, st_units, st_val, st_profit, st_pct = sheets.get_st_metrics(goldbees_price)
    lt_inv, lt_gold, lt_val, lt_profit, lt_pct = sheets.get_lt_metrics(gold_price)

    avg_price = sheets.get_avg_buy_price()
    bought = sheets.already_bought()

    st_data = sheets.get_st_history()
    ml_low, ml_high, ml_signal, win_rate, extra = ml.short_term_ml(bees_history, st_data)

    score = extract_score(extra)

    lt_trend_ml, lt_valn, lt_zone, lt_conf = ml.long_term_ml(
        gold_history, avg_price, gold_price
    )

    st_action, st_amt, st_reason, sl, tgt = logic.short_term_ai(
        st_cash, st_pct, bees_trend, score, win_rate, goldbees_price
    )

    lt_action, lt_amt, lt_reason = logic.long_term_ai(
        bought, gold_price, avg_price, gold_trend, gold_history
    )

    sheets.log_data(
        gold_price,
        gold_trend,
        score,
        goldbees_price,
        bees_trend,
        score
    )

    total_val = st_val + lt_val
    total_profit = total_val - (st_inv + lt_inv)

    msg = f"""
💎 GOLD AI PORTFOLIO ENGINE

💰 Gold: ₹{gold_price}
📈 GoldBees: ₹{goldbees_price}

📊 Trend (Gold): {gold_trend}
📊 Trend (GoldBees): {bees_trend}
📉 {reason}

━━━━━━━━━━━━━━━
🟢 LONG TERM

Invested: ₹{int(lt_inv)}
Gold: {round(lt_gold,3)}g
Value: ₹{int(lt_val)}

P/L: ₹{int(lt_profit)} ({round(lt_pct,2)}%)

Action: {lt_action}
Reason: {lt_reason}

━━━━━━━━━━━━━━━
🔴 SHORT TERM

Cash: ₹{int(st_cash)}
Units: {round(st_units,2)}

Value: ₹{int(st_val)}
P/L: ₹{int(st_profit)}
Return: {round(st_pct,2)}%

━━━━━━━━━━━━━━━
💎 TOTAL

Value: ₹{int(total_val)}
P/L: ₹{int(total_profit)}

━━━━━━━━━━━━━━━
🤖 AI DECISION

Short-Term: {st_action} ₹{st_amt}
Reason: {st_reason}
"""

    if sl:
        msg += f"\nStop Loss: ₹{sl}\nTarget: ₹{tgt}\n"

    msg += f"""
Long-Term: {lt_action}
Reason: {lt_reason}

━━━━━━━━━━━━━━━
🤖 ML INSIGHTS (SHORT TERM)

Range: ₹{ml_low} - ₹{ml_high}
Signal: {ml_signal}
Win Rate: {win_rate}%
{extra}

━━━━━━━━━━━━━━━
🤖 ML INSIGHTS (LONG TERM)

Trend Strength: {lt_trend_ml}
Valuation: {lt_valn}
Accumulation Zone: ₹{lt_zone}
Confidence: {lt_conf}
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

    gold_price = get_gold_price()
    goldbees_price = get_goldbees_price()

    try:
        if q.data == "lt_buy":
            sheets.add_long(gold_price)
            await q.message.reply_text("LT BUY DONE")

        elif "buy_" in q.data:
            amt = int(q.data.split("_")[1])
            sheets.add_short("BUY", amt, goldbees_price)
            await q.message.reply_text(f"BUY ₹{amt}")

        elif "sell_" in q.data:
            amt = int(q.data.split("_")[1])
            sheets.add_short("SELL", amt, goldbees_price)
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
    print("Scheduled Trigger")
    await send_dashboard(context)


# ================= MAIN =================
def main():
    create_lock()

    threading.Thread(target=start_health_server).start()

    while True:
        try:
            app = ApplicationBuilder().token(TOKEN).build()

            app.post_init = lambda app: app.bot.delete_webhook(drop_pending_updates=True)

            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("force", force))
            app.add_handler(CallbackQueryHandler(button))

            times = [
                time(10, 0, tzinfo=IST),
                time(12, 0, tzinfo=IST),
                time(14, 0, tzinfo=IST),
                time(16, 0, tzinfo=IST),
                time(18, 0, tzinfo=IST),
            ]

            if app.job_queue:
                for t in times:
                    app.job_queue.run_daily(job, time=t)

            print("Bot running 🚀")
            app.run_polling(drop_pending_updates=True)

        except Exception as e:
            print("Bot crashed, restarting...", e)


if __name__ == "__main__":
    main()