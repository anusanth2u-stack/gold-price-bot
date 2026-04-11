import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime


def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0


def get_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")

    with open("cred.json", "w") as f:
        f.write(creds_json)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name("cred.json", scope)
    return gspread.authorize(creds)


# -------- SUMMARY --------
def get_short_term_summary():
    sheet = get_client().open("Gold Tracker").worksheet("Short Term")
    data = sheet.get_all_records()

    if not data:
        return 0, 0

    last = data[-1]

    return safe_float(last.get("Cash Balance")), safe_float(last.get("Gold Holding"))


# -------- METRICS --------
def get_short_term_metrics(price):
    sheet = get_client().open("Gold Tracker").worksheet("Short Term")
    data = sheet.get_all_records()

    total_buy = 0
    total_sell = 0
    gold = 0

    for row in data:
        typ = row.get("Type")
        amt = safe_float(row.get("Amount"))
        grams = safe_float(row.get("Grams"))

        if typ == "BUY":
            total_buy += amt
            gold += grams

        elif typ == "SELL":
            total_sell += amt
            gold -= grams

    value = gold * price
    invested = total_buy - total_sell

    profit = value - invested
    pct = (profit / invested * 100) if invested > 0 else 0

    return profit, pct, gold, value


# -------- ADD ENTRY --------
def add_short(txn, amount, price):
    sheet = get_client().open("Gold Tracker").worksheet("Short Term")

    cash, gold = get_short_term_summary()

    grams = round(amount / price, 3) if price else 0

    if txn == "BUY":
        if cash < amount:
            raise Exception("Not enough cash")
        cash -= amount
        gold += grams

    elif txn == "SELL":
        if gold < grams:
            raise Exception("Not enough gold")
        cash += amount
        gold -= grams

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d"),
        txn,
        price,
        amount,
        grams,
        round(cash, 2),
        round(gold, 3)
    ])
