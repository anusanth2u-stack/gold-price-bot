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


from datetime import datetime


def long_term_ai(already_bought, price, avg_price, trend):
    today = datetime.now().day

    # ✅ Already done
    if already_bought:
        return "DONE", 0, "Already invested this month"

    # 📉 Cheap compared to your average
    if avg_price and price < avg_price * 0.98:
        return "BUY", 15000, "Price below your average — good accumulation zone"

    # 📉 Market falling → buy dip
    if trend.startswith("DOWN"):
        return "BUY", 15000, "Market dip — good long-term entry"

    # 📈 Market rising → wait for better price
    if trend.startswith("UP") and price > avg_price * 1.02:
        if today < 20:
            return "WAIT", 0, "Price slightly high — waiting for pullback"
    
    # ⏰ Deadline enforcement
    if today >= 20:
        return "BUY", 15000, "Deadline approaching — monthly discipline buy"

    # Default
    return "WAIT", 0, "No strong opportunity yet"
