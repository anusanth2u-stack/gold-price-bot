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

    learning = sheets.get_learning_factor(price)

    score = logic.calculate_score(price, history, learning)
    trend = logic.get_trend(price, history)
    volatility = logic.get_volatility(history)
    low, high, conf = logic.predict_ml(price, history)

    sheets.log_price(price, score)

    cash, st_gold = sheets.get_short_term_summary()
    lt_inv, lt_gold = sheets.get_long_summary()
    bought = sheets.already_bought()

    lt_decision = logic.long_term_decision(score, bought)
    st_decision = logic.short_term_decision(score, cash)

    total_gold, value, profit, pct, _ = sheets.get_portfolio(price)

    msg = f"""
💎 GOLD AI (SELF LEARNING)

💰 Price: ₹{price}
📊 Score: {score}
🧠 Learning Boost: {learning}

📉 Trend: {trend}
⚡ Volatility: {volatility}

🔮 Prediction:
₹{low} – ₹{high} ({conf})

━━━━━━━━━━━━━━━
🟢 LONG TERM
{lt_decision}

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
        [InlineKeyboardButton("🟢 LT BUY ₹15000", callback_data="lt_buy")],
        [InlineKeyboardButton("🟢 BUY ₹2000", callback_data="buy")],
        [InlineKeyboardButton("🔴 SELL ₹1000", callback_data="sell")]
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
        await query.message.reply_text("✅ LT BUY")

    elif query.data == "buy":
        sheets.add_short("BUY", 2000, price)
        await query.message.reply_text("✅ BUY")

    elif query.data == "sell":
        sheets.add_short("SELL", 1000, price)
        await query.message.reply_text("✅ SELL")


async def scheduler(app):
    while True:
        await dashboard(app)
        await asyncio.sleep(3600)


async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", dashboard))
    app.add_handler(CallbackQueryHandler(handle))

    await app.initialize()
    await app.start()

    asyncio.create_task(scheduler(app))

    await app.updater.start_polling()


print("Bot running 🚀")
asyncio.run(main())
