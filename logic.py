"""
logic.py — AI Decision Engine
==============================
Every decision is based on THREE pillars:

  1. MARKET SENTIMENT  (sentiment.py)
     - Fear & Greed, DXY, yields, crude, INR, Nifty, geopolitical, banking, news
     - Score 0-100: >65 bullish, <35 bearish, 35-65 neutral

  2. ML INSIGHT  (ml.py)
     - RSI, EMA crossover, momentum (5d + 10d), support/resistance
     - Score 0-100 + signal: BUY / NEUTRAL / SELL

  3. STOCK PERFORMANCE  (actual portfolio numbers from sheets.py)
     - Current P/L %, trend direction, position vs cycle low
     - Prevents buying into already-expensive positions
     - Prevents holding losers past stop loss

Decision = weighted vote of all three pillars.
"""

from datetime import datetime, date
import pytz

IST = pytz.timezone("Asia/Kolkata")


# ─────────────────────────────────────────────────────────────────────────────
# Trend
# ─────────────────────────────────────────────────────────────────────────────
def get_trend(price, history):
    """Interday trend using daily closes — last 10 days."""
    if len(history) < 3:
        return "SIDEWAYS", "Insufficient data"

    window    = history[-10:] if len(history) >= 10 else history
    mid       = len(window) // 2
    avg_early = sum(window[:mid]) / max(mid, 1)
    avg_late  = sum(window[mid:]) / max(len(window) - mid, 1)
    chg       = ((avg_late - avg_early) / avg_early * 100) if avg_early else 0

    if price > history[-2] and chg > 0.2:
        return "UP",       f"Uptrend +{round(chg,2)}% over recent days"
    elif price < history[-2] and chg < -0.2:
        return "DOWN",     f"Downtrend {round(chg,2)}% over recent days"
    else:
        return "SIDEWAYS", f"Consolidating ({round(chg,2)}%)"


# ─────────────────────────────────────────────────────────────────────────────
# Three-Pillar Score
# ─────────────────────────────────────────────────────────────────────────────
def _three_pillar_score(sent_score, ml_score, stock_score,
                        sent_w=0.40, ml_w=0.35, stock_w=0.25):
    """
    Combines the three scores into one composite (0-100).

    Weights (tunable):
      Sentiment  40% — macro & geopolitical context
      ML         35% — technical signal
      Stock      25% — portfolio performance reality check

    Returns (composite_score, interpretation_dict)
    """
    composite = round(
        sent_score  * sent_w +
        ml_score    * ml_w   +
        stock_score * stock_w
    )
    composite = max(0, min(100, composite))

    return composite, {
        "sentiment":  round(sent_score),
        "ml":         round(ml_score),
        "stock":      round(stock_score),
        "composite":  composite,
        "weights":    f"Sent {int(sent_w*100)}% / ML {int(ml_w*100)}% / Stock {int(stock_w*100)}%"
    }


def _stock_score_short(pct, trend, units, bees_price, cycle_low=None):
    """
    Stock performance score for short-term GoldBees position (0-100).
    Higher = more reason to buy / hold.

    Factors:
    - Current P/L: losing badly = sell; gaining well = hold/partial sell
    - Trend direction: up trend = bullish
    - Price vs support: near support = buy opportunity
    """
    score = 50  # neutral base

    # P/L based
    if pct <= -2.0:   score -= 30   # stop loss territory
    elif pct <= -1.0: score -= 15
    elif pct >= 8.0:  score -= 20   # overbought / take profit
    elif pct >= 5.0:  score -= 10   # partial profit zone
    elif pct >= 2.0:  score += 10   # healthy gain

    # Trend
    if trend == "UP":       score += 15
    elif trend == "DOWN":   score -= 10
    # SIDEWAYS = neutral, no change

    # No position = neutral (don't penalise for being in cash)
    if units == 0:
        score = max(score, 40)

    return max(10, min(90, score))


