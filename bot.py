import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import logic
import sheets

TOKEN = os.environ.get("TELEGRAM_TOKEN")
USER_ID = 5400949107


# ---------------- PRICE ----------------
def extract_number(text):
    match = re.search(r"\d{1,3}(?:,\d{3})*", text)
    if match:
        return float(match.group().replace(",", ""))
    return None


def get_price():
    try:
        url = "https://www.keralagold.com/kerala-gold-rate-per-gram.htm"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        rows = soup.find_all("tr")
        today_price = None
        latest_price = None

        for row in rows:
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

    except:
        pass

    try:
        url = "https://timesofindia.indiatimes.com/business/gold-rates-today/gold-price-in-bangalore.cms"
        res = requests.get(url)

        nums = re.findall(r"\d{1,3}(?:,\d{3})", res.text)
        for n in nums:
            val = float(n.replace(",", ""))
            if 3000 < val < 20000:
                return val
    except:
        pass

    return None


# ---------------- WINDOW CHECK ----------------
def is_window_open():
    now = datetime.now()
    return now.hour in [10, 12, 14, 16, 18]


# ---------------- DASHBOARD ----------------
async def send_dashboard(context: ContextTypes.DEFAULT_TYPE):
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
    lt_action, lt_amt, lt_reason = logic.long_term_ai(bought, price, avg_price, trend, history)

    total_val = st_val + lt_val
    total_profit = total_val - (st_inv + lt_inv)

    msg = f"""
💎 GOLD AI

Price: ₹{price}

Trend: {trend}
{reason}

LONG TERM → {lt_action}
SHORT TERM → {st_action}

TOTAL VALUE: ₹{int(total_val)}
P/L: ₹{int(total_profit)}
"""

    keyboard = []

    if lt_action == "BUY":
        keyboard.append([InlineKeyboardButton("LT BUY", callback_data="lt_buy")])

    if st_action == "BUY":
        keyboard.append([InlineKeyboardButton("BUY", callback_data=f"buy_{st_amt}")])

    if st_action == "SELL":
        keyboard.append([InlineKeyboardButton("SELL", callback_data=f"sell_{st_amt}")])

    await context.bot.send_message(chat_id=USER_ID, text=msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------- BUTTON ----------------
async def button(update, context):
    q = update.callback_query
    await q.answer()

    if not is_window_open():
        await q.message.reply_text("Window closed. Wait next slot.")
        return

    price = get_price()

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


# ---------------- SCHEDULER ----------------
async def window_job(context):
    print("Window triggered")
    await send_dashboard(context)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", send_dashboard))
    app.add_handler(CallbackQueryHandler(button))

    if app.job_queue:
        times = [time(10,0), time(12,0), time(14,0), time(16,0), time(18,0)]

        for t in times:
            app.job_queue.run_daily(window_job, time=t)

    print("Bot running 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
