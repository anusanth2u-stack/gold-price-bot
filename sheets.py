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


# ---------- SHORT TERM ----------
def get_short_term_metrics(price):
    sheet = get_client().open("Gold Tracker").worksheet("Short Term")
    data = sheet.get_all_records()

    invested = 0
    cash = 0
    gold = 0

    for row in data:
        typ = row["Type"]
        amt = safe_float(row["Amount"])
        grams = safe_float(row["Grams"])

        if typ == "BUDGET":
            cash += amt

        elif typ == "BUY":
            invested += amt
            cash -= amt
            gold += grams

        elif typ == "SELL":
            cash += amt
            gold -= grams

    gold_value = gold * price
    total_value = cash + gold_value

    profit = total_value - invested
    pct = (profit / invested * 100) if invested else 0

    return invested, cash, gold, gold_value, total_value, profit, pct


# ---------- LONG TERM ----------
def get_long_term_metrics(price):
    sheet = get_client().open("Gold Tracker").worksheet("Long Term")
    data = sheet.get_all_records()

    invested = 0
    gold = 0

    for row in data:
        invested += safe_float(row["Amount"])
        gold += safe_float(row["Grams"])

    value = gold * price
    profit = value - invested
    pct = (profit / invested * 100) if invested else 0

    return invested, gold, value, profit, pct


def already_bought_this_month():
    sheet = get_client().open("Gold Tracker").worksheet("Long Term")
    data = sheet.get_all_records()

    today = datetime.now()

    for row in data[::-1]:
        try:
            d = datetime.strptime(row["Date"], "%Y-%m-%d")
            if d.month == today.month:
                return True
        except:
            pass

    return False


# ---------- ADD TRANSACTIONS ----------
def add_short(txn, amount, price):
    sheet = get_client().open("Gold Tracker").worksheet("Short Term")

    grams = round(amount / price, 3)

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d"),
        txn,
        price,
        amount,
        grams,
        "",
        ""
    ])


def add_long(price):
    sheet = get_client().open("Gold Tracker").worksheet("Long Term")

    amount = 15000
    grams = round(amount / price, 3)

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d"),
        price,
        amount,
        grams
    ])
