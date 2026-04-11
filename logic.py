import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

URL = "https://www.keralagold.com/kerala-gold-rate-per-gram.htm"

def get_price():
    res = requests.get(URL)
    soup = BeautifulSoup(res.text, "html.parser")
    text = soup.get_text()

    match = re.search(r"Today\s*»Rs\.\s*([\d,]+)", text)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def calculate_score(price, history):
    score = 50

    if history:
        if price < history[-1]:
            score += 20
        else:
            score -= 10

    if len(history) >= 3:
        if price < history[-1] < history[-2]:
            score += 20

    avg = sum(history)/len(history) if history else price

    if price < avg:
        score += 10
    else:
        score -= 5

    return max(0, min(score, 100))


def long_term_decision(score, bought):
    day = datetime.now().day

    if bought:
        return "✅ DONE"

    if score >= 70:
        return "🟢 BUY"

    if day >= 20:
        return "⚠️ FORCE BUY"

    return "⏳ WAIT"


def short_term_decision(score, cash):
    if score >= 75:
        return min(2000, cash), "BUY"

    if score <= 30:
        return 1000, "SELL"

    return 0, "HOLD"
