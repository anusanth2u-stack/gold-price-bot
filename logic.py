import requests
from bs4 import BeautifulSoup
import re

URL = "https://www.keralagold.com/kerala-gold-rate-per-gram.htm"

def get_gold_price():
    res = requests.get(URL)
    soup = BeautifulSoup(res.text, "html.parser")
    text = soup.get_text()

    match = re.search(r"Today\s*»Rs\.\s*([\d,]+)", text)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def calculate_score(price, last_price=None):
    score = 50

    if last_price:
        if price < last_price:
            score += 20
        else:
            score -= 10

    return max(0, min(score, 100))
