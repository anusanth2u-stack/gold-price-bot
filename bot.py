import os
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

import logic
import sheets

TOKEN = os.environ.get("TELEGRAM_TOKEN")
USER_ID = 5400949107


async def dashboard(context):
    price = logic.get_price()
    history = sheets.get_history()

    score = logic.calculate_score(price, history)
    trend = logic.get_trend(price, history)
    volatility = logic.get_volatility(history)
    low, high = logic.predict_range(price, history)
    reason = logic.get_reason(score, trend, volatility)

    sheets.log_price(price, score)

    # portfolio
    cash, st_gold = sheets.get_short_term_summary()
    lt_inv, lt_gold = sheets.get_long_summary()
    bought = sheets.already_bought()

    lt_decision = logic.long_term_decision(score, bought)
    st_decision = logic.short_term_decision(score, cash)

    total_gold, value, profit, pct, _ = sheets.get_portfolio(price)

    msg = f"""
💎 GOLD AI ADVISOR

💰 Price: ₹{price}
📊 Score: {score}/100
📉 Trend: {trend}
⚡ Volatility: {volatility}

🔮 Next Day Range:
₹{low} – ₹{high}

🧠 Insight:
{reason}

━━━━━━━━━━━━━━━
🟢 LONG TERM

Status: {lt_decision}

━━━━━━━━━━━━━━━
🔴 SHORT TERM

Cash: ₹{int(cash)}
Gold: {round(st_gold,3)}g

Action: {st_decision}

━━━━━━━━━━━━━━━
📊 PORTFOLIO

Gold: {round(total_gold,3)}g
Value: ₹{int(value)}

P/L: ₹{int(profit)}
Return: {round(pct,2)}%
"""

    keyboard = [
        [InlineKeyboardButton("🟢 Long Term Buy ₹15000", callback_data="lt_buy")],
        [InlineKeyboardButton("🟢 Short Term Buy ₹2000", callback_data="buy")],
        [InlineKeyboardButton("🔴 Short Term Sell ₹1000", callback_data="sell")]
    ]

    await context.bot.send_message(
        chat_id=USER_ID,
        text=msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle(update, context):
    query = update.callback_query
    await query.answer()

    price = logic.get_price()

    if query.data == "lt_buy":
        sheets.add_long(price)
        await query.message.reply_text("✅ LT BUY recorded")

    elif query.data == "buy":
        sheets.add_short("BUY", 2000, price)
        await query.message.reply_text("✅ BUY recorded")

    elif query.data == "sell":
        sheets.add_short("SELL", 1000, price)
        await query.message.reply_text("✅ SELL recorded")


async def scheduler(app):
    while True:
        await dashboard(app)
        await asyncio.sleep(3600)


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", dashboard))
app.add_handler(CallbackQueryHandler(handle))

app.post_init = scheduler

print("Bot running 🚀")
app.run_polling()
