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


# -------- HISTORY --------
def get_history():
    sheet = get_client().open("Gold Tracker").worksheet("Data")
    values = sheet.col_values(2)[1:]
    return [int(v) for v in values[-10:] if v]


# -------- LEARNING --------
def get_learning_factor(current_price):
    sheet = get_client().open("Gold Tracker").worksheet("Short Term")
    data = sheet.get_all_records()

    if not data:
        return 0

    score = 0
    count = 0

    for row in data:
        if row["Type"] == "BUY":
            buy_price = float(row["Price"])

            # evaluate after buy
            diff = current_price - buy_price

            if diff > 100:
                score += 5   # good buy
            elif diff < -100:
                score -= 5   # bad buy

            count += 1

    return score // count if count else 0


# -------- SHORT TERM --------
def get_short_term_summary():
    sheet = get_client().open("Gold Tracker").worksheet("Short Term")
    data = sheet.get_all_records()

    if not data:
        return 0, 0

    last = data[-1]
    return float(last["Cash Balance"] or 0), float(last["Gold Holding"] or 0)


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


# -------- LONG TERM --------
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

    invested = sum(float(r["Amount"]) for r in data) if data else 0
    grams = sum(float(r["Grams"]) for r in data) if data else 0

    return invested, grams


def already_bought():
    sheet = get_client().open("Gold Tracker").worksheet("Long Term")
    data = sheet.get_all_records()

    today = datetime.now()

    for r in data:
        d = datetime.strptime(r["Date"], "%Y-%m-%d")
        if d.month == today.month:
            return True

    return False


# -------- PORTFOLIO --------
def get_portfolio(price):
    st_cash, st_gold = get_short_term_summary()
    lt_inv, lt_gold = get_long_summary()

    total_gold = st_gold + lt_gold
    value = total_gold * price

    profit = value - lt_inv
    pct = (profit / lt_inv * 100) if lt_inv else 0

    return total_gold, value, profit, pct, st_cash


# -------- DATA --------
def log_price(price, score):
    sheet = get_client().open("Gold Tracker").worksheet("Data")

    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        price,
        "",
        score
    ])
