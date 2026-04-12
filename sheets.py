import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")


def safe(x):
    try:
        return float(x)
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


def log_data(gold_price, gold_trend, gold_score, bees_price, bees_trend, bees_score):
    sheet = client().open("Gold Tracker").worksheet("Data")

    sheet.append_row([
        datetime.now(IST).strftime("%Y-%m-%d %H:%M"),
        gold_price,
        gold_trend,
        gold_score,
        bees_price,
        bees_trend,
        bees_score
    ])


def get_gold_history():
    data = client().open("Gold Tracker").worksheet("Data").get_all_values()[1:]
    return [safe(r[1]) for r in data if r[1]]


def get_bees_history():
    data = client().open("Gold Tracker").worksheet("Data").get_all_values()[1:]
    return [safe(r[4]) for r in data if r[4]]


def get_last_st():
    data = client().open("Gold Tracker").worksheet("Short Term").get_all_records()
    if not data:
        return 0, 0
    last = data[-1]
    return safe(last["Cash Balance"]), safe(last["Holding"])


def add_short(txn, amount, price):
    sheet = client().open("Gold Tracker").worksheet("Short Term")

    cash, units = get_last_st()
    qty = round(amount / price, 2)

    if txn == "BUY":
        cash -= amount
        units += qty
    else:
        cash += amount
        units -= qty

    sheet.append_row([
        datetime.now(IST).strftime("%Y-%m-%d"),
        txn,
        price,
        amount,
        qty,
        round(cash, 2),
        round(units, 2)
    ])


def get_st_metrics(price):
    data = client().open("Gold Tracker").worksheet("Short Term").get_all_records()

    invested = sum([safe(r["Amount"]) for r in data if r["Type"] == "BUY"])
    cash, units = get_last_st()

    value = cash + units * price
    profit = value - invested
    pct = (profit / invested * 100) if invested else 0

    return invested, cash, units, value, profit, pct


def get_st_history():
    return client().open("Gold Tracker").worksheet("Short Term").get_all_records()


def add_long(price):
    sheet = client().open("Gold Tracker").worksheet("Long Term")
    grams = round(15000 / price, 3)

    sheet.append_row([
        datetime.now(IST).strftime("%Y-%m-%d"),
        price,
        15000,
        grams
    ])


def get_lt_metrics(price):
    data = client().open("Gold Tracker").worksheet("Long Term").get_all_records()

    inv = sum([safe(r["Amount"]) for r in data])
    gold = sum([safe(r["Grams"]) for r in data])

    val = gold * price
    profit = val - inv
    pct = (profit / inv * 100) if inv else 0

    return inv, gold, val, profit, pct


def get_avg_buy_price():
    data = client().open("Gold Tracker").worksheet("Long Term").get_all_records()

    amt = sum([safe(r["Amount"]) for r in data])
    gold = sum([safe(r["Grams"]) for r in data])

    return amt / gold if gold else 0


def already_bought():
    data = client().open("Gold Tracker").worksheet("Long Term").get_all_records()

    today = datetime.now(IST)
    for r in data[::-1]:
        if r["Date"].startswith(today.strftime("%Y-%m")):
            return True
    return False
