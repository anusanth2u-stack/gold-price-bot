import numpy as np


def short_term_ml(history, st_data):
    if len(history) < 5:
        return 0, 0, "NA", 50, "Score:50%"

    prices = np.array(history[-15:])
    last = prices[-1]

    volatility = np.std(prices)

    low = int(last - volatility)
    high = int(last + volatility)

    score = int(max(50, min(90, 70 - volatility)))

    return low, high, "Neutral", 50, f"Score:{score}%"


def long_term_ml(history, avg_price, current):
    if len(history) < 5:
        return "NA", "NA", "NA", "Low"

    trend = "UP" if history[-1] > history[0] else "DOWN"

    if avg_price:
        if current < avg_price:
            val = "Undervalued"
        else:
            val = "Fair"
    else:
        val = "NA"

    zone = f"{int(current*0.96)}-{int(current*0.99)}"

    return trend, val, zone, "Medium"
