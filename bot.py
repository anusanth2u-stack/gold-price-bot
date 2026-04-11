import os
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import logic
import sheets

TOKEN = os.environ.get("TELEGRAM_TOKEN")
USER_ID = 5400949107


def auth(user_id):
    return user_id == USER_ID


async def dashboard(context):
    price = logic.get_price()
    history = sheets.get_history()
    score = logic.calculate_score(price, history)

    sheets.log_price(price, score)

    invested, lt_grams, avg = sheets.get_long_term_summary()
    cash, st_grams = sheets.get_short_term_summary()

    lt_value = lt_grams * price
    st_value = st_grams * price + cash

    keyboard = [
        [InlineKeyboardButton("🟢 Confirm LT Buy", callback_data="lt_buy")],
        [InlineKeyboardButton("🔴 Short Buy", callback_data="st_buy")],
        [InlineKeyboardButton("🔴 Short Sell", callback_data="st_sell")]
    ]

    msg = f"""
💎 GOLD AI DASHBOARD

💰 Price: ₹{price}
📊 Score: {score}

🟢 LONG TERM
Invested: ₹{invested}
Gold: {round(lt_grams,2)}g
Value: ₹{round(lt_value)}

🔴 SHORT TERM
Cash: ₹{cash}
Gold: {round(st_grams,3)}g
Value: ₹{round(st_value)}
"""

    await context.bot.send_message(chat_id=USER_ID, text=msg,
                                   reply_markup=InlineKeyboardMarkup(keyboard))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update.effective_user.id):
        return

    await dashboard(context)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update.effective_user.id):
        return

    query = update.callback_query
    await query.answer()

    price = logic.get_price()

    if query.data == "lt_buy":
        sheets.long_term_buy(price)
        await query.message.reply_text("✅ Long-term buy recorded")

    elif query.data == "st_buy":
        sheets.short_term_txn("BUY", 2000, price)
        await query.message.reply_text("✅ Short-term BUY")

    elif query.data == "st_sell":
        sheets.short_term_txn("SELL", 1000, price)
        await query.message.reply_text("✅ Short-term SELL")


async def scheduler(app):
    while True:
        await dashboard(app)
        await asyncio.sleep(3600)


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

app.post_init = scheduler

print("Bot running 🚀")
app.run_polling()
