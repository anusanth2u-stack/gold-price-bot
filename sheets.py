import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime

def get_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")

    with open("cred.json", "w") as f:
        f.write(creds_json)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name("cred.json", scope)
    return gspread.authorize(creds)


def log_price(price, score):
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Data")

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        price,
        "",
        score
    ])


def get_history():
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Data")
    data = sheet.col_values(2)[1:]
    return [int(x) for x in data[-5:]]


def long_term_buy(price):
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Long Term")

    amount = 15000
    grams = round(amount / price, 3)

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d"),
        "Y",
        price,
        amount,
        grams
    ])


def short_term_txn(txn_type, amount, price):
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Short Term")

    grams = round(amount / price, 3)

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d"),
        txn_type,
        price,
        amount,
        grams
    ])


def get_long_term_summary():
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Long Term")
    data = sheet.get_all_records()

    invested = sum([r["Amount"] for r in data]) if data else 0
    grams = sum([r["Grams"] for r in data]) if data else 0

    avg = invested / grams if grams else 0

    return invested, grams, avg


def get_short_term_summary():
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Short Term")
    data = sheet.get_all_records()

    cash = 5000
    grams = 0

    for r in data:
        if r["Type"] == "BUY":
            cash -= r["Amount"]
            grams += r["Grams"]
        else:
            cash += r["Amount"]
            grams -= r["Grams"]

    return cash, grams


def already_bought_this_month():
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Long Term")
    data = sheet.get_all_records()

    today = datetime.now()

    for r in reversed(data):
        d = datetime.strptime(r["Date"], "%Y-%m-%d")
        if d.month == today.month:
            return True

    return False
