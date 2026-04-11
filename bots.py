from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import logic
import sheets
import os

TOKEN = os.environ.get("TELEGRAM_TOKEN")
USER_ID = 5400949107


def is_authorized(user_id):
    return user_id == USER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    keyboard = [
        [InlineKeyboardButton("🟢 Long Term Buy", callback_data='lt_buy')],
        [InlineKeyboardButton("🔴 Short Term Buy", callback_data='st_buy')],
        [InlineKeyboardButton("📊 Portfolio", callback_data='portfolio')]
    ]

    await update.message.reply_text(
        "💎 GOLD AI ADVISOR",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    query = update.callback_query
    await query.answer()

    context.user_data["action"] = query.data

    if query.data == "lt_buy":
        await query.message.reply_text("Enter price:")

    elif query.data == "st_buy":
        await query.message.reply_text("Enter amount price (2000 13850):")

    elif query.data == "portfolio":
        invested, grams, avg = sheets.get_long_term_summary()
        await query.message.reply_text(
            f"📊 Portfolio\n\nInvested: ₹{invested}\nGold: {grams}g\nAvg: ₹{round(avg)}"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    text = update.message.text
    action = context.user_data.get("action")

    if action == "lt_buy":
        price = float(text)
        sheets.add_long_term(price)
        await update.message.reply_text("✅ Long-term saved")

    elif action == "st_buy":
        amount, price = map(float, text.split())
        sheets.add_short_term("BUY", amount, price)
        await update.message.reply_text("✅ Short-term saved")

    else:
        await update.message.reply_text("Use /start")


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT, handle_message))

print("Bot running 🚀")
app.run_polling()