def _stock_score_long(price, cycle_low, avg_price, gold_trend):
    """
    Stock performance score for long-term Kalyan gold position (0-100).
    Higher = better time to buy.

    Factors:
    - Price vs cycle low: near low = great buy
    - Price vs historical avg: below avg = undervalued
    - Trend: downtrend = might go lower (wait) OR good dip
    """
    score = 50

    if cycle_low:
        pct_above = (price - cycle_low) / cycle_low * 100
        if pct_above <= 0.3:   score += 30   # at or below cycle low
        elif pct_above <= 1.0: score += 20
        elif pct_above <= 2.0: score += 5
        elif pct_above > 3.0:  score -= 15   # significantly above low

    if avg_price:
        pct_vs_avg = (price - avg_price) / avg_price * 100
        if pct_vs_avg < -3.0:   score += 20  # well below avg = strong buy
        elif pct_vs_avg < -1.0: score += 10
        elif pct_vs_avg > 3.0:  score -= 10  # above avg = less attractive

    if gold_trend == "DOWN":   score += 5   # dip = slight buy signal
    elif gold_trend == "UP":   score -= 5   # rising = might overpay

    return max(10, min(90, score))


# ─────────────────────────────────────────────────────────────────────────────
# Position sizing
# ─────────────────────────────────────────────────────────────────────────────
def _position_size(cash, composite, win_rate):
    """Scale position size to composite confidence."""
    if composite >= 75:   base = 0.50
    elif composite >= 65: base = 0.35
    elif composite >= 55: base = 0.22
    else:                 base = 0.12

    if win_rate >= 60:   base += 0.08
    elif win_rate < 40:  base -= 0.08

    base = max(0.10, min(base, 0.55))
    return int(cash * base / 100) * 100  # round to nearest ₹100


