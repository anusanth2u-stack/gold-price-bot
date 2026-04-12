import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, time
import pytz

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


# ---------------- CLEAN TELEGRAM SESSION ----------------
async def post_init(app):
    try:
        print("Cleaning old sessions...")
        await app.bot.delete_webhook(drop_pending_updates=True)
        print("Clean start complete")
    except Exception as e:
        print("Cleanup error:", e)


# ---------------- SCRAPER ----------------
def extract_number(text):
    match = re.search(r"\d{1,3}(?:,\d{3})*", text)
    return float(match.group().replace(",", "")) if match else None


def get_price():
    try:
        res = requests.get(
            "https://www.keralagold.com/kerala-gold-rate-per-gram.htm",
            headers={"User-Agent": "Mozilla"},
        )
        soup = BeautifulSoup(res.text, "html.parser")

        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) == 2:
                price = extract_number(cols[1].text)
                if price:
                    return price
    except:
        pass

    return None


# ---------------- WINDOW ----------------
def is_window_open():
    return datetime.now(IST).hour in [10, 12, 14, 16, 18]


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

    # ML
    st_data = sheets.get_st_history()
    ml_low, ml_high, ml_signal, win_rate, extra = ml.get_prediction(history, st_data)

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
        keyboard.append([InlineKeyboardButton("🟢 LT BUY ₹15000", callback_data="lt_buy")])

    if st_action == "BUY":
        keyboard.append([InlineKeyboardButton(f"🟢 BUY ₹{st_amt}", callback_data=f"buy_{st_amt}")])

    if st_action == "SELL":
        keyboard.append([InlineKeyboardButton(f"🔴 SELL ₹{st_amt}", callback_data=f"sell_{st_amt}")])

    await context.bot.send_message(chat_id=USER_ID, text=msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.post_init = post_init

    app.add_handler(CommandHandler("start", lambda u, c: send_dashboard(c)))
    app.add_handler(CommandHandler("force", lambda u, c: send_dashboard(c)))
    app.add_handler(CallbackQueryHandler(button))

    times = [time(10,0,tzinfo=IST), time(12,0,tzinfo=IST),
             time(14,0,tzinfo=IST), time(16,0,tzinfo=IST),
             time(18,0,tzinfo=IST)]

    for t in times:
        app.job_queue.run_daily(lambda c: send_dashboard(c), time=t)

    print("Bot running 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
