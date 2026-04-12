from datetime import datetime


def get_trend(price, history):
    if len(history) < 2:
        return "SIDEWAYS", "No clear direction"

    if price > history[-1]:
        return "UP", "Momentum positive"
    elif price < history[-1]:
        return "DOWN", "Selling pressure"

    return "SIDEWAYS", "No clear direction"


# ---------------- POSITION SIZE ----------------
def position_size(cash, score, win_rate, trend):
    if score >= 80:
        base = 0.5
    elif score >= 65:
        base = 0.35
    elif score >= 50:
        base = 0.2
    else:
        base = 0.1

    if win_rate > 70:
        base += 0.1
    elif win_rate < 40:
        base -= 0.05

    if trend == "UP":
        base += 0.05
    elif trend == "DOWN":
        base -= 0.05

    base = max(0.05, min(base, 0.6))
    return int(cash * base)


# ---------------- RISK CONTROL ----------------
def risk_control(score, win_rate, trend):
    if score < 50:
        return False, "Low ML confidence"

    if win_rate < 30:
        return False, "Low win rate"

    if trend == "SIDEWAYS" and score < 60:
        return False, "No clear trend"

    return True, "Safe to trade"


# ---------------- SL TARGET ----------------
def get_sl_target(price, trend):
    if trend == "DOWN":
        return int(price * 0.97), int(price * 1.03)
    elif trend == "UP":
        return int(price * 0.98), int(price * 1.04)
    else:
        return int(price * 0.975), int(price * 1.02)


# ---------------- SHORT TERM ----------------
def short_term_ai(cash, pct, trend, score, win_rate, price):
    if pct >= 5:
        return "SELL", int(cash * 0.4), "Profit booking", None, None

    allowed, reason = risk_control(score, win_rate, trend)
    if not allowed:
        return "HOLD", 0, reason, None, None

    if trend == "DOWN" and cash > 1000:
        amt = position_size(cash, score, win_rate, trend)
        sl, tgt = get_sl_target(price, trend)
        return "BUY", amt, "ML-based dip buying", sl, tgt

    return "HOLD", 0, "No strong signal", None, None


# ---------------- LONG TERM ----------------
def long_term_ai(bought, price, avg_price, trend, history):
    today = datetime.now().day

    if bought:
        return "DONE", 0, "Already invested this month"

    if avg_price and price < avg_price * 0.98:
        return "BUY", 15000, "Good accumulation"

    if trend == "DOWN":
        return "BUY", 15000, "Market dip"

    if today >= 20:
        return "BUY", 15000, "Monthly discipline"

    return "WAIT", 0, "No strong signal"
