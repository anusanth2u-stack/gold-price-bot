import numpy as np


def analyze_trades(st_data):
    buys, sells = [], []

    for r in st_data:
        try:
            if r["Type"] == "BUY":
                buys.append(float(r["Price"]))
            elif r["Type"] == "SELL":
                sells.append(float(r["Price"]))
        except:
            pass

    total = min(len(buys), len(sells))
    wins = sum(1 for i in range(total) if sells[i] > buys[i])

    win_rate = int((wins / total) * 100) if total else 50
    avg_buy = np.mean(buys) if buys else 0

    return avg_buy, win_rate


def get_prediction(history, st_data):
    if len(history) < 5:
        return 0, 0, "NA", 50, "Score:50%"

    prices = np.array(history[-15:])
    diffs = np.diff(prices)

    avg_change = np.mean(diffs)
    volatility = np.std(prices)
    last = prices[-1]

    low = int(last - volatility)
    high = int(last + volatility)

    avg_buy, win_rate = analyze_trades(st_data)

    score = min(95, max(50, int(win_rate + 50 - volatility)))

    extra = f"Score:{score}% | BuyZone:{int(last*0.95)}-{int(last)} | Size:MEDIUM"

    return low, high, "Neutral", win_rate, extra


def long_term_ml(price, history, avg_price):
    if len(history) < 5:
        return "NA", "NA", "NA", "Low"

    trend = "Strong" if history[-1] > history[0] else "Weak"

    if avg_price:
        if price < avg_price * 0.95:
            val = "Undervalued"
        elif price > avg_price * 1.05:
            val = "Overvalued"
        else:
            val = "Fair"
    else:
        val = "NA"

    zone = f"{int(price*0.96)}-{int(price*0.99)}"

    return trend, val, zone, "Medium"
