import os
import requests
from bs4 import BeautifulSoup
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import logic
import sheets

TOKEN = os.environ.get("TELEGRAM_TOKEN")
USER_ID = 5400949107


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

        if today_price:
            return today_price

        if latest_price:
            return latest_price

    except Exception as e:
        print("KeralaGold error:", e)

    # fallback
    try:
        url = "https://timesofindia.indiatimes.com/business/gold-rates-today/gold-price-in-bangalore.cms"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)

        numbers = re.findall(r"\d{1,3}(?:,\d{3})", res.text)

        for num in numbers:
            val = float(num.replace(",", ""))
            if 3000 < val < 20000:
                return val

    except Exception as e:
        print("TOI error:", e)

    return None


async def send_dashboard(context: ContextTypes.DEFAULT_TYPE):
    try:
        price = get_price()

        if not price:
            await context.bot.send_message(
                chat_id=USER_ID,
                text="⚠️ No gold price data available today. No updates made."
            )
            return

        sheets.add_budget()
        history = sheets.get_history()

        trend, reason = logic.get_trend(price, history)
        sheets.log_data(price, trend)

        st_inv, st_cash, st_gold, st_value, st_profit, st_pct = sheets.get_st_metrics(price)
        lt_inv, lt_gold, lt_value, lt_profit, lt_pct = sheets.get_lt_metrics(price)

        bought = sheets.already_bought()

        st_action, st_amt, st_reason = logic.short_term_ai(st_cash, st_pct, trend)
        avg_price = sheets.get_avg_buy_price()

        lt_action,lt_amt,lt_reason = logic.long_term_ai(bought,price,avg_price,trend)

        total_val = st_value + lt_value
        total_inv = st_inv + lt_inv
        total_profit = total_val - total_inv

        msg = f"""
💎 GOLD AI PORTFOLIO ENGINE

💰 Price: ₹{price}

📉 Trend: {trend}
🧠 {reason}

━━━━━━━━━━━━━━━
🟢 LONG TERM

Invested: ₹{int(lt_inv)}
Gold: {round(lt_gold,3)}g
Value: ₹{int(lt_value)}

P/L: ₹{int(lt_profit)} ({round(lt_pct,2)}%)

Action: {lt_action}
Reason: {lt_reason}

━━━━━━━━━━━━━━━
🔴 SHORT TERM

Cash: ₹{int(st_cash)}
Gold: {round(st_gold,3)}g

Value: ₹{int(st_value)}
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
"""

        keyboard = []

        if lt_action == "BUY":
            keyboard.append([InlineKeyboardButton("🟢 LT BUY ₹15000", callback_data="lt_buy")])

        if st_action == "BUY":
            keyboard.append([InlineKeyboardButton(f"🟢 BUY ₹{st_amt}", callback_data=f"buy_{st_amt}")])

        if st_action == "SELL":
            keyboard.append([InlineKeyboardButton(f"🔴 SELL ₹{st_amt}", callback_data=f"sell_{st_amt}")])

        await context.bot.send_message(chat_id=USER_ID, text=msg, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        print("ERROR:", e)


async def start(update, context):
    await send_dashboard(context)


async def scheduler(context):
    await send_dashboard(context)


async def button(update, context):
    q = update.callback_query
    await q.answer()

    price = get_price()

    try:
        if not price:
            await q.message.reply_text("⚠️ Cannot execute — price not available")
            return

        if q.data == "lt_buy":
            sheets.add_long(price)
            await q.message.reply_text("LT BUY DONE")

        elif "buy_" in q.data:
            amt = int(q.data.split("_")[1])
            sheets.add_short("BUY", amt, price)
            await q.message.reply_text(f"BUY ₹{amt}")

        elif "sell_" in q.data:
            amt = int(q.data.split("_")[1])
            sheets.add_short("SELL", amt, price)
            await q.message.reply_text(f"SELL ₹{amt}")

    except Exception as e:
        await q.message.reply_text(str(e))


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    if app.job_queue:
        app.job_queue.run_repeating(scheduler, interval=3600, first=10)

    print("Bot running 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
