import numpy as np


def short_term_ml(history, st_data):
    if len(history) < 5:
        return 0, 0, "NA", 50, "Score:50%"

    prices = np.array(history[-15:])
    last = prices[-1]

    volatility = np.std(prices)

    low = int(last - volatility)
    high = int(last + volatility)

    # FIX 1: score = int(70 - volatility) makes no sense — volatility for gold
    # prices is typically hundreds (e.g. 300-800), so 70 - volatility goes deeply
    # negative and gets clamped to 50 every time, making score always 50.
    # Normalize volatility as a % of price so the score is meaningful.
    volatility_pct = (volatility / last) * 100 if last else 0
    score = int(max(50, min(90, 90 - volatility_pct * 2)))

    # FIX 2: Signal is hardcoded to "Neutral" regardless of trend or score.
    # Derive a signal from the score.
    if score >= 75:
        signal = "BUY"
    elif score <= 55:
        signal = "SELL"
    else:
        signal = "Neutral"

    # FIX 3: win_rate is hardcoded to 50 — compute it from st_data if available.
    win_rate = 50
    if st_data:
        trades = [r for r in st_data if r.get("Type") in ("BUY", "SELL")]
        if len(trades) >= 2:
            wins = 0
            for i in range(len(trades) - 1):
                if trades[i]["Type"] == "BUY" and trades[i + 1]["Type"] == "SELL":
                    buy_price = float(trades[i].get("Price", 0))
                    sell_price = float(trades[i + 1].get("Price", 0))
                    if buy_price and sell_price > buy_price:
                        wins += 1
            pairs = sum(
                1 for i in range(len(trades) - 1)
                if trades[i]["Type"] == "BUY" and trades[i + 1]["Type"] == "SELL"
            )
            win_rate = int((wins / pairs) * 100) if pairs else 50

    return low, high, signal, win_rate, f"Score:{score}%"


def long_term_ml(history, avg_price, current):
    if len(history) < 5:
        return "NA", "NA", "NA", "Low"

    # FIX 4: Comparing history[-1] to history[0] uses the full history range,
    # which reflects a very long-term bias and ignores recent momentum.
    # Use a shorter recent window (last 10 entries) for a more relevant trend.
    recent = history[-10:]
    trend = "UP" if recent[-1] > recent[0] else "DOWN"

    if avg_price:
        # FIX 5: Only "Undervalued" or "Fair" — missing "Overvalued" case.
        # Added a threshold so prices significantly above avg show as Overvalued.
        if current < avg_price * 0.98:
            val = "Undervalued"
        elif current > avg_price * 1.02:
            val = "Overvalued"
        else:
            val = "Fair"
    else:
        val = "NA"

    zone = f"{int(current*0.96)}-{int(current*0.99)}"

    # FIX 6: Confidence is hardcoded to "Medium" regardless of data.
    # Base it on how much history is available.
    if len(history) >= 30:
        conf = "High"
    elif len(history) >= 15:
        conf = "Medium"
    else:
        conf = "Low"

    return trend, val, zone, conf
