def get_short_term_metrics(price):
    data = sheet.get_all_records()

    invested = 0
    cash = 0
    gold = 0

    for row in data:
        typ = row["Type"]
        amt = float(row["Amount"] or 0)
        grams = float(row["Grams"] or 0)

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
