import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, date, time
import pytz
import json
import atexit
import threading

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import logic
import sheets
import ml
import sentiment as senti

# ═══════════════════════════════════════════════════════
TOKEN   = os.environ.get("TELEGRAM_TOKEN")
USER_ID = 5400949107
IST     = pytz.timezone("Asia/Kolkata")
CACHE_FILE = "price_cache.json"
LOCK_FILE  = "bot.lock"

# ─────────────────────────────────────────────────────
# Flask API — serves live data to goldmarket.onrender.com
# ─────────────────────────────────────────────────────
app_web    = Flask(__name__)
CORS(app_web)          # allow goldmarket.onrender.com to fetch from this API
latest_data = {}       # populated every time send_dashboard() runs

@app_web.route("/data")
def get_data():
    if not latest_data:
        return jsonify({"error": "No data yet — waiting for first bot run"}), 503
    return jsonify(latest_data)

@app_web.route("/health")
def health():
    return jsonify({"status": "ok", "updated": latest_data.get("updated_at", "never")})

# ── Simple PIN verification (no email needed) ────────────────────────────
# Set OTP_PIN env var in Render to your chosen 6-digit PIN e.g. 482931

@app_web.route("/send-otp", methods=["POST"])
def send_otp():
    # No email — just confirm PIN is configured and tell frontend to show PIN screen
    pin = os.environ.get("OTP_PIN", "")
    if not pin:
        return jsonify({"ok": False, "message": "OTP_PIN not set in environment"}), 500
    return jsonify({"ok": True, "message": "Enter your security PIN"})

@app_web.route("/verify-otp", methods=["POST"])
def verify_otp():
    from flask import request as freq
    body    = freq.get_json()
    entered = str(body.get("otp", "")).strip()
    pin     = os.environ.get("OTP_PIN", "")
    if not pin:
        return jsonify({"ok": False, "message": "OTP_PIN not configured on server"}), 500
    if entered != pin:
        return jsonify({"ok": False, "message": "Incorrect PIN"}), 400
    return jsonify({"ok": True, "message": "Verified"})

