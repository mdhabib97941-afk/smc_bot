import os
import time
import math
import threading
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template_string

# Flask App for Render Web Service Health Checks
app = Flask(__name__)

# Configuration from Environment Variables (with fallback defaults)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8995620553:AAHAyY1lOSruZUOx-sWjtQPXBZc-55j0Cjo")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7736288854")
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
PORT = int(os.getenv("PORT", 10000))

# Bangladesh Timezone (BST = UTC+6)
BD_TZ = timezone(timedelta(hours=6))

# In-memory bot state
bot_state = {
    "status": "RUNNING",
    "started_at": datetime.now(BD_TZ).strftime("%d %b %Y | %I:%M %p"),
    "last_check_time": None,
    "last_alert_time": None,
    "current_position": "LONG",
    "last_entry_price": 82833.4,
    "last_sl_price": 82161.4,
    "alerts_sent_count": 0,
    "last_error": None
}

def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        r = requests.post(url, json=payload, timeout=8)
        return r.status_code == 200
    except Exception as e:
        bot_state["last_error"] = str(e)
        return False

def fetch_klines(symbol=SYMBOL, interval="1h", limit=50):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    for _ in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                return r.json()
        except:
            time.sleep(1)
    return []

def evaluate_1h_order_block(klines, target_offset=2):
    """
    Evaluates closed 1H candle for Bullish or Bearish Order Block confirmation.
    target_offset=2 evaluates the newly-closed candle (since index -1 is running).
    """
    if len(klines) < 25: return None
    c_list = []
    for k in klines:
        v = float(k[5])
        tbv = float(k[9])
        c_list.append({
            'time': int(k[0]),
            'close_time': int(k[6]),
            'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4]),
            'volume': v, 'tbv': tbv, 'delta': tbv - (v - tbv)
        })
    n = len(c_list)
    
    # ATR calculation
    tr = [c_list[0]['high'] - c_list[0]['low']]
    for i in range(1, n):
        tr.append(max(c_list[i]['high'] - c_list[i]['low'], abs(c_list[i]['high'] - c_list[i-1]['close']), abs(c_list[i]['low'] - c_list[i-1]['close'])))
    atr = [sum(tr[max(0, i-13):i+1])/len(tr[max(0, i-13):i+1]) for i in range(n)]
    volSMA = [sum(c_list[i-k]['volume'] for k in range(min(20, i+1)))/min(20, i+1) for i in range(n)]

    # Swings
    swH, swL = [], []
    for i in range(3, n - 4):
        cH, cL = c_list[i]['high'], c_list[i]['low']
        isH, isL = True, True
        for j in range(1, 4):
            if c_list[i-j]['high'] >= cH or c_list[i+j]['high'] > cH: isH = False
            if c_list[i-j]['low'] <= cL or c_list[i+j]['low'] < cL: isL = False
        if isH: swH.append({'index': i, 'price': cH})
        if isL: swL.append({'index': i, 'price': cL})
    swH, swL = swH[-30:], swL[-30:]

    target_idx = n - target_offset
    if target_idx < 5: return None
    c = c_list[target_idx]
    prevC = c_list[target_idx - 1]
    
    avgV = volSMA[target_idx]
    isVSpike = c['volume'] >= avgV * 1.2

    # Momentum Z-Score (synced with SMC MATRIX PRO smcEngine.ts)
    changes = [c_list[i]['close'] - c_list[i-1]['close'] if i > 0 else 0 for i in range(n)]
    mom_lb = min(20, target_idx)
    sub_changes = [changes[target_idx - k] for k in range(mom_lb)]
    avg_change = sum(sub_changes) / mom_lb if mom_lb > 0 else 0
    std_change = math.sqrt(sum((x - avg_change) ** 2 for x in sub_changes) / mom_lb) if mom_lb > 0 else 1e-5
    std_change = std_change or 1e-5
    momentumZ = (changes[target_idx] - avg_change) / std_change

    bSize = abs(c['close'] - c['open'])
    isDisp = bSize >= atr[target_idx] * 0.75

    isBullSweep = any(sw['index'] < target_idx - 1 and prevC['low'] < sw['price'] and c['close'] > sw['price'] and c['close'] > c['open'] for sw in swL)
    isBearSweep = any(sw['index'] < target_idx - 1 and prevC['high'] > sw['price'] and c['close'] < sw['price'] and c['close'] < c['open'] for sw in swH)

    isBullBOS = any(c['close'] > sw['price'] and prevC['close'] <= sw['price'] for sw in swH if sw['index'] < target_idx - 2)
    isBearBOS = any(c['close'] < sw['price'] and prevC['close'] >= sw['price'] for sw in swL if sw['index'] < target_idx - 2)

    isBullMomDisp = (momentumZ > 0.75 or (c['close'] > prevC['high'] and isVSpike)) and isDisp and c['close'] > c['open']
    isBearMomDisp = (momentumZ < -0.75 or (c['close'] < prevC['low'] and isVSpike)) and isDisp and c['close'] < c['open']

    isBullOB = isBullMomDisp or ((isBullSweep or isBullBOS or isDisp) and (isVSpike or c['volume'] >= avgV) and c['close'] > c['open'])
    isBearOB = isBearMomDisp or ((isBearSweep or isBearBOS or isDisp) and (isVSpike or c['volume'] >= avgV) and c['close'] < c['open'])

    buffer_atr = atr[target_idx] * 0.2

    if isBullOB:
        obIdx = target_idx - 1
        for k in range(1, 6):
            if target_idx - k >= 0 and c_list[target_idx-k]['close'] < c_list[target_idx-k]['open']:
                obIdx = target_idx - k; break
        top = max(c_list[obIdx]['open'], c_list[obIdx]['high'])
        bot = c_list[obIdx]['low']
        sl = round(bot - buffer_atr, 1)
        entry = round(c['close'], 1)
        sl_dist = max(50.0, entry - sl)

        # Exness Lot sizing (1.0 Lot = 1 BTC on Exness BTCUSD)
        exness_lot_10 = max(0.01, round(10.0 / sl_dist, 2))
        exness_loss_10 = round(exness_lot_10 * sl_dist, 2)
        exness_lot_6 = max(0.01, round(6.0 / sl_dist, 2))
        exness_loss_6 = round(exness_lot_6 * sl_dist, 2)

        return {
            'dir': 'LONG',
            'type': '🟢 BULLISH ORDER BLOCK',
            'ob_time_ms': c_list[obIdx]['time'],
            'time_ms': c['time'],
            'close_time_ms': c['close_time'],
            'is_live_forming': (target_offset == 1),
            'entry': entry,
            'sl': sl,
            'sl_dist': sl_dist,
            'ob_range': f"${bot:,.1f} - ${top:,.1f}",
            'delta': round(c['delta'], 1),
            'volume': round(c['volume'], 1),
            'exness_lot_10': exness_lot_10,
            'exness_loss_10': exness_loss_10,
            'exness_lot_6': exness_lot_6,
            'exness_loss_6': exness_loss_6
        }

    elif isBearOB:
        obIdx = target_idx - 1
        for k in range(1, 6):
            if target_idx - k >= 0 and c_list[target_idx-k]['close'] > c_list[target_idx-k]['open']:
                obIdx = target_idx - k; break
        top = c_list[obIdx]['high']
        bot = min(c_list[obIdx]['open'], c_list[obIdx]['low'])
        sl = round(top + buffer_atr, 1)
        entry = round(c['close'], 1)
        sl_dist = max(50.0, sl - entry)
        
        exness_lot_10 = max(0.01, round(10.0 / sl_dist, 2))
        exness_loss_10 = round(exness_lot_10 * sl_dist, 2)
        exness_lot_6 = max(0.01, round(6.0 / sl_dist, 2))
        exness_loss_6 = round(exness_lot_6 * sl_dist, 2)

        return {
            'dir': 'SHORT',
            'type': '🔻 BEARISH ORDER BLOCK',
            'ob_time_ms': c_list[obIdx]['time'],
            'time_ms': c['time'],
            'close_time_ms': c['close_time'],
            'is_live_forming': (target_offset == 1),
            'entry': entry,
            'sl': sl,
            'sl_dist': sl_dist,
            'ob_range': f"${bot:,.1f} - ${top:,.1f}",
            'delta': round(c['delta'], 1),
            'volume': round(c['volume'], 1),
            'exness_lot_10': exness_lot_10,
            'exness_loss_10': exness_loss_10,
            'exness_lot_6': exness_lot_6,
            'exness_loss_6': exness_loss_6
        }

    return None

