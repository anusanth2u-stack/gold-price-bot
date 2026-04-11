import requests
from bs4 import BeautifulSoup
import re


URL = "https://www.keralagold.com/kerala-gold-rate-per-gram.htm"


def get_price():
    try:
        res = requests.get(URL, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text()

        match = re.search(r"Today\s*»Rs\.\s*([\d,]+)", text)
        if match:
            return float(match.group(1).replace(",", ""))
    except:
        pass

    return None


def calculate_score(price, history, learning):
    score = 50

    if history:
        if price < history[-1]:
            score += 15
        else:
            score -= 10

    avg = sum(history) / len(history) if history else price

    if price < avg:
        score += 15
    else:
        score -= 5

    score += learning

    return max(0, min(score, 100))


def get_trend(price, history):
    if len(history) < 3:
        return "FLAT"

    short = price - history[-1]
    medium = history[-1] - history[-3]

    if short > 0 and medium > 0:
        return "STRONG UP 📈"

    if short < 0 and medium < 0:
        return "STRONG DOWN 📉"

    if short > 0:
        return "REVERSAL UP 🔄"

    if short < 0:
        return "REVERSAL DOWN 🔄"

    return "SIDEWAYS"


def get_volatility(history):
    if len(history) < 3:
        return "LOW"

    diffs = [abs(history[i] - history[i-1]) for i in range(1, len(history))]
    avg = sum(diffs) / len(diffs)

    if avg > 150:
        return "HIGH 🔥"
    if avg > 70:
        return "MEDIUM ⚡"

    return "LOW 🟢"


def predict_ml(price, history):
    if len(history) < 5:
        return price - 50, price + 50, "LOW"

    weights = [1, 2, 3, 4, 5]
    recent = history[-5:]

    weighted_avg = sum(w * p for w, p in zip(weights, recent)) / sum(weights)
    momentum = price - weighted_avg

    low = int(price - abs(momentum))
    high = int(price + abs(momentum))

    confidence = "HIGH" if abs(momentum) > 80 else "MEDIUM"

    return low, high, confidence


def short_term_decision(score, cash):
    if cash < 500:
        return "⛔ NO CASH"

    if score >= 75:
        return f"🟢 BUY ₹{min(2000, int(cash))}"

    if score <= 30:
        return "🔴 SELL ₹1000"

    return "⏳ HOLD"


def long_term_decision(score, bought):
    from datetime import datetime

    day = datetime.now().day

    if bought:
        return "✅ DONE"

    if day >= 23 or day <= 3:
        return "🟢 BUY NOW" if score >= 60 else "⏳ WAIT"

    return "⏳ OUTSIDE WINDOW"
