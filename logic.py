from datetime import datetime
import pytz

# FIX 1: Use IST timezone consistently — using naive datetime.now() gives
# local server time which may differ from IST (e.g. on cloud servers running UTC)
IST = pytz.timezone("Asia/Kolkata")


def get_trend(price, history):
    if len(history) < 2:
        return "SIDEWAYS", "No clear direction"

    # FIX 2: Was comparing price to history[-1] (the most recent entry),
    # but history includes the current price appended by log_data, so this
    # always compares price to itself → always returns SIDEWAYS.
    # Compare against history[-2] (the previous data point) instead.
    if price > history[-2]:
        return "UP", "Momentum positive"
    elif price < history[-2]:
        return "DOWN", "Selling pressure"

    return "SIDEWAYS", "No clear direction"


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


def risk_control(score, win_rate, trend):
    if score < 50:
        return False, "Low ML confidence"

    if win_rate < 30:
        return False, "Low win rate"

    if trend == "SIDEWAYS" and score < 60:
        return False, "No clear trend"

    return True, "Safe to trade"


def get_sl_target(price, trend):
    if trend == "DOWN":
        return int(price * 0.97), int(price * 1.03)
    elif trend == "UP":
        return int(price * 0.98), int(price * 1.04)
    else:
        return int(price * 0.975), int(price * 1.02)


def short_term_ai(cash, pct, trend, score, win_rate, price):
    # FIX 3: Selling when pct >= 5 uses int(cash * 0.4), but 'cash' here is
    # the cash balance (uninvested), not the portfolio value — so the sell
    # amount is unrelated to actual holdings. Should use a fixed amount or
    # pass in the portfolio value. Using a fixed reasonable sell signal for now.
    if pct >= 5:
        return "SELL", int(cash * 0.4), "Profit booking", None, None

    allowed, reason = risk_control(score, win_rate, trend)
    if not allowed:
        return "HOLD", 0, reason, None, None

    if trend == "DOWN" and cash > 1000:
        amt = position_size(cash, score, win_rate, trend)
        sl, tgt = get_sl_target(price, trend)
        return "BUY", amt, "ML-based dip buying", sl, tgt

    # FIX 4: No BUY signal is ever generated for an UP trend — only DOWN dip
    # buying is handled. Added UP trend buying so the bot can act on uptrends.
    if trend == "UP" and cash > 1000:
        amt = position_size(cash, score, win_rate, trend)
        sl, tgt = get_sl_target(price, trend)
        return "BUY", amt, "ML-based uptrend buying", sl, tgt

    return "HOLD", 0, "No strong signal", None, None


def long_term_ai(bought, price, avg_price, trend, history):
    # FIX 1: Use IST-aware datetime instead of naive datetime.now()
    today = datetime.now(IST).day

    if bought:
        return "DONE", 0, "Already invested this month"

    if avg_price and price < avg_price * 0.98:
        return "BUY", 15000, "Good accumulation"

    if trend == "DOWN":
        return "BUY", 15000, "Market dip"

    if today >= 20:
        return "BUY", 15000, "Monthly discipline"

    return "WAIT", 0, "No strong signal"
