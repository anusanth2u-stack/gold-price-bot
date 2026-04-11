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


def get_history():
    sheet = get_client().open("Gold Tracker").worksheet("Data")
    rows = sheet.get_all_values()[1:]

    prices = []
    for row in rows[-10:]:
        if row and len(row) > 1 and row[1]:
            prices.append(safe_float(row[1]))

    return prices


def log_price(price, score):
    sheet = get_client().open("Gold Tracker").worksheet("Data")

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        price,
        "",
        score
    ])


def get_short_term_summary():
    sheet = get_client().open("Gold Tracker").worksheet("Short Term")
    data = sheet.get_all_records()

    if not data:
        return 0, 0

    last = data[-1]

    return safe_float(last.get("Cash Balance")), safe_float(last.get("Gold Holding"))


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


def get_long_summary():
    sheet = get_client().open("Gold Tracker").worksheet("Long Term")
    data = sheet.get_all_records()

    invested = sum(safe_float(r.get("Amount")) for r in data)
    grams = sum(safe_float(r.get("Grams")) for r in data)

    return invested, grams


def already_bought():
    sheet = get_client().open("Gold Tracker").worksheet("Long Term")
    data = sheet.get_all_records()

    today = datetime.now()

    for r in data:
        try:
            d = datetime.strptime(r["Date"], "%Y-%m-%d")
            if d.month == today.month:
                return True
        except:
            pass

    return False


def get_learning_factor(current_price):
    sheet = get_client().open("Gold Tracker").worksheet("Short Term")
    data = sheet.get_all_records()

    score = 0
    count = 0

    for row in data:
        if row.get("Type") == "BUY":
            buy_price = safe_float(row.get("Price"))
            diff = current_price - buy_price

            if diff > 100:
                score += 5
            elif diff < -100:
                score -= 5

            count += 1

    return int(score / count) if count else 0


def get_portfolio(price):
    st_cash, st_gold = get_short_term_summary()
    lt_inv, lt_gold = get_long_summary()

    total_gold = st_gold + lt_gold
    value = total_gold * price

    profit = value - lt_inv
    pct = (profit / lt_inv * 100) if lt_inv else 0

    return total_gold, value, profit, pct, st_cash
