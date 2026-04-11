from datetime import datetime


def get_trend(price, history):
    if len(history) < 2:
        return "FLAT", "Not enough data"

    if price > history[-1]:
        return "UP ↗️", "Momentum positive"
    elif price < history[-1]:
        return "DOWN ↘️", "Selling pressure"

    return "SIDEWAYS", "No clear direction"


def short_term_ai(cash, pct, trend):
    if pct >= 5:
        return "SELL", int(cash * 0.4), "High profit booking"

    if pct >= 3:
        return "SELL", int(cash * 0.25), "Partial profit booking"

    if trend.startswith("DOWN") and cash > 1000:
        return "BUY", min(2000, cash), "Buying dip"

    return "HOLD", 0, "No strong signal"


def long_term_ai(already_bought, price, avg_price, trend, history):
    today = datetime.now().day

    if already_bought:
        return "DONE", 0, "Already invested this month"

    recent = history[-5:] if len(history) >= 5 else history

    volatility = max(recent) - min(recent) if len(recent) > 1 else 0
    momentum = price - recent[0] if recent else 0

    if avg_price and price < avg_price * 0.98:
        return "BUY", 15000, "Below average — strong accumulation"

    if trend.startswith("DOWN") and volatility > 100:
        return "BUY", 15000, "Dip buying opportunity"

    if trend == "SIDEWAYS" and volatility < 80:
        return "BUY", 15000, "Stable accumulation zone"

    if avg_price and price > avg_price * 1.05 and today < 20:
        return "WAIT", 0, "Price high — waiting"

    if momentum > 200 and today < 20:
        return "WAIT", 0, "Avoid buying at spike"

    if today >= 20:
        return "BUY", 15000, "Deadline approaching"

    return "WAIT", 0, "No strong signal"
