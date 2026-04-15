"""
sentiment.py — Comprehensive Gold Price Sentiment Engine (India)
================================================================
Covers ALL major factors that affect gold price in India:

GLOBAL MACRO
  1. Fear & Greed Index        — market panic = safe haven gold demand
  2. US Dollar Index (DXY)     — inverse relationship with gold
  3. US 10Y Treasury Yield     — opportunity cost of holding gold
  4. US Federal Reserve news   — rate decisions move gold significantly
  5. Crude Oil (WTI)           — inflation proxy, correlated with gold
  6. Global equity markets     — risk-off = gold up

GEOPOLITICAL
  7. War / conflict news       — uncertainty = gold safe haven
  8. Sanctions / trade war     — dollar alternatives = gold up

INDIA-SPECIFIC
  9. INR/USD exchange rate     — weak rupee = higher gold price in INR
 10. Indian inflation (CPI)    — high inflation = gold hedge
 11. RBI policy / repo rate    — rate hikes = bearish gold
 12. India import duty         — direct price impact
 13. Wedding / festival season — demand spike (Diwali, Akshaya Tritiya)
 14. India equity (Nifty)      — risk-off from Nifty = gold up

BANKING & FINANCIAL
 15. Banking sector stress      — bank failures = gold safe haven
 16. ETF flows (gold ETF AUM)   — institutional demand signal
"""

import requests
import xml.etree.ElementTree as ET
import re
import json
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

# ─────────────────────────────────────────────────────────────────────────────
# Keyword lists
# ─────────────────────────────────────────────────────────────────────────────

GOLD_BULLISH = [
    # Safe haven / fear
    "war", "conflict", "attack", "missile", "sanction", "crisis", "tension",
    "geopolit", "uncertainty", "recession", "collapse", "bank fail",
    "bank run", "default", "debt crisis", "contagion", "panic",
    # Inflation / monetary
    "inflation", "cpi rise", "price rise", "rate cut", "fed pause",
    "fed hold", "dovish", "stimulus", "quantitative easing", "qe",
    "money printing", "fiscal deficit",
    # Dollar weakness
    "weak dollar", "dollar fall", "dollar drop", "dxy fall",
    "dollar index drop", "usd weak",
    # Demand
    "demand surge", "import surge", "festival", "wedding season",
    "diwali", "akshaya tritiya", "dhanteras", "navratri", "jewellery demand",
    "etf inflow", "gold etf buy", "central bank buy", "reserve buy",
    # Supply
    "supply crunch", "mine output fall", "production cut",
    # India specific
    "rupee fall", "inr weak", "rupee deprecia", "inr deprecia",
    "india import", "duty cut", "import duty reduction",
]

GOLD_BEARISH = [
    # Risk-on
    "rate hike", "hawkish", "fed hike", "rbi hike", "repo rate hike",
    "interest rate rise", "yield rise", "bond yield up", "taper",
    "quantitative tightening", "qt",
    # Dollar strength
    "strong dollar", "dollar rise", "dollar surge", "dxy rise",
    "dollar index up", "usd strong",
    # Demand drop
    "etf outflow", "gold etf sell", "profit booking", "gold sell",
    "jewellery demand fall", "import fall", "duty hike", "import duty hike",
    # Risk-on / equity rally
    "equity rally", "stock market high", "nifty high", "sensex high",
    "risk appetite", "bull market", "economic recovery",
    # India specific
    "rupee rise", "inr strong", "rupee appreciate", "rbi intervention",
    "forex reserve high",
    # Macro
    "deflation", "low inflation", "disinflation", "cpi fall",
]


