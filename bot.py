async def dashboard(context):
    price = 14000  # replace with API

    history = []
    trend, trend_reason = logic.get_trend(price, history)

    # SHORT TERM
    st_inv, st_cash, st_gold, gold_val, st_value, st_profit, st_pct = sheets.get_short_term_metrics(price)

    # LONG TERM
    lt_inv, lt_gold, lt_value, lt_profit, lt_pct = sheets.get_long_term_metrics(price)

    bought = sheets.already_bought_this_month()

    # AI
    st_action, st_amt, st_reason = logic.short_term_ai(st_cash, st_pct, trend)
    lt_action, lt_amt, lt_reason = logic.long_term_ai(bought)

    risk = logic.risk_signal(st_pct)

    total_value = st_value + lt_value
    total_inv = st_inv + lt_inv
    total_profit = total_value - total_inv
    total_pct = (total_profit / total_inv * 100) if total_inv else 0

    msg = f"""
💎 GOLD AI PORTFOLIO ENGINE

💰 Price: ₹{price}

📉 MARKET TREND
Trend: {trend}
Insight: {trend_reason}

━━━━━━━━━━━━━━━━━━━
🟢 LONG TERM

Invested: ₹{int(lt_inv)}
Gold: {round(lt_gold,3)}g
Value: ₹{int(lt_value)}

P/L: ₹{int(lt_profit)} ({round(lt_pct,2)}%)

Action: {lt_action}
Reason: {lt_reason}

━━━━━━━━━━━━━━━━━━━
🔴 SHORT TERM

💵 Cash: ₹{int(st_cash)}
🪙 Gold: {round(st_gold,3)}g

Gold Value: ₹{int(gold_val)}
Total Value: ₹{int(st_value)}

Invested: ₹{int(st_inv)}

P/L: ₹{int(st_profit)}
Return: {round(st_pct,2)}%

Risk: {risk}

━━━━━━━━━━━━━━━━━━━
💎 TOTAL

Value: ₹{int(total_value)}
Invested: ₹{int(total_inv)}

P/L: ₹{int(total_profit)}
Return: {round(total_pct,2)}%

━━━━━━━━━━━━━━━━━━━
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

    await context.bot.send_message(
        chat_id=USER_ID,
        text=msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
