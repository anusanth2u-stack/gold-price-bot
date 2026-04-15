import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime, date
import pytz

IST = pytz.timezone("Asia/Kolkata")


def safe(x):
    try:
        return float(x)
    except:
        return 0


def client():
    creds = os.environ.get("GOOGLE_CREDENTIALS")
    if isinstance(creds, str):
        creds_data = json.loads(creds)
    else:
        creds_data = creds
    with open("cred.json", "w") as f:
        json.dump(creds_data, f)
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


def _aggregate_daily(rows, col_index):
    """Last price of each day — prevents same-day hourly bias."""
    daily = {}
    for r in rows:
        if not r[col_index]:
            continue
        date_str = r[0][:10]
        daily[date_str] = safe(r[col_index])
    return [daily[d] for d in sorted(daily.keys())]


def get_gold_daily():
    data = client().open("Gold Tracker").worksheet("Data").get_all_values()[1:]
    return _aggregate_daily(data, 1)


def get_bees_daily():
    data = client().open("Gold Tracker").worksheet("Data").get_all_values()[1:]
    return _aggregate_daily(data, 4)


def get_kalyan_cycle_low():
    """
    Returns the lowest gold price within the current Kalyan cycle.
    Cycle: 24th of previous month → 23rd of current month.
    e.g. today = Apr 15 → cycle start = Mar 24, cycle end = Apr 23.
    """
    now  = datetime.now(IST)
    today = now.date()

    # Determine cycle start date
    if today.day <= 23:
        # We are in the window: cycle started on 24th of previous month
        if today.month == 1:
            cycle_start = date(today.year - 1, 12, 24)
        else:
            cycle_start = date(today.year, today.month - 1, 24)
    else:
        # Past 23rd: cycle just started on 24th of this month
        cycle_start = date(today.year, today.month, 24)

    cycle_start_str = cycle_start.strftime("%Y-%m-%d")

    data = client().open("Gold Tracker").worksheet("Data").get_all_values()[1:]
    prices = [
        safe(r[1]) for r in data
        if r[0] >= cycle_start_str and r[1]
    ]
    return min(prices) if prices else None


def get_last_st():
    data = client().open("Gold Tracker").worksheet("Short Term").get_all_records()
    if not data:
        return 0, 0
    for r in reversed(data):
        cb = r.get("Cash Balance", "")
        h  = r.get("Holding", "")
        if cb != "" and h != "":
            return safe(cb), safe(h)
    return 0, 0


def add_short(txn, amount, price):
    sheet = client().open("Gold Tracker").worksheet("Short Term")
    cash, units = get_last_st()
    qty = round(amount / price, 2)

    if txn == "BUY":
        if amount > cash:
            raise ValueError(f"Insufficient cash. Available: ₹{round(cash,2)}, Required: ₹{amount}")
        cash  -= amount
        units += qty
    elif txn == "SELL":
        if qty > units:
            qty    = round(units, 2)
            amount = round(qty * price, 2)
        if qty <= 0:
            raise ValueError("No units available to sell")
        cash  += amount
        units  = round(units - qty, 2)

    sheet.append_row([
        datetime.now(IST).strftime("%Y-%m-%d"),
        txn,
        price,
        round(amount, 2),
        qty,
        round(cash, 2),
        round(units, 2)
    ])


def get_st_metrics(price):
    data = client().open("Gold Tracker").worksheet("Short Term").get_all_records()
    cash, units = get_last_st()
    holding_value = units * price

    cost_basis    = 0.0
    running_units = 0.0
    for r in data:
        row_type = str(r.get("Type", "")).strip().upper()
        if row_type not in ("BUY", "SELL"):
            continue
        if row_type == "BUY":
            running_units += safe(r["Units"])
            cost_basis    += safe(r["Amount"])
        elif row_type == "SELL" and running_units > 0:
            avg            = cost_basis / running_units
            sold_qty       = safe(r["Units"])
            cost_basis    -= avg * sold_qty
            running_units -= sold_qty

    profit = holding_value - cost_basis
    pct    = (profit / cost_basis * 100) if cost_basis else 0
    value  = cash + holding_value
    return cost_basis, cash, units, value, profit, pct


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
    data   = client().open("Gold Tracker").worksheet("Long Term").get_all_records()
    inv    = sum(safe(r["Amount"]) for r in data)
    gold   = sum(safe(r["Grams"])  for r in data)
    val    = gold * price
    profit = val - inv
    pct    = (profit / inv * 100) if inv else 0
    return inv, gold, val, profit, pct


def get_avg_buy_price():
    data = client().open("Gold Tracker").worksheet("Long Term").get_all_records()
    amt  = sum(safe(r["Amount"]) for r in data)
    gold = sum(safe(r["Grams"])  for r in data)
    return amt / gold if gold else 0


def already_bought():
    """
    Returns True if Kalyan purchase already made in the current cycle.
    Cycle: 24th of last month → 23rd of this month.
    """
    now   = datetime.now(IST)
    today = now.date()

    if today.day <= 23:
        if today.month == 1:
            cycle_start = date(today.year - 1, 12, 24)
        else:
            cycle_start = date(today.year, today.month - 1, 24)
    else:
        cycle_start = date(today.year, today.month, 24)

    cycle_start_str = cycle_start.strftime("%Y-%m-%d")

    data = client().open("Gold Tracker").worksheet("Long Term").get_all_records()
    for r in data:
        if str(r.get("Date", "")) >= cycle_start_str:
            return True
    return False
