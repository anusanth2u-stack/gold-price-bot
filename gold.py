import requests
from bs4 import BeautifulSoup
import re

URL = "https://www.keralagold.com/kerala-gold-rate-per-gram.htm"

def get_gold_price():
    try:
        res = requests.get(URL, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text()

        match = re.search(r"Today\s*»Rs\.\s*([\d,]+)", text)
        
        if match:
            return match.group(1)
    except Exception as e:
        print("Error fetching price:", e)

    return None


def send_telegram(price):
    TOKEN = "8745874680:AAE1ICZiXUf3Xu8kHylh6mLYp7ZQNi1FxZ0"   # 🔴 Replace this
    CHAT_ID = "5400949107"

    message = f"💰 Gold Price Update\n1g (22K): ₹{price}"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.get(url, params={"chat_id": CHAT_ID, "text": message})


if __name__ == "__main__":
    price = get_gold_price()
    
    if price:
        send_telegram(price)
    else:
        print("Price not found")
