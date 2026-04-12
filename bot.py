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
    await send_dashboard(context)


async def force(update, context):
    await update.message.reply_text("⚡ Force update")
    await send_dashboard(context)


# ---------------- BUTTON ----------------
async def button(update, context):
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
    print("Scheduled Trigger")
    await send_dashboard(context)


# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

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