@app_web.route("/sheet-data")
def sheet_data():
    try:
        lt = sheets.get_lt_raw()
        st = sheets.get_st_raw()
        return jsonify({"long_term": lt, "short_term": st, "ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port, use_reloader=False)


# ═══════════════════════════════════════════════════════ LOCK
def create_lock():
    # On Render each deploy is a fresh container.
    # Skip the exit() on cloud, only enforce locally.
    if os.path.exists(LOCK_FILE):
        if not os.environ.get("RENDER"):
            print("Lock file exists locally — exiting.")
            exit()
        else:
            os.remove(LOCK_FILE)  # stale lock from previous deploy
    with open(LOCK_FILE, "w") as f:
        f.write("running")

def remove_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

atexit.register(remove_lock)

# ═══════════════════════════════════════════════════════ CACHE
def load_cache():
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

def set_cached(key, value):
    data = load_cache()
    data[key] = {"value": value, "time": datetime.now().timestamp()}
    save_cache(data)

def get_cached(key, expiry):
    data = load_cache().get(key)
    if not data:
        return None
    if datetime.now().timestamp() - data["time"] > expiry:
        return None
    return data["value"]

# ═══════════════════════════════════════════════════════ GOLD PRICE
def get_gold_price():
    try:
        url  = "https://keralagoldrates.com/today-22k-gold-rate-kerala/"
        r    = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        for m in re.findall(r"₹\d{1,2},\d{3}", soup.get_text()):
            val = float(m.replace("₹","").replace(",",""))
            if 13000 < val < 16000:
                set_cached("gold", val)
                return val, "LIVE"
    except Exception as e:
        print("KeralaGoldRates fail:", e)

    try:
        url  = "https://www.indiagoldrate.co.in/22k-gold-rate.php"
        r    = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 2:
                label = cols[0].get_text().lower()
                value = cols[1].get_text().replace(",","").strip()
                if "22" in label and value.isdigit():
                    val = float(value)
                    if 5000 < val < 8000:
                        set_cached("gold", val)
                        return val, "LIVE"
    except Exception as e:
        print("India fallback fail:", e)

    cached = get_cached("gold", 1800)
    if cached:
        return cached, "CACHE"
    return 14000, "DEFAULT"

# ═══════════════════════════════════════════════════════ GOLDBEES
def get_goldbees_price():
    try:
        url  = "https://www.google.com/finance/quote/GOLDBEES:NSE"
        r    = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        tag  = soup.find("div", {"class": "YMlKec fxKbKc"})
        if tag:
            val = float(tag.text.replace("₹","").replace(",",""))
            if 80 < val < 200:
                set_cached("bees", val)
                return val, "LIVE"
    except Exception as e:
        print("Google fail:", e)

    try:
        url  = "https://www.moneycontrol.com/india/stockpricequote/gold-etf/nipponindiaetfgoldbees/GBE"
        r    = requests.get(url, headers={"User-Agent": "Mozilla"}, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        tag  = soup.find("span", {"class": "inprice1"})
        if tag:
            val = float(tag.text.strip())
            if 80 < val < 200:
                set_cached("bees", val)
                return val, "LIVE"
    except Exception as e:
        print("MC fail:", e)

    cached = get_cached("bees", 600)
    if cached:
        return cached, "CACHE"
    return 120, "DEFAULT"

# ═══════════════════════════════════════════════════════ ALERT
def check_price_alert(name, new_price, key):
    old = load_cache().get(key)
    if not old:
        return None
    change = ((new_price - old["value"]) / old["value"]) * 100
    if abs(change) >= 1.0:
        return (
            f"🚨 {name} ALERT\n\n"
            f"Old: ₹{round(old['value'],2)}\n"
            f"New: ₹{round(new_price,2)}\n"
            f"Change: {round(change,2)}%"
        )
    return None

# ═══════════════════════════════════════════════════════ HELPERS
def is_window_open():
    return datetime.now(IST).hour in [10, 12, 14, 16, 18]

def extract_score(extra):
    try:
        return int(extra.split("Score:")[1].split("%")[0])
    except:
        return 50

def kalyan_cycle_label():
    today = datetime.now(IST).date()
    if today.day <= 23:
        if today.month == 1:
            start = date(today.year - 1, 12, 24)
        else:
            start = date(today.year, today.month - 1, 24)
        end = date(today.year, today.month, 23)
    else:
        start = date(today.year, today.month, 24)
        if today.month == 12:
            end = date(today.year + 1, 1, 23)
        else:
            end = date(today.year, today.month + 1, 23)
    return f"{start.strftime('%d %b')} – {end.strftime('%d %b')}"

def kalyan_days_left():
    today = datetime.now(IST).date()
    if today.day <= 23:
        deadline = date(today.year, today.month, 23)
    else:
        if today.month == 12:
            deadline = date(today.year + 1, 1, 23)
        else:
            deadline = date(today.year, today.month + 1, 23)
    return (deadline - today).days

def kalyan_cycle_pct():
    """% progress through the 30-day cycle for the progress bar."""
    today = datetime.now(IST).date()
    if today.day <= 23:
        days_elapsed = 30 - (23 - today.day) - 1
    else:
        days_elapsed = today.day - 24
    return min(100, max(0, int((days_elapsed / 30) * 100)))

# ═══════════════════════════════════════════════════════ DASHBOARD
async def send_dashboard(context: ContextTypes.DEFAULT_TYPE):
    global latest_data

    gold_price, gold_src = get_gold_price()
    bees_price, bees_src = get_goldbees_price()

    alert1 = check_price_alert("GOLD",     gold_price, "gold")
    alert2 = check_price_alert("GOLDBEES", bees_price, "bees")
    if alert1: await context.bot.send_message(chat_id=USER_ID, text=alert1)
    if alert2: await context.bot.send_message(chat_id=USER_ID, text=alert2)

    gold_daily = sheets.get_gold_daily()
    bees_daily = sheets.get_bees_daily()

    gold_trend, gold_reason = logic.get_trend(gold_price, gold_daily)
    bees_trend, bees_reason = logic.get_trend(bees_price, bees_daily)

    st_inv, st_cash, st_units, st_val, st_profit, st_pct = sheets.get_st_metrics(bees_price)
    lt_inv, lt_gold, lt_val, lt_profit, lt_pct           = sheets.get_lt_metrics(gold_price)

    avg_price = sheets.get_avg_buy_price()
    bought    = sheets.already_bought()
    cycle_low = sheets.get_kalyan_cycle_low()

    st_data = sheets.get_st_history()
    ml_low, ml_high, ml_signal, win_rate, extra = ml.short_term_ml(bees_daily, st_data)
    ml_score = extract_score(extra)

    lt_trend_ml, lt_valn, lt_zone, lt_conf = ml.long_term_ml(gold_daily, avg_price, gold_price)

    sent = senti.get_combined_sentiment()

    st_action, st_amt, st_reason, sl, tgt = logic.short_term_ai(
        st_cash, st_pct, bees_trend, ml_score, win_rate,
        bees_price, st_units, sent
    )

    lt_action, lt_amt, lt_reason = logic.long_term_ai(
        bought, gold_price, avg_price, gold_trend, gold_daily,
        cycle_low, ml_score, sent
    )

    sheets.log_data(gold_price, gold_trend, ml_score, bees_price, bees_trend, win_rate)

    total_val    = st_val + lt_val
    total_invest = st_inv + lt_inv
    total_profit = total_val - total_invest

    # ── Update latest_data for the Flask /data endpoint ──
    latest_data = {
        # Prices
        "gold_price":  gold_price,
        "gold_src":    gold_src,
        "gold_trend":  gold_trend,
        "gold_reason": gold_reason,
        "bees_price":  bees_price,
        "bees_src":    bees_src,
        "bees_trend":  bees_trend,
        "bees_reason": bees_reason,

        # Long term
        "lt_inv":       lt_inv,
        "lt_gold":      round(lt_gold, 3),
        "lt_val":       lt_val,
        "lt_profit":    lt_profit,
        "lt_pct":       round(lt_pct, 2),
        "lt_ml_trend":  lt_trend_ml,
        "lt_valn":      lt_valn,
        "lt_zone":      lt_zone,
        "lt_conf":      lt_conf,
        "cycle_label":  kalyan_cycle_label(),
        "cycle_low":    cycle_low,
        "days_left":    kalyan_days_left(),
        "cycle_pct":    kalyan_cycle_pct(),

        # Short term
        "st_inv":    st_inv,
        "st_cash":   st_cash,
        "st_units":  round(st_units, 2),
        "st_val":    st_val,
        "st_profit": st_profit,
        "st_pct":    round(st_pct, 2),

        # Totals
        "total_invest":  total_invest,
        "total_val":     total_val,
        "total_profit":  total_profit,

        # AI decisions
        "st_action": st_action,
        "st_amt":    st_amt,
        "st_reason": st_reason,
        "sl":        sl,
        "tgt":       tgt,
        "lt_action": lt_action,
        "lt_reason": lt_reason,

        # ML
        "ml_score":   ml_score,
        "ml_signal":  ml_signal,
        "ml_winrate": win_rate,
        "ml_low":     ml_low,
        "ml_high":    ml_high,
        "ml_detail":  extra,

        # Sentiment (full dict)
        "sent_score":   sent.get("score", 50),
        "sent_label":   sent.get("label", "NEUTRAL"),
        "sent_summary": sent.get("summary", ""),
        "drivers":      sent.get("top_drivers", []),
        "fg_score":     sent.get("fear_greed", (None,"NA",50))[0],
        "fg_label":     sent.get("fear_greed", (None,"NA",50))[1],
        "fg_impl":      sent.get("fear_greed", (None,"NA",50))[2],
        "dxy_val":      sent.get("dxy", (None,None,50,"NA"))[0],
        "dxy_chg":      sent.get("dxy", (None,None,50,"NA"))[1],
        "dxy_impl":     sent.get("dxy", (None,None,50,"NA"))[3],
        "yld_val":      sent.get("yield_10y", (None,None,50,"NA"))[0],
        "yld_chg":      sent.get("yield_10y", (None,None,50,"NA"))[1],
        "yld_impl":     sent.get("yield_10y", (None,None,50,"NA"))[3],
        "oil_val":      sent.get("crude_oil", (None,None,50,"NA"))[0],
        "oil_chg":      sent.get("crude_oil", (None,None,50,"NA"))[1],
        "oil_impl":     sent.get("crude_oil", (None,None,50,"NA"))[3],
        "sp_val":       sent.get("sp500", (None,None,50,"NA"))[0],
        "sp_chg":       sent.get("sp500", (None,None,50,"NA"))[1],
        "sp_impl":      sent.get("sp500", (None,None,50,"NA"))[3],
        "inr_val":      sent.get("inr_usd", (None,None,50,"NA"))[0],
        "inr_chg":      sent.get("inr_usd", (None,None,50,"NA"))[1],
        "inr_impl":     sent.get("inr_usd", (None,None,50,"NA"))[3],
        "nifty_val":    sent.get("nifty", (None,None,50,"NA"))[0],
        "nifty_chg":    sent.get("nifty", (None,None,50,"NA"))[1],
        "nifty_impl":   sent.get("nifty", (None,None,50,"NA"))[3],
        "season_name":  sent.get("seasonal", ("Off-season","LOW",40))[0],
        "season_level": sent.get("seasonal", ("Off-season","LOW",40))[1],
        "geo_label":    sent.get("geopolitical", ("UNKNOWN",50))[0],
        "bank_label":   sent.get("banking", ("NEUTRAL",50))[0],
        "news_score":   sent.get("news", (50,0,[]))[0],
        "news_cnt":     sent.get("news", (50,0,[]))[1],
        "headlines":    sent.get("news", (50,0,[]))[2],

        "updated_at": datetime.now(IST).strftime("%d %b %Y %H:%M IST")
    }

    # ── Telegram message ─────────────────────────────────
    sl_line  = f"\n   🛑 SL:     ₹{sl}"  if sl  else ""
    tgt_line = f"\n   🎯 Target: ₹{tgt}" if tgt else ""
    cycle_label = kalyan_cycle_label()
    low_line    = f"Cycle Low:  ₹{int(cycle_low)}" if cycle_low else "Cycle Low:  tracking..."
    sent_block  = senti.format_sentiment_block(sent)

    msg = f"""
💎 GOLD AI PORTFOLIO ENGINE

💰 Gold (22K): ₹{gold_price} ({gold_src})
📈 GoldBees:   ₹{bees_price} ({bees_src})

📊 Gold Trend:     {gold_trend}
📊 GoldBees Trend: {bees_trend}
   {bees_reason}

━━━━━━━━━━━━━━━
🟢 KALYAN GOLD SCHEME
   Cycle: {cycle_label}

Invested: ₹{int(lt_inv)}
Gold:     {round(lt_gold,3)}g
Value:    ₹{int(lt_val)}
P/L:      ₹{int(lt_profit)} ({round(lt_pct,2)}%)
{low_line}

━━━━━━━━━━━━━━━
🔴 GOLDBEES (Interday)

Cash:  ₹{int(st_cash)}
Units: {round(st_units,2)}
Value: ₹{int(st_val)}
P/L:   ₹{int(st_profit)} ({round(st_pct,2)}%)

━━━━━━━━━━━━━━━
💎 TOTAL  ₹{int(total_val)} | P/L: ₹{int(total_profit)}

━━━━━━━━━━━━━━━
🤖 AI DECISION

📌 Short-Term{sl_line}{tgt_line}
   {st_action} ₹{st_amt}
   {st_reason}

📌 Long-Term (Kalyan)
   {lt_action}
   {lt_reason}

━━━━━━━━━━━━━━━
🌐 MARKET SENTIMENT
{sent_block}

━━━━━━━━━━━━━━━
🤖 ML  Range:₹{ml_low}–₹{ml_high} | {ml_signal} | WR:{win_rate}%
{extra}
"""

    keyboard = []
    if lt_action == "BUY":
        keyboard.append([InlineKeyboardButton("🟢 KALYAN BUY ₹15000", callback_data="lt_buy")])
    if st_action == "BUY":
        keyboard.append([InlineKeyboardButton(f"🟢 BUY ₹{st_amt}", callback_data=f"buy_{st_amt}")])
    if st_action == "SELL":
        keyboard.append([InlineKeyboardButton(f"🔴 SELL ₹{st_amt}", callback_data=f"sell_{st_amt}")])

    await context.bot.send_message(
        chat_id=USER_ID, text=msg,
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )

# ═══════════════════════════════════════════════════════ BUTTON
async def button(update, context):
    q = update.callback_query
    await q.answer()
    if not is_window_open():
        await q.message.reply_text("⏰ Window closed — bot runs at 10, 12, 14, 16, 18 IST")
        return
    gold_price, _ = get_gold_price()
    bees_price, _ = get_goldbees_price()
    try:
        if q.data == "lt_buy":
            sheets.add_long(gold_price)
            await q.message.reply_text(f"✅ Kalyan BUY ₹15000 @ ₹{gold_price}/g")
        elif q.data.startswith("buy_"):
            amt = int(q.data.split("_")[1])
            sheets.add_short("BUY", amt, bees_price)
            await q.message.reply_text(f"✅ BUY ₹{amt} @ ₹{bees_price}")
        elif q.data.startswith("sell_"):
            amt = int(q.data.split("_")[1])
            sheets.add_short("SELL", amt, bees_price)
            await q.message.reply_text(f"✅ SELL ₹{amt} @ ₹{bees_price}")
    except Exception as e:
        await q.message.reply_text(f"❌ Error: {str(e)}")

# ═══════════════════════════════════════════════════════ COMMANDS
async def start(update, context):
    await send_dashboard(context)

async def force(update, context):
    await send_dashboard(context)

async def dashboard_link(update, context):
    await update.message.reply_text(
        "📊 Open your live dashboard:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Open Dashboard", url="https://goldmarket.onrender.com")
        ]])
    )

