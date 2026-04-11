import os
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

import logic
import sheets

TOKEN = os.environ.get("TELEGRAM_TOKEN")
USER_ID = 5400949107


def is_authorized(user_id):
    return user_id == USER_ID


async def dashboard(context):
    sheets.ensure_monthly_budget()

    price = logic.get_price()
    if not price:
        await context.bot.send_message(chat_id=USER_ID, text="⚠️ Failed to fetch price")
        return

    history = sheets.get_history()
    score = logic.calculate_score(price, history)

    sheets.log_price(price, score)

    cash, gold = sheets.get_summary()

    decision = logic.short_term_decision(score, cash)

    keyboard = [
        [InlineKeyboardButton("🟢 BUY ₹2000", callback_data="buy")],
        [InlineKeyboardButton("🔴 SELL ₹1000", callback_data="sell")]
    ]

    msg = f"""
💎 GOLD AI ADVISOR

💰 Price: ₹{price}
📊 Score: {score}/100

💼 Cash: ₹{int(cash)}
🪙 Gold: {round(gold,3)}g

🤖 Recommendation:
{decision}
"""

    await context.bot.send_message(
        chat_id=USER_ID,
        text=msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def start(update, context):
    if not is_authorized(update.effective_user.id):
        return

    await dashboard(context)


async def handle_button(update, context):
    query = update.callback_query
    await query.answer()

    if not is_authorized(query.from_user.id):
        return

    price = logic.get_price()
    cash, _ = sheets.get_summary()

    if query.data == "buy":
        if cash < 1000:
            await query.message.reply_text("⛔ Not enough cash")
            return

        sheets.add_transaction("BUY", 2000, price)
        await query.message.reply_text("✅ BUY recorded")

    elif query.data == "sell":
        sheets.add_transaction("SELL", 1000, price)
        await query.message.reply_text("✅ SELL recorded")


async def scheduler(app):
    while True:
        try:
            await dashboard(app)
        except Exception as e:
            print("Error:", e)

        await asyncio.sleep(3600)


async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_button))

    await app.initialize()
    await app.start()

    asyncio.create_task(scheduler(app))

    await app.updater.start_polling()


print("Bot running 🚀")
asyncio.run(main())
