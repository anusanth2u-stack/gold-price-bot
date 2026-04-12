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
            continue

    total = min(len(buys), len(sells))
    wins = sum(1 for i in range(total) if sells[i] > buys[i])

    win_rate = int((wins / total) * 100) if total else 0
    avg_buy = np.mean(buys) if buys else 0

    return avg_buy, win_rate


def get_prediction(history, st_data):
    if len(history) < 5:
        return "NA", "NA", "Not enough data", 0, "NA"

    prices = np.array(history[-15:])
    diffs = np.diff(prices)

    avg_change = np.mean(diffs)
    volatility = np.std(prices)
    last_price = prices[-1]

    next_price = last_price + avg_change
    low = int(next_price - volatility)
    high = int(next_price + volatility)

    avg_buy, win_rate = analyze_trades(st_data)

    buy_low = int(avg_buy * 0.97) if avg_buy else int(last_price * 0.97)
    buy_high = int(avg_buy) if avg_buy else int(last_price)

    if avg_buy and last_price < avg_buy:
        signal = "Good Buy Zone"
    elif avg_buy and last_price > avg_buy * 1.05:
        signal = "Overvalued"
    else:
        signal = "Neutral"

    score = min(95, max(50, int(win_rate + 50 - volatility / 10)))

    if win_rate > 70:
        size = "HIGH"
    elif win_rate > 50:
        size = "MEDIUM"
    else:
        size = "LOW"

    extra = f"Score:{score}% | BuyZone:{buy_low}-{buy_high} | Size:{size}"

    return low, high, signal, win_rate, extra
