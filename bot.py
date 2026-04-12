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


# ---------------- CLEAN START ----------------
async def post_init(app):
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        print("Clean start done")
    except Exception as e:
        print("Cleanup error:", e)


# ---------------- PRICE HELPERS ----------------
def extract_number(text):
    match = re.search(r"\d{1,3}(?:,\d{3})*", text)
    return float(match.group().replace(",", "")) if match else None


# ---------------- GOLD PRICE ----------------
def get_gold_price():
    try:
        url = "https://www.keralagold.com/kerala-gold-rate-per-gram.htm"
        res = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) == 2:
                price = extract_number(cols[1].text)
                if price:
                    return price
    except:
        pass

    # Fallback → TOI
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


# ---------------- GOLDBEES PRICE ----------------
def get_goldbees_price():
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=GOLDBEES.NS"
        res = requests.get(url).json()
        return res["quoteResponse"]["result"][0]["regularMarketPrice"]
    except:
        return None


# ---------------- WINDOW ----------------
def is_window_open():
    return datetime.now(IST).hour in [10, 12, 14, 16, 18]


# ---------------- SCORE PARSER ----------------
def extract_score(extra):
    try:
        return int(extra.split("Score:")[1].split("%")[0])
    except:
        return 50


# ---------------- DASHBOARD ----------------
async def send_dashboard(context: ContextTypes.DEFAULT_TYPE):

    gold_price = get_gold_price()
    goldbees_price = get_goldbees_price()

    if not gold_price or not goldbees_price:
        await context.bot.send_message(chat_id=USER_ID, text="⚠️ Price fetch failed")
        return

    # HISTORIES
    gold_history = sheets.get_gold_history()
    bees_history = sheets.get_bees_history()

    # TRENDS
    gold_trend, gold_reason = logic.get_trend(gold_price, gold_history)
    bees_trend, bees_reason = logic.get_trend(goldbees_price, bees_history)

    # METRICS
    st_inv, st_cash, st_units, st_val, st_profit, st_pct = sheets.get_st_metrics(goldbees_price)
    lt_inv, lt_gold, lt_val, lt_profit, lt_pct = sheets.get_lt_metrics(gold_price)

    avg_price = sheets.get_avg_buy_price()
    bought = sheets.already_bought()

    # ML
    st_data = sheets.get_st_history()
    ml_low, ml_high, ml_signal, win_rate, extra = ml.short_term_ml(bees_history, st_data)

    score = extract_score(extra)

    lt_trend_ml, lt_valn, lt_zone, lt_conf = ml.long_term_ml(
        gold_history, avg_price, gold_price
    )

    # AI
    st_action, st_amt, st_reason, sl, tgt = logic.short_term_ai(
        st_cash, st_pct, bees_trend, score, win_rate, goldbees_price
    )

    lt_action, lt_amt, lt_reason = logic.long_term_ai(
        bought, gold_price, avg_price, gold_trend, gold_history
    )

    # LOG DATA
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

    # ---------------- UI ----------------
    msg = f"""
💎 GOLD AI PORTFOLIO ENGINE

💰 Gold: ₹{gold_price}
📈 GoldBees: ₹{goldbees_price}

📊 Trend (Gold): {gold_trend}
📊 Trend (GoldBees): {bees_trend}

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

    # ---------------- BUTTONS ----------------
    keyboard = []

    if lt_action == "BUY":
        keyboard.append([InlineKeyboardButton("🟢 LT BUY ₹15000", callback_data="lt_buy")])

    if st_action == "BUY":
        keyboard.append([InlineKeyboardButton(f"🟢 BUY ₹{st_amt}", callback_data=f"buy_{st_amt}")])

    if st_action == "SELL":
        keyboard.append([InlineKeyboardButton(f"🔴 SELL ₹{st_amt}", callback_data=f"sell_{st_amt}")])

    await context.bot.send_message(chat_id=USER_ID, text=msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------- BUTTON ----------------
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


# ---------------- COMMANDS ----------------
async def start(update, context):
    await send_dashboard(context)


async def force(update, context):
    await update.message.reply_text("⚡ Force update")
    await send_dashboard(context)


# ---------------- SCHEDULER ----------------
async def job(context):
    print("Scheduled Trigger")
    await send_dashboard(context)


# ---------------- MAIN ----------------
def main():
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
            app.job_queue.run_daily(job, time=t)

    print("Bot running 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
