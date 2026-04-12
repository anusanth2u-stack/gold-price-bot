import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, time
import pytz
import uuid
import redis
import atexit

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

TOKEN = os.environ.get("TELEGRAM_TOKEN")
USER_ID = 5400949107

IST = pytz.timezone("Asia/Kolkata")

# ---------------- REDIS LOCK ----------------
REDIS_URL = os.environ.get("REDIS_URL")
LOCK_KEY = "gold_ai_bot_lock"
INSTANCE_ID = str(uuid.uuid4())
redis_client = redis.from_url(REDIS_URL) if REDIS_URL else None


def acquire_lock():
    if not redis_client:
        print("Redis not configured. Skipping duplicate-instance lock.")
        return True

    try:
        locked = redis_client.set(LOCK_KEY, INSTANCE_ID, nx=True, ex=3600)
        if locked:
            print("Redis lock acquired")
            return True

        current_owner = redis_client.get(LOCK_KEY)
        print(f"Another instance is active. Lock owner: {current_owner}")
        return False
    except Exception as e:
        print("Redis lock error:", e)
        return True


def refresh_lock():
    if not redis_client:
        return

    try:
        current_owner = redis_client.get(LOCK_KEY)
        if current_owner and current_owner.decode() == INSTANCE_ID:
            redis_client.expire(LOCK_KEY, 3600)
    except Exception as e:
        print("Redis refresh error:", e)


def release_lock():
    if not redis_client:
        return

    try:
        current_owner = redis_client.get(LOCK_KEY)
        if current_owner and current_owner.decode() == INSTANCE_ID:
            redis_client.delete(LOCK_KEY)
            print("Redis lock released")
    except Exception as e:
        print("Redis release error:", e)


atexit.register(release_lock)


# ---------------- PRICE SCRAPER ----------------
def extract_number(text):
    match = re.search(r"\d{1,3}(?:,\d{3})*", text)
    return float(match.group().replace(",", "")) if match else None


def get_price():
    # PRIMARY SOURCE
    try:
        url = "https://www.keralagold.com/kerala-gold-rate-per-gram.htm"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        latest_price = None
        today_price = None

        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) != 2:
                continue

            label = cols[0].get_text(" ", strip=True).lower()
            price = extract_number(cols[1].get_text(strip=True))

            if not price:
                continue

            latest_price = price

            if "today" in label:
                today_price = price

        return today_price or latest_price

    except Exception as e:
        print("KeralaGold Error:", e)

    # FALLBACK SOURCE
    try:
        url = "https://timesofindia.indiatimes.com/business/gold-rates-today/gold-price-in-bangalore.cms"
        res = requests.get(url)

        nums = re.findall(r"\d{1,3}(?:,\d{3})", res.text)
        for n in nums:
            val = float(n.replace(",", ""))
            if 3000 < val < 20000:
                return val

    except Exception as e:
        print("TOI Error:", e)

    return None


# ---------------- WINDOW CHECK ----------------
def is_window_open():
    now = datetime.now(IST)
    return now.hour in [10, 12, 14, 16, 18]


# ---------------- DASHBOARD ----------------
async def send_dashboard(context: ContextTypes.DEFAULT_TYPE):
    refresh_lock()

    price = get_price()

    if not price:
        await context.bot.send_message(chat_id=USER_ID, text="⚠️ No price data")
        return

    sheets.add_budget()

    history = sheets.get_history()
    trend, reason = logic.get_trend(price, history)
    sheets.log_data(price, trend)

    st_inv, st_cash, st_gold, st_val, st_profit, st_pct = sheets.get_st_metrics(price)
    lt_inv, lt_gold, lt_val, lt_profit, lt_pct = sheets.get_lt_metrics(price)

    avg_price = sheets.get_avg_buy_price()
    bought = sheets.already_bought()

    st_action, st_amt, st_reason = logic.short_term_ai(st_cash, st_pct, trend)
    lt_action, lt_amt, lt_reason = logic.long_term_ai(
        bought, price, avg_price, trend, history
    )

    total_val = st_val + lt_val
    total_profit = total_val - (st_inv + lt_inv)

    # ---------- ML ----------
    st_data = sheets.get_st_history()
    ml_low, ml_high, ml_signal, win_rate, extra = ml.get_prediction(
        history, st_data
    )

    msg = f"""
💎 GOLD AI PORTFOLIO ENGINE

💰 Price: ₹{price}

📊 Trend: {trend}
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
Gold: {round(st_gold,3)}g

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

Long-Term: {lt_action}
Reason: {lt_reason}

━━━━━━━━━━━━━━━
🤖 ML INSIGHTS

Range: ₹{ml_low} - ₹{ml_high}
Signal: {ml_signal}
Win Rate: {win_rate}%
{extra}
"""

    keyboard = []

    if lt_action == "BUY":
        keyboard.append(
            [InlineKeyboardButton("🟢 LT BUY ₹15000", callback_data="lt_buy")]
        )

    if st_action == "BUY":
        keyboard.append(
            [InlineKeyboardButton(f"🟢 BUY ₹{st_amt}", callback_data=f"buy_{st_amt}")]
        )

    if st_action == "SELL":
        keyboard.append(
            [InlineKeyboardButton(f"🔴 SELL ₹{st_amt}", callback_data=f"sell_{st_amt}")]
        )

    await context.bot.send_message(
        chat_id=USER_ID, text=msg, reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------- COMMANDS ----------------
async def start(update, context):
    refresh_lock()
    await send_dashboard(context)


async def force(update, context):
    refresh_lock()
    await update.message.reply_text("⚡ Force update")
    await send_dashboard(context)


# ---------------- BUTTON ----------------
async def button(update, context):
    refresh_lock()

    q = update.callback_query
    await q.answer()

    if not is_window_open():
        await q.message.reply_text("Window closed. Wait next slot.")
        return

    price = get_price()

    try:
        if q.data == "lt_buy":
            sheets.add_long(price)
            await q.message.reply_text("LT BUY DONE")

        elif "buy_" in q.data:
            amt = int(q.data.split("_")[1])
            sheets.add_short("BUY", amt, price)
            await q.message.reply_text(f"BUY {amt}")

        elif "sell_" in q.data:
            amt = int(q.data.split("_")[1])
            sheets.add_short("SELL", amt, price)
            await q.message.reply_text(f"SELL {amt}")

    except Exception as e:
        await q.message.reply_text(str(e))


# ---------------- SCHEDULER ----------------
async def window_job(context):
    refresh_lock()
    print("Scheduled Trigger")
    await send_dashboard(context)


# ---------------- TELEGRAM SESSION CLEANUP ----------------
async def post_init(app):
    try:
        print("Clearing old Telegram webhook/session...")
        await app.bot.delete_webhook(drop_pending_updates=True)
        print("Old Telegram session cleared")
    except Exception as e:
        print("deleteWebhook error:", e)


# ---------------- MAIN ----------------
def main():
    if not acquire_lock():
        print("Exiting: duplicate bot instance detected")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.post_init = post_init

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
            app.job_queue.run_daily(window_job, time=t)

    print("Bot running 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
