import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

URL = "https://www.keralagold.com/kerala-gold-rate-per-gram.htm"


def get_price():
    try:
        res = requests.get(URL, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text()

        match = re.search(r"Today\s*»Rs\.\s*([\d,]+)", text)
        if match:
            return int(match.group(1).replace(",", ""))
    except:
        pass

    return None


# -------- SCORE --------
def calculate_score(price, history):
    score = 50

    if history:
        if price < history[-1]:
            score += 15
        else:
            score -= 10

    avg = sum(history)/len(history) if history else price

    if price < avg:
        score += 15
    else:
        score -= 5

    return max(0, min(score, 100))


# -------- TREND --------
def get_trend(price, history):
    if len(history) < 3:
        return "FLAT"

    short = price - history[-1]
    medium = history[-1] - history[-3]

    if short > 0 and medium > 0:
        return "STRONG UP 📈"

    if short < 0 and medium < 0:
        return "STRONG DOWN 📉"

    if short > 0 and medium < 0:
        return "REVERSAL UP 🔄"

    if short < 0 and medium > 0:
        return "REVERSAL DOWN 🔄"

    return "SIDEWAYS ⚖️"


# -------- VOLATILITY --------
def get_volatility(history):
    if len(history) < 3:
        return "LOW"

    diffs = [abs(history[i] - history[i-1]) for i in range(1, len(history))]
    avg_move = sum(diffs) / len(diffs)

    if avg_move > 150:
        return "HIGH 🔥"
    if avg_move > 70:
        return "MEDIUM ⚡"

    return "LOW 🟢"


# -------- PRICE PREDICTION --------
def predict_range(price, history):
    if len(history) < 3:
        return price - 50, price + 50

    diffs = [abs(history[i] - history[i-1]) for i in range(1, len(history))]
    avg_move = sum(diffs) / len(diffs)

    low = int(price - avg_move)
    high = int(price + avg_move)

    return low, high


# -------- REASONING --------
def get_reason(score, trend, volatility):
    if score >= 75:
        return "Strong dip — ideal buy zone"

    if score >= 60:
        return "Below average — good accumulation"

    if score <= 30:
        return "Overpriced — consider selling"

    if "STRONG DOWN" in trend:
        return "Falling trend — accumulate slowly"

    if "STRONG UP" in trend:
        return "Uptrend — wait for correction"

    if "REVERSAL" in trend:
        return "Trend reversal — early opportunity"

    if "HIGH" in volatility:
        return "High volatility — stagger buying"

    return "Stable market — hold position"


# -------- DECISIONS --------
def short_term_decision(score, cash):
    if cash < 500:
        return "⛔ NO CASH"

    if score >= 75:
        return f"🟢 BUY ₹{min(2000, int(cash))}"

    if score <= 30:
        return "🔴 SELL ₹1000"

    return "⏳ HOLD"


def long_term_decision(score, bought):
    today = datetime.now().day

    if bought:
        return "✅ DONE"

    if today >= 23 or today <= 3:
        if score >= 60:
            return "🟢 BUY NOW"
        return "⏳ WAIT"

    return "⏳ OUTSIDE WINDOW"