def format_telegram_alert(ob, is_flip=False, prev_dir=None):
    now_bd = datetime.now(BD_TZ)
    time_str = now_bd.strftime("%d %b %Y | %I:%M:%S %p")
    
    flip_header = ""
    if is_flip and prev_dir:
        flip_header = f"🚨 <b>[INSTANT FLIP ALERT: CLOSE {prev_dir} & ENTER {ob['dir']} NOW!]</b>\n"
        flip_header += f"<i>চার্টে নতুন {ob['dir']} OB ভেসে উঠেছে! আগের {prev_dir} ট্রেড ক্লোজ করে সাথে সাথে {ob['dir']} নিন!</i>\n\n"
    else:
        flip_header = f"🚨 <b>[INSTANT 1-HOUR ORDER BLOCK DETECTED]</b>\n\n"

    emoji = "🟢" if ob['dir'] == 'LONG' else "🔻"
    action = f"{emoji} <b>{ob['dir']} ENTRY TRIGGER (LIVE CHART SYNC)</b>"

    msg = f"""{flip_header}{action}
⏱️ <b>সময়:</b> {time_str} (বাংলাদেশ সময়)
━━━━━━━━━━━━━━━━━━━━
🎯 <b>এন্ট্রি প্রাইস:</b> <code>${ob['entry']:,.1f}</code>
🛡️ <b>স্টপ লস (SL):</b> <code>${ob['sl']:,.1f}</code> (দূরত্ব: ${ob['sl_dist']:,.1f})
📦 <b>অর্ডার ব্লক রেঞ্জ:</b> <code>{ob['ob_range']}</code>
📊 <b>ক্যান্ডেল ডেল্টা:</b> <code>{ob['delta']:+,.1f} BTC</code> (ভলিউম: {ob['volume']:,.0f})
━━━━━━━━━━━━━━━━━━━━
🏛️ <b>Exness (MT4/MT5 / App) লট সাইজ ($২০০ একাউন্ট):</b>
• <b>৩% রিস্ক (স্ট্যান্ডার্ড):</b> লট = <code>{ob['exness_lot_6']} Lot</code> (এসএল খেলে যাবে -${ob['exness_loss_6']})
• <b>৫% রিস্ক (গ্রোথ):</b> লট = <code>{ob['exness_lot_10']} Lot</code> (এসএল খেলে যাবে -${ob['exness_loss_10']})
<i>(Exness-এ BTCUSD পেয়ারে ১.০ লট = ১ BTC, মিনিমাম ০.০১ লট)</i>

🎯 <b>এক্সিট / টিপি রুলস:</b>
পরবর্তী বিপরীত ১-ঘণ্টা অর্ডার ব্লক তৈরি না হওয়া পর্যন্ত ট্রেড রান করতে দিন। বিপরীত সিগন্যাল চার্টে আসা মাত্রই সাথে সাথে টেলিগ্রামে ইনস্ট্যান্ট ফ্লিপ অ্যালার্ট চলে আসবে!
"""
    return msg

