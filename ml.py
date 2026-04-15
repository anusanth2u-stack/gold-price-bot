import numpy as np


def short_term_ml(history, st_data):
    if len(history) < 5:
        return 0, 0, "NA", 50, "Score:50%"

    prices = np.array(history[-15:])
    last = prices[-1]

    volatility = np.std(prices)

    low = int(last - volatility)
    high = int(last + volatility)

    # Normalize volatility as % of price for a meaningful score
    volatility_pct = (volatility / last) * 100 if last else 0
    score = int(max(50, min(90, 90 - volatility_pct * 2)))

    # Derive signal from score
    if score >= 75:
        signal = "BUY"
    elif score <= 55:
        signal = "SELL"
    else:
        signal = "Neutral"

    # Compute win rate from actual BUY/SELL pairs in st_data
    win_rate = 50
    if st_data:
        trades = [r for r in st_data if r.get("Type") in ("BUY", "SELL")]
        if len(trades) >= 2:
            wins = 0
            pairs = 0
            for i in range(len(trades) - 1):
                if trades[i]["Type"] == "BUY" and trades[i + 1]["Type"] == "SELL":
                    buy_price = float(trades[i].get("Price", 0))
                    sell_price = float(trades[i + 1].get("Price", 0))
                    pairs += 1
                    if buy_price and sell_price > buy_price:
                        wins += 1
            win_rate = int((wins / pairs) * 100) if pairs else 50

    return low, high, signal, win_rate, f"Score:{score}%"


def long_term_ml(history, avg_price, current):
    if len(history) < 5:
        return "NA", "NA", "NA", "Low"

    # Use recent 10 entries for more relevant trend
    recent = history[-10:]
    trend = "UP" if recent[-1] > recent[0] else "DOWN"

    if avg_price:
        if current < avg_price * 0.98:
            val = "Undervalued"
        elif current > avg_price * 1.02:
            val = "Overvalued"
        else:
            val = "Fair"
    else:
        val = "NA"

    zone = f"{int(current * 0.96)}-{int(current * 0.99)}"

    if len(history) >= 30:
        conf = "High"
    elif len(history) >= 15:
        conf = "Medium"
    else:
        conf = "Low"

    return trend, val, zone, conf
