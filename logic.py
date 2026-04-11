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
            return int(match.group(1).replace(",", ""))
    except:
        pass

    return None


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


def short_term_decision(score, cash):
    if cash < 500:
        return "⛔ NO CASH"

    if score >= 75:
        return f"🟢 BUY ₹{min(2000, int(cash))}"

    if score <= 30:
        return "🔴 SELL ₹1000"

    return "⏳ HOLD"
