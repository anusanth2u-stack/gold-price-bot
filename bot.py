import os
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import logic
import sheets

TOKEN = os.environ.get("TELEGRAM_TOKEN")
USER_ID = 5400949107


# -------- DASHBOARD --------
async def dashboard(context: ContextTypes.DEFAULT_TYPE):
    price = logic.get_price()
    if not price:
        await context.bot.send_message(chat_id=USER_ID, text="⚠️ Price fetch failed")
        return

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

    keyboard = [
        [InlineKeyboardButton("🟢 Long Term Buy ₹15000", callback_data="lt_buy")],
        [InlineKeyboardButton("🟢 Short Term Buy ₹2000", callback_data="buy")],
        [InlineKeyboardButton("🔴 Short Term Sell ₹1000", callback_data="sell")],
    ]

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

    await context.bot.send_message(
        chat_id=USER_ID,
        text=msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# -------- START --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        return
    await dashboard(context)


# -------- BUTTON HANDLER --------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != USER_ID:
        return

    price = logic.get_price()
    cash, _ = sheets.get_short_term_summary()

    try:
        if query.data == "lt_buy":
            sheets.add_long(price)
            await query.message.reply_text("✅ Long-term BUY recorded")

        elif query.data == "buy":
            if cash < 500:
                await query.message.reply_text("⛔ Not enough cash")
                return

            sheets.add_short("BUY", 2000, price)
            await query.message.reply_text("✅ Short-term BUY recorded")

        elif query.data == "sell":
            sheets.add_short("SELL", 1000, price)
            await query.message.reply_text("✅ Short-term SELL recorded")

    except Exception as e:
        await query.message.reply_text(f"⚠️ Error: {str(e)}")


# -------- SCHEDULER --------
async def scheduler(app):
    while True:
        try:
            await dashboard(app)
        except Exception as e:
            print("Scheduler error:", e)

        await asyncio.sleep(3600)


# -------- MAIN --------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    # start scheduler AFTER app starts
    async def post_init(app):
        asyncio.create_task(scheduler(app))

    app.post_init = post_init

    print("Bot running 🚀")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