def _get_sl_target(price, trend):
    if trend == "DOWN":
        return round(price * 0.990, 2), round(price * 1.025, 2)
    elif trend == "UP":
        return round(price * 0.985, 2), round(price * 1.030, 2)
    else:
        return round(price * 0.988, 2), round(price * 1.020, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Short-Term AI (GoldBees interday)
# ─────────────────────────────────────────────────────────────────────────────
def short_term_ai(cash, pct, trend, ml_score, win_rate, price, units=0, sentiment=None):
    """
    GoldBees interday decision — three-pillar model.

    Pillar scores:
      Sentiment : from sentiment dict (0-100)
      ML        : from ml.short_term_ml score (0-100)
      Stock     : derived from P/L%, trend, position size

    Decision thresholds:
      Composite >= 65 → BUY signal
      Composite <= 35 → SELL signal
      35–65           → HOLD

    Hard overrides (take priority over composite):
      pct <= -2%  → stop loss SELL regardless
      pct >= 8%   → strong profit exit regardless
    """
    sent_score = sentiment.get("score", 50) if sentiment else 50
    stock_sc   = _stock_score_short(pct, trend, units, price)
    composite, breakdown = _three_pillar_score(sent_score, ml_score, stock_sc)

    reason_base = (
        f"Composite: {composite}/100 "
        f"[Sent:{breakdown['sentiment']} ML:{breakdown['ml']} Stock:{breakdown['stock']}]"
    )

    # ── Hard overrides ───────────────────────────────────────
    if pct <= -2.0 and units > 0:
        sell_amt = max(100, int(round(units * price * 0.6, -2)))
        sl, _    = _get_sl_target(price, trend)
        return "SELL", sell_amt, f"🛑 Stop loss ({round(pct,2)}%) — {reason_base}", sl, None

    if pct >= 8.0 and units > 0:
        sell_amt = max(100, int(round(units * price * 0.8, -2)))
        return "SELL", sell_amt, f"🎯 Strong profit exit ({round(pct,2)}%) — {reason_base}", None, None

    if pct >= 5.0 and units > 0:
        sell_amt = max(100, int(round(units * price * 0.4, -2)))
        return "SELL", sell_amt, f"✅ Partial profit ({round(pct,2)}%) — {reason_base}", None, None

    # ── Three-pillar decision ────────────────────────────────
    if composite >= 65 and cash > 500:
        amt     = _position_size(cash, composite, win_rate)
        sl, tgt = _get_sl_target(price, trend)
        return "BUY", amt, f"📈 Strong composite signal — {reason_base}", sl, tgt

    if composite <= 35 and units > 0:
        sell_amt = max(100, int(round(units * price * 0.4, -2)))
        return "SELL", sell_amt, f"📉 Weak composite signal — {reason_base}", None, None

    return "HOLD", 0, f"⏳ Mixed signals — {reason_base}", None, None


# ─────────────────────────────────────────────────────────────────────────────
# Kalyan cycle helpers
# ─────────────────────────────────────────────────────────────────────────────
def _kalyan_days_info():
    today = datetime.now(IST).date()
    if today.day <= 23:
        if today.month == 1:
            cycle_start = date(today.year - 1, 12, 24)
        else:
            cycle_start = date(today.year, today.month - 1, 24)
        deadline = date(today.year, today.month, 23)
    else:
        cycle_start = date(today.year, today.month, 24)
        if today.month == 12:
            deadline = date(today.year + 1, 1, 23)
        else:
            deadline = date(today.year, today.month + 1, 23)
    days_left = (deadline - datetime.now(IST).date()).days
    return days_left, cycle_start, deadline


# ─────────────────────────────────────────────────────────────────────────────
# Long-Term AI (Kalyan Scheme)
# ─────────────────────────────────────────────────────────────────────────────
def long_term_ai(bought, price, avg_price, gold_trend, gold_history,
                 cycle_low, ml_score, sentiment):
    """
    Kalyan scheme decision — three-pillar model.

    Rules:
    - BUY only (no sell — scheme is accumulation)
    - Must buy within cycle (24th → 23rd deadline)
    - Strategy: buy at lowest price of cycle

    Three-pillar logic:
      High composite + near cycle low   → BUY NOW
      High composite + price elevated   → BUY (sentiment supports it)
      Low composite  + price elevated   → WAIT for dip
      Low composite  + near cycle low   → BUY (it's the low, don't miss it)
      ≤ 3 days left  + any composite    → FORCE BUY (deadline)
    """
    days_left, _, deadline = _kalyan_days_info()
    deadline_str = deadline.strftime("%d %b")

    if bought:
        return "DONE", 0, f"✅ Kalyan investment done this cycle (deadline: {deadline_str})"

    sent_score = sentiment.get("score", 50) if sentiment else 50
    stock_sc   = _stock_score_long(price, cycle_low, avg_price, gold_trend)
    composite, breakdown = _three_pillar_score(sent_score, ml_score, stock_sc)

    pct_above_low = round((price - cycle_low) / cycle_low * 100, 2) if cycle_low else 0
    at_low        = cycle_low and price <= cycle_low * 1.005
    low_str       = f"₹{int(cycle_low)}" if cycle_low else "tracking..."
    score_str     = f"[Sent:{breakdown['sentiment']} ML:{breakdown['ml']} Stock:{breakdown['stock']}]"

    # ── Hard deadline override ───────────────────────────────
    if days_left <= 3:
        return "BUY", 15000, (
            f"⏰ {days_left}d to deadline — buying now regardless of signals.\n"
            f"   Composite: {composite}/100 {score_str}"
        )

    # ── At cycle low — always buy, this is the target ────────
    if at_low:
        return "BUY", 15000, (
            f"🟢 At cycle low {low_str} — exactly what we wait for.\n"
            f"   Composite: {composite}/100 {score_str}"
        )

    # ── Strong composite (all three pillars agree) → BUY ────
    if composite >= 68:
        return "BUY", 15000, (
            f"📈 Strong signal across all pillars — good entry.\n"
            f"   Composite: {composite}/100 {score_str}\n"
            f"   Price {pct_above_low}% above cycle low {low_str}"
        )

    # ── Weak composite + price elevated + time left → WAIT ──
    if composite <= 40 and pct_above_low > 1.0 and days_left > 7:
        return "WAIT", 0, (
            f"📉 Weak signals — price likely to fall further.\n"
            f"   Composite: {composite}/100 {score_str}\n"
            f"   Price {pct_above_low}% above cycle low {low_str} | {days_left}d left"
        )

    # ── Moderate composite + near low → acceptable entry ────
    if composite >= 50 and pct_above_low <= 1.5:
        return "BUY", 15000, (
            f"🟡 Moderate signal but near cycle low — acceptable entry.\n"
            f"   Composite: {composite}/100 {score_str}"
        )

    # ── Deadline safety net ──────────────────────────────────
    if days_left <= 7:
        return "BUY", 15000, (
            f"⏰ {days_left}d left — not worth risking deadline miss.\n"
            f"   Composite: {composite}/100 {score_str}\n"
            f"   Price {pct_above_low}% above cycle low {low_str}"
        )

    # ── Default: monitor ─────────────────────────────────────
    return "WAIT", 0, (
        f"⏳ Monitoring for better entry.\n"
        f"   Composite: {composite}/100 {score_str}\n"
        f"   Price {pct_above_low}% above cycle low {low_str} | {days_left}d left"
    )