def telegram_monitor_thread():
    print("Telegram Background Scanner Thread Started (5s Instant Chart Sync)...")
    seen_ob_keys = set()
    current_active_dir = "SHORT"

    # Calibrate initial OBs so startup doesn't re-send old OBs
    init_klines = fetch_klines(limit=40)
    if init_klines and len(init_klines) >= 25:
        for off in [1, 2, 3, 4]:
            ob = evaluate_1h_order_block(init_klines, target_offset=off)
            if ob:
                seen_ob_keys.add(f"{ob['ob_time_ms']}_{ob['dir']}")
                if current_active_dir is None:
                    current_active_dir = ob['dir']

    while True:
        try:
            bot_state["last_check_time"] = datetime.now(BD_TZ).strftime("%d %b %Y | %I:%M:%S %p")
            klines = fetch_klines(limit=40)
            if klines and len(klines) >= 25:
                for offset in [1, 2]:
                    ob = evaluate_1h_order_block(klines, target_offset=offset)
                    if ob:
                        ob_key = f"{ob['ob_time_ms']}_{ob['dir']}"
                        if ob_key not in seen_ob_keys:
                            seen_ob_keys.add(ob_key)
                            is_flip = (current_active_dir is not None and current_active_dir != ob['dir'])
                            msg = format_telegram_alert(ob, is_flip=is_flip, prev_dir=current_active_dir)
                            if send_telegram_message(msg):
                                current_active_dir = ob['dir']
                                bot_state["current_position"] = ob['dir']
                                bot_state["last_entry_price"] = ob['entry']
                                bot_state["last_sl_price"] = ob['sl']
                                bot_state["last_alert_time"] = datetime.now(BD_TZ).strftime("%d %b %Y | %I:%M:%S %p")
                                bot_state["alerts_sent_count"] += 1
                                print(f"INSTANT Alert sent for {ob['dir']} at ${ob['entry']} (OB Key: {ob_key})")

        except Exception as e:
            bot_state["last_error"] = str(e)
            print(f"Monitor error: {e}")

        time.sleep(5)

