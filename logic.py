from datetime import datetime

def get_trend(price, history):
    if len(history) < 2:
        return "FLAT", "Not enough data"

    if price > history[-1]:
        return "UP ↗️", "Momentum positive"
    elif price < history[-1]:
        return "DOWN ↘️", "Selling pressure"

    return "SIDEWAYS", "No clear direction"


def risk_signal(profit_pct):
    if profit_pct > 5:
        return "🔥 Profit Zone"
    if profit_pct < -3:
        return "⚠️ Drawdown Risk"
    return "🟡 Neutral"


def short_term_ai(cash, profit_pct, trend):
    if profit_pct >= 5:
        return "SELL", int(cash * 0.5), "High profit booking"

    if profit_pct >= 3:
        return "SELL", int(cash * 0.3), "Partial profit booking"

    if trend.startswith("DOWN") and cash > 1000:
        return "BUY", min(2000, cash), "Buying dip"

    return "HOLD", 0, "No strong signal"


def long_term_ai(already_bought):
    today = datetime.now().day

    if already_bought:
        return "DONE", 0, "Already invested this month"

    if today < 23:
        return "BUY", 15000, "Mandatory buy before 23rd"

    return "BUY", 15000, "Deadline crossed — invest immediately"
