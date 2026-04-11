import os
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


async def dashboard(context: ContextTypes.DEFAULT_TYPE):
    try:
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
💎 GOLD AI

💰 Price: ₹{price}
📊 Score: {score}
🧠 Learning: {learning}

📉 Trend: {trend}
⚡ Volatility: {volatility}

🔮 Prediction: ₹{low} – ₹{high} ({conf})

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

    except Exception as e:
        print("Dashboard error:", e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != USER_ID:
        return
    await dashboard(context)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    price = logic.get_price()
    cash, _ = sheets.get_short_term_summary()

    if query.data == "lt_buy":
        sheets.add_long(price)
        await query.message.reply_text("✅ LT BUY recorded")

    elif query.data == "buy":
        if cash < 500:
            await query.message.reply_text("⛔ Not enough cash")
            return
        sheets.add_short("BUY", 2000, price)
        await query.message.reply_text("✅ BUY recorded")

    elif query.data == "sell":
        sheets.add_short("SELL", 1000, price)
        await query.message.reply_text("✅ SELL recorded")


async def scheduler_job(context: ContextTypes.DEFAULT_TYPE):
    await dashboard(context)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.job_queue.run_repeating(scheduler_job, interval=3600, first=10)

    print("Bot running 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