def _safe_get(url, timeout=7, headers=None):
    try:
        h = headers or {"User-Agent": "Mozilla/5.0 (compatible; GoldBot/1.0)"}
        r = requests.get(url, headers=h, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  ✗ Fetch [{url[:55]}...]: {e}")
        return None


def _yahoo_close(ticker, range_="5d", interval="1d"):
    """Fetch last 2 closes from Yahoo Finance. Returns (current, prev, change_pct)."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={range_}"
        r   = _safe_get(url)
        if not r:
            return None, None, None
        data   = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        if len(closes) < 2:
            return None, None, None
        curr   = round(closes[-1], 4)
        prev   = closes[-2]
        chg    = round((curr - prev) / prev * 100, 3)
        return curr, prev, chg
    except Exception as e:
        print(f"  ✗ Yahoo [{ticker}]: {e}")
        return None, None, None


# ─────────────────────────────────────────────────────────────────────────────
# 1. Fear & Greed Index
# ─────────────────────────────────────────────────────────────────────────────
def get_fear_greed():
    try:
        r = _safe_get("https://production.dataviz.cnn.io/index/fearandgreed/v1/historical")
        if not r:
            return None, "NA", 50
        d     = r.json()["fear_and_greed"]
        score = round(d["score"], 1)
        label = d["rating"]
        # Fear = bullish gold (safe haven), Greed = bearish gold
        if score <= 25:   gold_score = 85
        elif score <= 40: gold_score = 70
        elif score <= 55: gold_score = 50
        elif score <= 70: gold_score = 35
        else:             gold_score = 20
        return score, label, gold_score
    except Exception as e:
        print("  ✗ Fear&Greed:", e)
        return None, "NA", 50


# ─────────────────────────────────────────────────────────────────────────────
# 2. USD Index (DXY) — inverse to gold
# ─────────────────────────────────────────────────────────────────────────────
def get_dxy():
    curr, _, chg = _yahoo_close("DX-Y.NYB")
    if curr is None:
        return None, None, 50, "NA"
    # DXY up → gold bearish
    gold_score = max(10, min(90, 50 - chg * 25))
    impl = (
        "BEARISH — strong USD suppresses gold" if chg >= 0.3 else
        "BULLISH — weak USD lifts gold"        if chg <= -0.3 else
        "NEUTRAL"
    )
    return curr, chg, gold_score, impl


# ─────────────────────────────────────────────────────────────────────────────
# 3. US 10Y Treasury Yield — opportunity cost
# ─────────────────────────────────────────────────────────────────────────────
def get_treasury_yield():
    curr, _, chg = _yahoo_close("%5ETNX")
    if curr is None:
        return None, None, 50, "NA"
    gold_score = max(10, min(90, 50 - chg * 80))
    impl = (
        "BEARISH — rising yields hurt gold" if chg >= 0.05 else
        "BULLISH — falling yields help gold" if chg <= -0.05 else
        "NEUTRAL"
    )
    return curr, chg, gold_score, impl


# ─────────────────────────────────────────────────────────────────────────────
# 4. Crude Oil (WTI) — inflation proxy, correlated with gold
# ─────────────────────────────────────────────────────────────────────────────
def get_crude_oil():
    curr, _, chg = _yahoo_close("CL=F")
    if curr is None:
        return None, None, 50, "NA"
    # Oil up → inflation fears → gold up (mild positive correlation)
    gold_score = max(20, min(80, 50 + chg * 5))
    impl = (
        "MILDLY BULLISH — rising oil signals inflation, supports gold" if chg >= 1.0 else
        "MILDLY BEARISH — falling oil reduces inflation fears"         if chg <= -1.0 else
        "NEUTRAL"
    )
    return curr, chg, gold_score, impl


# ─────────────────────────────────────────────────────────────────────────────
# 5. INR/USD Exchange Rate — weak INR = higher gold price in India
# ─────────────────────────────────────────────────────────────────────────────
def get_inr_usd():
    curr, _, chg = _yahoo_close("INR=X")
    if curr is None:
        return None, None, 50, "NA"
    # INR/USD up = more rupees per dollar = rupee weakening = gold costs more in INR
    # chg > 0 means rupee is weaker → bullish for gold in India
    gold_score = max(10, min(90, 50 + chg * 30))
    impl = (
        f"BULLISH — INR weakened ({chg:+.3f}%), gold costs more in ₹" if chg >= 0.1 else
        f"BEARISH — INR strengthened ({chg:+.3f}%), gold cheaper in ₹" if chg <= -0.1 else
        "NEUTRAL — INR stable"
    )
    return curr, chg, gold_score, impl


# ─────────────────────────────────────────────────────────────────────────────
# 6. India Equity — Nifty 50 (risk-off = gold up)
# ─────────────────────────────────────────────────────────────────────────────
def get_nifty():
    curr, _, chg = _yahoo_close("%5ENSEBANK")   # Nifty Bank as proxy
    nifty, _, nifty_chg = _yahoo_close("%5ENSEI")  # Nifty 50
    val  = nifty  or curr
    chg_ = nifty_chg or chg
    if val is None:
        return None, None, 50, "NA"
    # Nifty up = risk-on = bearish for gold; Nifty down = risk-off = bullish gold
    gold_score = max(10, min(90, 50 - chg_ * 8))
    impl = (
        "BEARISH — equity rally reduces gold safe-haven appeal" if chg_ >= 1.0 else
        "BULLISH — equity weakness drives gold safe-haven demand" if chg_ <= -1.0 else
        "NEUTRAL"
    )
    return val, chg_, gold_score, impl


# ─────────────────────────────────────────────────────────────────────────────
# 7. Global Equity (S&P 500) — broad risk sentiment
# ─────────────────────────────────────────────────────────────────────────────
def get_sp500():
    curr, _, chg = _yahoo_close("%5EGSPC")
    if curr is None:
        return None, None, 50, "NA"
    gold_score = max(10, min(90, 50 - chg * 6))
    impl = (
        "BEARISH — global risk-on, investors exit gold" if chg >= 1.0 else
        "BULLISH — global risk-off, investors flee to gold" if chg <= -1.0 else
        "NEUTRAL"
    )
    return curr, chg, gold_score, impl


# ─────────────────────────────────────────────────────────────────────────────
# 8. India Season / Festival Demand
# ─────────────────────────────────────────────────────────────────────────────
def get_seasonal_demand():
    """
    India gold demand peaks during:
    - Akshaya Tritiya (Apr–May)
    - Navratri / Dussehra (Oct)
    - Dhanteras / Diwali (Oct–Nov)
    - Wedding season (Nov–Dec, Apr–May)
    Returns (season_name, demand_level, gold_score)
    """
    month = datetime.now(IST).month
    day   = datetime.now(IST).day

    # High demand periods
    if month in (4, 5):
        return "Akshaya Tritiya / Wedding Season", "HIGH", 75
    elif month == 10:
        return "Navratri / Dussehra", "HIGH", 72
    elif month == 11:
        return "Dhanteras / Diwali / Wedding Season", "VERY HIGH", 85
    elif month == 12:
        return "Wedding Season", "MODERATE-HIGH", 65
    elif month in (1, 2):
        return "Wedding Season (south India)", "MODERATE", 58
    elif month == 3:
        return "Gudi Padwa / Ugadi", "MODERATE", 55
    else:
        return "Off-season", "LOW", 40


# ─────────────────────────────────────────────────────────────────────────────
# 9. News Sentiment — comprehensive gold & macro keywords
# ─────────────────────────────────────────────────────────────────────────────
def get_news_sentiment():
    feeds = [
        "https://news.google.com/rss/search?q=gold+price+india&hl=en-IN&gl=IN&ceid=IN:en",
        "https://news.google.com/rss/search?q=gold+rate+rupee&hl=en-IN&gl=IN&ceid=IN:en",
        "https://news.google.com/rss/search?q=war+sanctions+geopolitical+gold&hl=en&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=federal+reserve+interest+rate+gold&hl=en&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=rbi+repo+rate+india+economy&hl=en-IN&gl=IN&ceid=IN:en",
        "https://economictimes.indiatimes.com/markets/commodities/rss.cms",
    ]

    all_text = []
    headlines = []

    for url in feeds:
        try:
            r = _safe_get(url)
            if not r:
                continue
            root = ET.fromstring(r.content)
            for item in list(root.iter("item"))[:8]:
                title = re.sub(r"<[^>]+>", "", item.findtext("title") or "").strip()
                desc  = re.sub(r"<[^>]+>", "", item.findtext("description") or "").strip()
                combined = (title + " " + desc).lower()
                all_text.append(combined)
                if title and len(headlines) < 5:
                    headlines.append(title)
        except Exception as e:
            print(f"  ✗ RSS [{url[:40]}]:", e)

    if not all_text:
        return 50, 0, []

    bull = sum(sum(1 for w in GOLD_BULLISH if w in t) for t in all_text)
    bear = sum(sum(1 for w in GOLD_BEARISH if w in t) for t in all_text)
    total = bull + bear
    score = int((bull / total) * 100) if total > 0 else 50

    return score, len(all_text), headlines[:5]


# ─────────────────────────────────────────────────────────────────────────────
# 10. Banking Sector Stress
# ─────────────────────────────────────────────────────────────────────────────
def get_banking_stress():
    """
    Checks news for banking sector stress keywords.
    Bank failures / stress = safe haven gold demand.
    """
    bank_stress_words = [
        "bank fail", "bank collapse", "bank run", "banking crisis",
        "svb", "credit suisse", "nbfc crisis", "npa rise",
        "bad loan", "bank stress", "liquidity crisis", "bank default",
        "fdic", "bank rescue", "bank bailout", "financial contagion"
    ]
    bank_stable_words = [
        "bank profit", "banking sector strong", "npa fall", "credit growth",
        "bank earnings beat", "bank recovery", "capital adequate"
    ]

    try:
        url = "https://news.google.com/rss/search?q=banking+crisis+bank+failure+india&hl=en&gl=IN&ceid=IN:en"
        r   = _safe_get(url)
        if not r:
            return "NA", 50

        root  = ET.fromstring(r.content)
        texts = []
        for item in list(root.iter("item"))[:10]:
            title = re.sub(r"<[^>]+>", "", item.findtext("title") or "").lower()
            texts.append(title)

        stress_count = sum(sum(1 for w in bank_stress_words if w in t) for t in texts)
        stable_count = sum(sum(1 for w in bank_stable_words if w in t) for t in texts)

        if stress_count >= 2:
            return "STRESSED", 80   # bullish for gold
        elif stress_count == 1:
            return "MILD STRESS", 62
        elif stable_count >= 2:
            return "STABLE", 40
        else:
            return "NEUTRAL", 50

    except Exception as e:
        print("  ✗ Banking stress:", e)
        return "NA", 50


# ─────────────────────────────────────────────────────────────────────────────
# 11. Geopolitical Risk
# ─────────────────────────────────────────────────────────────────────────────
def get_geopolitical_risk():
    """
    Monitors war, sanctions, trade war, terrorism keywords.
    High geopolitical risk = strong bullish for gold.
    """
    high_risk = [
        "war", "missile strike", "bombing", "invasion", "military attack",
        "nuclear threat", "sanction", "embargo", "trade war", "tariff war",
        "terrorist attack", "coup", "civil war", "conflict escalat",
        "nato", "russia ukraine", "israel gaza", "iran", "taiwan strait",
        "south china sea", "north korea"
    ]
    low_risk = [
        "ceasefire", "peace deal", "peace talks", "truce", "diplomacy",
        "de-escalat", "trade deal", "sanction lift", "normalization"
    ]

    try:
        url = "https://news.google.com/rss/search?q=war+conflict+geopolitical+sanctions+2025&hl=en&gl=US&ceid=US:en"
        r   = _safe_get(url)
        if not r:
            return "UNKNOWN", 50

        root  = ET.fromstring(r.content)
        texts = []
        for item in list(root.iter("item"))[:15]:
            title = re.sub(r"<[^>]+>", "", item.findtext("title") or "").lower()
            desc  = re.sub(r"<[^>]+>", "", item.findtext("description") or "").lower()
            texts.append(title + " " + desc)

        risk_count  = sum(sum(1 for w in high_risk if w in t) for t in texts)
        peace_count = sum(sum(1 for w in low_risk  if w in t) for t in texts)

        if risk_count >= 5:
            return "HIGH RISK", 85
        elif risk_count >= 2:
            return "MODERATE RISK", 68
        elif peace_count >= 2:
            return "LOW RISK", 38
        else:
            return "MODERATE RISK", 55

    except Exception as e:
        print("  ✗ Geopolitical:", e)
        return "UNKNOWN", 50


# ─────────────────────────────────────────────────────────────────────────────
# Master aggregator
# ─────────────────────────────────────────────────────────────────────────────
def get_combined_sentiment():
    """
    Combines all 11 factors into one gold sentiment score (0–100).

    Weights (tuned for Indian gold market):
      Fear & Greed       10%   — global risk mood
      DXY                15%   — strongest inverse driver
      US 10Y Yield       12%   — opportunity cost
      Crude Oil           5%   — inflation proxy
      INR/USD            12%   — India-specific amplifier
      Nifty               5%   — local risk sentiment
      S&P 500             5%   — global risk sentiment
      News sentiment     15%   — real-time keyword signal
      Geopolitical       10%   — safe haven trigger
      Banking stress      6%   — systemic risk
      Seasonal demand     5%   — India demand calendar

    Returns dict with score, label, summary and all sub-scores.
    """
    print("📡 Fetching sentiment data...")

    fg_score, fg_label, fg_gold         = get_fear_greed()
    dxy_val, dxy_chg, dxy_gold, dxy_impl= get_dxy()           
    yld_val, yld_chg, yld_gold, yld_impl= get_treasury_yield()
    oil_val, oil_chg, oil_gold, oil_impl= get_crude_oil()
    inr_val, inr_chg, inr_gold, inr_impl= get_inr_usd()
    nft_val, nft_chg, nft_gold, nft_impl= get_nifty()
    sp_val,  sp_chg,  sp_gold,  sp_impl = get_sp500()
    news_score, news_cnt, headlines      = get_news_sentiment()
    geo_label, geo_gold                  = get_geopolitical_risk()
    bank_label, bank_gold                = get_banking_stress()
    season_name, season_level, sea_gold  = get_seasonal_demand()

    # Handle None scores
    def s(val, default=50):
        return val if val is not None else default

    # Weighted composite
    factors = [
        (s(fg_gold),    0.10, "Fear & Greed"),
        (s(dxy_gold),   0.15, "DXY"),
        (s(yld_gold),   0.12, "US 10Y Yield"),
        (s(oil_gold),   0.05, "Crude Oil"),
        (s(inr_gold),   0.12, "INR/USD"),
        (s(nft_gold),   0.05, "Nifty"),
        (s(sp_gold),    0.05, "S&P 500"),
        (news_score,    0.15, "News"),
        (s(geo_gold),   0.10, "Geopolitical"),
        (s(bank_gold),  0.06, "Banking"),
        (sea_gold,      0.05, "Seasonal"),
    ]

    combined = int(round(sum(sc * wt for sc, wt, _ in factors)))
    combined = max(0, min(100, combined))

    if combined >= 65:
        label   = "BULLISH 🟢"
        summary = "Multiple factors favour gold — good time to consider buying"
    elif combined <= 35:
        label   = "BEARISH 🔴"
        summary = "Multiple factors working against gold — consider waiting"
    else:
        label   = "NEUTRAL 🟡"
        summary = "Mixed signals — no strong directional bias"

    # Top 3 bullish / bearish factors for explanation
    sorted_factors = sorted(factors, key=lambda x: abs(x[0] - 50), reverse=True)
    top_drivers = []
    for sc, wt, name in sorted_factors[:3]:
        if sc >= 60:
            top_drivers.append(f"↑ {name} (bullish)")
        elif sc <= 40:
            top_drivers.append(f"↓ {name} (bearish)")

    return {
        "score":         combined,
        "label":         label,
        "summary":       summary,
        "top_drivers":   top_drivers,
        # Sub-scores
        "fear_greed":    (fg_score,  fg_label,     fg_gold),
        "dxy":           (dxy_val,   dxy_chg,      dxy_gold,  dxy_impl  if dxy_val  else "NA"),
        "yield_10y":     (yld_val,   yld_chg,      yld_gold,  yld_impl  if yld_val  else "NA"),
        "crude_oil":     (oil_val,   oil_chg,      oil_gold,  oil_impl  if oil_val  else "NA"),
        "inr_usd":       (inr_val,   inr_chg,      inr_gold,  inr_impl  if inr_val  else "NA"),
        "nifty":         (nft_val,   nft_chg,      nft_gold,  nft_impl  if nft_val  else "NA"),
        "sp500":         (sp_val,    sp_chg,        sp_gold,  sp_impl   if sp_val   else "NA"),
        "news":          (news_score, news_cnt,     headlines),
        "geopolitical":  (geo_label, geo_gold),
        "banking":       (bank_label, bank_gold),
        "seasonal":      (season_name, season_level, sea_gold),
    }


def format_sentiment_block(s):
    """Formats sentiment dict into a Telegram-ready string."""

    def val_line(label, val, chg, impl, unit="", chg_unit="%"):
        if val is None:
            return f"{label}: N/A"
        chg_str = f" ({'+' if chg and chg > 0 else ''}{chg}{chg_unit})" if chg is not None else ""
        return f"{label}: {unit}{val}{chg_str} — {impl}"

    dxy  = s["dxy"]
    yld  = s["yield_10y"]
    oil  = s["crude_oil"]
    inr  = s["inr_usd"]
    nft  = s["nifty"]
    sp   = s["sp500"]
    fg   = s["fear_greed"]
    news = s["news"]
    geo  = s["geopolitical"]
    bank = s["banking"]
    sea  = s["seasonal"]

    drivers = "\n".join(f"  {d}" for d in s.get("top_drivers", [])) or "  No strong drivers"

    headlines = ""
    if news[2]:
        headlines = "\n" + "\n".join(f"  📰 {h[:75]}" for h in news[2][:3])

    return (
        f"Score: {s['score']}/100 — {s['label']}\n"
        f"{s['summary']}\n\n"
        f"Key Drivers:\n{drivers}\n\n"
        f"📊 Global Macro\n"
        f"  Fear&Greed: {fg[0]} ({fg[1]})\n"
        f"  {val_line('DXY', dxy[0], dxy[1], dxy[3])}\n"
        f"  {val_line('US 10Y', yld[0], yld[1], yld[3], unit='', chg_unit='')}\n"
        f"  {val_line('Crude', oil[0], oil[1], oil[3], unit='$')}\n\n"
        f"🇮🇳 India Factors\n"
        f"  {val_line('INR/USD', inr[0], inr[1], inr[3])}\n"
        f"  {val_line('Nifty', nft[0], nft[1], nft[3])}\n"
        f"  Season: {sea[0]} — Demand {sea[1]}\n\n"
        f"⚠️ Risk Factors\n"
        f"  Geopolitical: {geo[0]}\n"
        f"  Banking Sector: {bank[0]}\n\n"
        f"📰 News Sentiment: {news[0]}/100 ({news[1]} headlines){headlines}"
    )
