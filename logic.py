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


# -------- SCORE --------
def calculate_score(price, history, learning):
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

    score += learning

    return max(0, min(score, 100))


# -------- TREND --------
def get_trend(price, history):
    if len(history) < 3:
        return "FLAT"

    short = price - history[-1]
    medium = history[-1] - history[-3]

    if short > 50 and medium > 50:
        return "STRONG UP 📈"

    if short < -50 and medium < -50:
        return "STRONG DOWN 📉"

    if short > 0:
        return "UP ↗️"

    if short < 0:
        return "DOWN ↘️"

    return "SIDEWAYS"


# -------- AI BUY SIZE --------
def get_buy_amount(score, cash):
    if cash < 500:
        return 0

    if score >= 80:
        return min(3000, cash)

    if score >= 65:
        return min(2000, cash)

    if score >= 55:
        return min(1000, cash)

    return 0


# -------- AI SELL SIZE --------
def get_sell_amount(profit_pct, gold_value):
    if gold_value <= 0:
        return 0

    if profit_pct >= 5:
        return gold_value * 0.5   # sell 50%

    if profit_pct >= 3:
        return gold_value * 0.3

    if profit_pct >= 2:
        return gold_value * 0.2

    return 0


# -------- FINAL DECISION --------
def short_term_ai(score, cash, profit_pct, gold_value):
    buy_amt = get_buy_amount(score, cash)
    sell_amt = get_sell_amount(profit_pct, gold_value)

    if sell_amt > 0:
        return "SELL", int(sell_amt)

    if buy_amt > 0:
        return "BUY", int(buy_amt)

    return "HOLD", 0
