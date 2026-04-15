import numpy as np


def _rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    deltas    = np.diff(prices[-(period + 1):])
    gains     = np.where(deltas > 0, deltas, 0.0)
    losses    = np.where(deltas < 0, -deltas, 0.0)
    avg_gain  = np.mean(gains)
    avg_loss  = np.mean(losses) if np.mean(losses) != 0 else 1e-9
    rs        = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _ema(prices, span):
    if len(prices) < span:
        span = len(prices)
    weights  = np.exp(np.linspace(-1, 0, span))
    weights /= weights.sum()
    return float(np.convolve(np.array(prices[-span:]), weights, mode='valid')[-1])


def _momentum(prices, window=5):
    if len(prices) < window + 1:
        return 0
    return round((prices[-1] - prices[-window - 1]) / prices[-window - 1] * 100, 3)


def _support_resistance(prices, window=20):
    recent = prices[-window:] if len(prices) >= window else prices
    return round(float(np.min(recent)), 2), round(float(np.max(recent)), 2)


def short_term_ml(daily_history, st_data):
    """
    Interday ML for GoldBees.
    Expects DAILY close prices (already aggregated in sheets.get_bees_daily()).
    Uses last 20 days for context.
    """
    if len(daily_history) < 3:
        return 0, 0, "NA", 50, "Score:50%"

    prices = np.array(daily_history[-20:])
    last   = float(prices[-1])

    volatility = float(np.std(prices))
    low  = round(last - volatility, 2)
    high = round(last + volatility, 2)

    rsi   = _rsi(prices, period=min(14, len(prices) - 1))
    mom5d = _momentum(list(prices), window=min(5,  len(prices) - 1))  # 1 week
    mom10d= _momentum(list(prices), window=min(10, len(prices) - 1))  # 2 weeks

    ema_fast  = _ema(list(prices), min(5,  len(prices)))   # 1-week EMA
    ema_slow  = _ema(list(prices), min(15, len(prices)))   # 3-week EMA
    ema_cross = ema_fast - ema_slow

    support, resistance = _support_resistance(list(prices), window=min(20, len(prices)))
    near_support    = last <= support    * 1.005
    near_resistance = last >= resistance * 0.995

    # ── Composite score ───────────────────────────────────────
    score = 50

    if rsi < 30:   score += 25
    elif rsi < 40: score += 15
    elif rsi < 50: score += 5
    elif rsi > 70: score -= 25
    elif rsi > 60: score -= 15
    elif rsi > 55: score -= 5

    if mom5d > 0.3:    score += 15
    elif mom5d > 0.1:  score += 8
    elif mom5d < -0.3: score -= 15
    elif mom5d < -0.1: score -= 8

    if mom10d > 0.5:   score += 10
    elif mom10d > 0:   score += 5
    elif mom10d < -0.5:score -= 10
    elif mom10d < 0:   score -= 5

    if ema_cross > 0:  score += 10
    elif ema_cross < 0:score -= 10

    if near_support:    score += 10
    if near_resistance: score -= 10

    score = int(max(20, min(90, score)))

    if score >= 68:     signal = "BUY"
    elif score <= 35:   signal = "SELL"
    else:               signal = "NEUTRAL"

    # Win rate from closed BUY→SELL pairs
    win_rate = 50
    if st_data:
        trades = [r for r in st_data if str(r.get("Type", "")).upper() in ("BUY", "SELL")]
        pairs, wins = 0, 0
        for i in range(len(trades) - 1):
            if str(trades[i]["Type"]).upper() == "BUY" and str(trades[i+1]["Type"]).upper() == "SELL":
                bp = float(trades[i].get("Price", 0) or 0)
                sp = float(trades[i+1].get("Price", 0) or 0)
                if bp:
                    pairs += 1
                    if sp > bp:
                        wins += 1
        win_rate = int((wins / pairs) * 100) if pairs else 50

    extra = (
        f"Score:{score}%\n"
        f"RSI:{rsi} | Mom(5d):{mom5d}% | Mom(10d):{mom10d}%\n"
        f"EMA:{'Bullish ↑' if ema_cross > 0 else 'Bearish ↓'} | "
        f"S:₹{support} R:₹{resistance}"
    )

    return low, high, signal, win_rate, extra


def long_term_ml(daily_history, avg_price, current):
    """
    Gold macro trend for Kalyan scheme context.
    Uses daily prices — last 30 days.
    """
    if len(daily_history) < 3:
        return "NA", "NA", "NA", "Low"

    recent = daily_history[-30:] if len(daily_history) >= 30 else daily_history
    trend  = "UP" if recent[-1] > recent[0] else "DOWN"

    if avg_price:
        if current < avg_price * 0.97:
            val = "Undervalued"
        elif current > avg_price * 1.03:
            val = "Overvalued"
        else:
            val = "Fair"
    else:
        val = "NA"

    # Buy zone: 1–2% below current (for Kalyan dip buying)
    zone = f"{round(current * 0.98, 0):.0f}–{round(current * 0.99, 0):.0f}"

    if len(daily_history) >= 20:   conf = "High"
    elif len(daily_history) >= 10: conf = "Medium"
    else:                          conf = "Low"

    return trend, val, zone, conf