# ═══════════════════════════════════════════════════════ MAIN
def main():
    create_lock()

    # ── FIX 1: Start Flask FIRST so Render sees an open port ──
    # Render health-checks for an open port immediately on start.
    # If Flask isn't up first, Render kills the service.
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Wait until Flask is actually accepting connections
    import socket, time as _time
    port = int(os.environ.get("PORT", 8080))
    for _ in range(20):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=1)
            s.close()
            print(f"Flask API live on port {port} ✅")
            break
        except OSError:
            _time.sleep(0.5)

    # ── FIX 2: Delete any existing webhook AND drop pending updates
    # before starting polling, to avoid the Conflict error when
    # a previous instance is still registered with Telegram.
    async def post_init(app):
        await app.bot.delete_webhook(drop_pending_updates=True)
        print("Webhook cleared ✅")

    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("force",     force))
    app.add_handler(CommandHandler("dashboard", dashboard_link))
    app.add_handler(CallbackQueryHandler(button))

    times = [
        time(10, 0, tzinfo=IST), time(12, 0, tzinfo=IST),
        time(14, 0, tzinfo=IST), time(16, 0, tzinfo=IST),
        time(18, 0, tzinfo=IST),
    ]
    if app.job_queue:
        for t in times:
            app.job_queue.run_daily(send_dashboard, time=t)

    print("Telegram bot running 🚀")
    # drop_pending_updates=True also clears any queued messages from old instance
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
