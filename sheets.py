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


def ensure_monthly_budget():
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Short Term")

    data = sheet.get_all_records()
    today = datetime.now()
    current_month = today.strftime("%Y-%m")

    for row in data:
        if row["Type"] == "BUDGET" and row["Date"].startswith(current_month):
            return

    sheet.append_row([
        today.strftime("%Y-%m-%d"),
        "BUDGET",
        "",
        5000,
        "",
        "",
        ""
    ])


def add_transaction(txn_type, amount, price):
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Short Term")

    grams = round(amount / price, 3)

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d"),
        txn_type,
        price,
        amount,
        grams,
        "",
        ""
    ])


def get_summary():
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Short Term")

    data = sheet.get_all_records()

    if not data:
        return 0, 0

    last = data[-1]

    cash = float(last.get("Cash Balance") or 0)
    gold = float(last.get("Gold Holding") or 0)

    return cash, gold


def get_history():
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Data")

    values = sheet.col_values(2)[1:]

    return [int(v) for v in values[-5:] if v]


def log_price(price, score):
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Data")

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        price,
        "",
        score
    ])
