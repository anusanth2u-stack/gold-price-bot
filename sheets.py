import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime

def get_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")

    with open("credentials.json", "w") as f:
        f.write(creds_json)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)


def add_long_term(price):
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Long Term")

    amount = 15000
    grams = round(amount / price, 3)
    date = datetime.now().strftime("%Y-%m-%d")

    sheet.append_row([date, "Y", price, amount, grams])


def add_short_term(txn_type, amount, price):
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Short Term")

    grams = round(amount / price, 3)
    date = datetime.now().strftime("%Y-%m-%d")

    sheet.append_row([date, txn_type, price, amount, grams])


def get_long_term_summary():
    client = get_client()
    sheet = client.open("Gold Tracker").worksheet("Long Term")
    data = sheet.get_all_records()

    total_invested = sum([row["Amount"] for row in data]) if data else 0
    total_grams = sum([row["Grams"] for row in data]) if data else 0

    avg_price = total_invested / total_grams if total_grams else 0

    return total_invested, total_grams, avg_price