# Flask Web Routes for Render Health Checks & Ping
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>SMC 1H Order Block Bot | Live on Cloud</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; background: #0d1117; color: #c9d1d9; text-align: center; padding: 40px 20px; }
        .card { max-width: 600px; margin: 0 auto; background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 25px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
        h1 { color: #58a6ff; font-size: 24px; margin-bottom: 5px; }
        .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 13px; background: #238636; color: white; margin-bottom: 20px; }
        .metric { display: flex; justify-content: space-between; border-bottom: 1px solid #21262d; padding: 10px 0; font-size: 14px; }
        .metric:last-child { border-bottom: none; }
        .val { font-weight: bold; color: #f0f6fc; }
        .pos { color: #3fb950; font-size: 16px; font-weight: bold; }
        .btn { display: inline-block; margin-top: 20px; padding: 10px 20px; background: #1f6feb; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; }
        .btn:hover { background: #388bfd; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🚀 SMC 1H Order Block Bot</h1>
        <div class="badge">● 24/7 CLOUD ACTIVE</div>
        
        <div class="metric"><span>স্ট্যাটাস:</span><span class="val">{{ state.status }}</span></div>
        <div class="metric"><span>বর্তমান একটিভ পজিশন:</span><span class="val pos">{{ state.current_position }}</span></div>
        <div class="metric"><span>সর্বশেষ এন্ট্রি প্রাইস:</span><span class="val">${{ state.last_entry_price }}</span></div>
        <div class="metric"><span>স্টপ লস (SL):</span><span class="val">${{ state.last_sl_price }}</span></div>
        <div class="metric"><span>মোট পাঠানো অ্যালার্ট:</span><span class="val">{{ state.alerts_sent_count }} টি</span></div>
        <div class="metric"><span>সর্বশেষ স্ক্যান সময়:</span><span class="val">{{ state.last_check_time }}</span></div>
        <div class="metric"><span>সার্ভার স্টার্ট সময়:</span><span class="val">{{ state.started_at }}</span></div>
        
        <a class="btn" href="/test-alert">🔔 Send Test Telegram Alert</a>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_PAGE, state=bot_state)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "state": bot_state}), 200

@app.route("/test-alert")
def trigger_test_alert():
    klines = fetch_klines(limit=35)
    found_ob = None
    for offset in [2, 3, 4, 5]:
        ob = evaluate_1h_order_block(klines, target_offset=offset)
        if ob:
            found_ob = ob
            break
    if found_ob:
        msg = format_telegram_alert(found_ob, is_flip=False)
        success = send_telegram_message(msg)
        return jsonify({"success": success, "message": "Telegram test alert sent!"})
    return jsonify({"success": False, "message": "No recent OB found to test."})

# Start the background monitor thread on application startup
threading.Thread(target=telegram_monitor_thread, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
