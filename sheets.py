import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime


def safe(val):
    try:
        return float(val)
    except:
        return 0


def client():
    creds = os.environ.get("GOOGLE_CREDENTIALS")

    with open("cred.json", "w") as f:
        f.write(creds)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    auth = ServiceAccountCredentials.from_json_keyfile_name("cred.json", scope)
    return gspread.authorize(auth)


# ---------------- DATA ----------------

def log_data(price, trend, score):
    sheet = client().open("Gold Tracker").worksheet("Data")

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        price,
        trend,
        score
    ])


def get_history():
    sheet = client().open("Gold Tracker").worksheet("Data")
    data = sheet.get_all_values()[1:]

    prices = []
    for row in data[-10:]:
        try:
            prices.append(float(row[1]))
        except:
            pass

    return prices


# ---------------- SHORT TERM ----------------

def get_last_st():
    sheet = client().open("Gold Tracker").worksheet("Short Term")
    data = sheet.get_all_records()

    if not data:
        return 0, 0

    last = data[-1]
    return safe(last["Cash Balance"]), safe(last["Gold Holding"])


def add_budget():
    sheet = client().open("Gold Tracker").worksheet("Short Term")
    data = sheet.get_all_records()

    today = datetime.now()

    for row in data[::-1]:
        if row["Type"] == "BUDGET":
            d = datetime.strptime(row["Date"], "%Y-%m-%d")
            if d.month == today.month:
                return

    cash, gold = get_last_st()
    cash += 5000

    sheet.append_row([
        today.strftime("%Y-%m-%d"),
        "BUDGET",
        "",
        5000,
        "",
        round(cash, 2),
        round(gold, 3)
    ])


def add_short(txn, amount, price):
    sheet = client().open("Gold Tracker").worksheet("Short Term")

    cash, gold = get_last_st()

    grams = round(amount / price, 3)

    if txn == "BUY":
        if cash < amount:
            raise Exception("No cash")
        cash -= amount
        gold += grams

    elif txn == "SELL":
        if gold < grams:
            raise Exception("No gold")
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


def get_st_metrics(price):
    sheet = client().open("Gold Tracker").worksheet("Short Term")
    data = sheet.get_all_records()

    invested = 0

    for row in data:
        if row["Type"] == "BUY":
            invested += safe(row["Amount"])

    cash, gold = get_last_st()

    value = cash + gold * price
    profit = value - invested
    pct = (profit / invested * 100) if invested else 0

    return invested, cash, gold, value, profit, pct


# ---------------- LONG TERM ----------------

def get_lt_metrics(price):
    sheet = client().open("Gold Tracker").worksheet("Long Term")
    data = sheet.get_all_records()

    inv = 0
    gold = 0

    for r in data:
        inv += safe(r["Amount"])
        gold += safe(r["Grams"])

    val = gold * price
    profit = val - inv
    pct = (profit / inv * 100) if inv else 0

    return inv, gold, val, profit, pct


def already_bought():
    sheet = client().open("Gold Tracker").worksheet("Long Term")
    data = sheet.get_all_records()

    today = datetime.now()

    for r in data[::-1]:
        d = datetime.strptime(r["Date"], "%Y-%m-%d")
        if d.month == today.month:
            return True

    return False


def add_long(price):
    sheet = client().open("Gold Tracker").worksheet("Long Term")

    grams = round(15000 / price, 3)

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d"),
        price,
        15000,
        grams
    ])
