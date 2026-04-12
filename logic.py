from datetime import datetime


def get_trend(price, history):
    if len(history) < 2:
        return "SIDEWAYS", "No clear direction"

    if price > history[-1]:
        return "UP", "Momentum positive"
    elif price < history[-1]:
        return "DOWN", "Selling pressure"

    return "SIDEWAYS", "No clear direction"


def short_term_ai(cash, pct, trend):
    if pct >= 5:
        return "SELL", int(cash * 0.4), "High profit booking"

    if pct >= 3:
        return "SELL", int(cash * 0.25), "Partial profit booking"

    if trend == "DOWN" and cash > 1000:
        return "BUY", min(2000, cash), "Buying dip"

    return "HOLD", 0, "No strong signal"


def long_term_ai(already_bought, price, avg_price, trend, history):
    today = datetime.now().day

    if already_bought:
        return "DONE", 0, "Already invested this month"

    if avg_price and price < avg_price * 0.98:
        return "BUY", 15000, "Stable accumulation zone"

    if trend == "DOWN":
        return "BUY", 15000, "Market dip"

    if today >= 20:
        return "BUY", 15000, "Monthly discipline"

    return "WAIT", 0, "No strong signal"
