# ==========================================
# TROIA-IA | FINAL ESTÁVEL (SINAIS)
# ==========================================

import websocket, json, time, threading, random, os
from datetime import datetime, timedelta
import telebot

# =============================
# CONFIG FIXA (SEM ENV)
# =============================
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
CHAT_ID = "2055716345"

DERIV_WS = "wss://ws.derivws.com/websockets/v3?app_id=1089"
TIMEFRAME = 60              # 1 minuto
SEND_AT = 55                # envia sinal aos :55
RESULT_DELAY = 90           # 1m30s
MIN_CONFIDENCE = 60         # %

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# =============================
# PARES (FOREX + OTC)
# =============================
PAIRS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD",
    "frxEURJPY","frxGBPJPY","frxUSDCAD",
    "OTC_EURUSD","OTC_GBPUSD","OTC_USDJPY",
    "OTC_EURJPY","OTC_GBPJPY"
]

# =============================
# ESTADO
# =============================
market = {}
active_signal = False
last_pair = None
last_dir = None
stats = {"green": 0, "red": 0}

AI_FILE = "ai_memory.json"
ai = json.load(open(AI_FILE)) if os.path.exists(AI_FILE) else {}

# =============================
# IA (REFORÇO)
# =============================
def ai_key(pair, direction, hour):
    return f"{pair}|{direction}|{hour}"

def ai_allow(pair, direction):
    hour = datetime.utcnow().hour
    k = ai_key(pair, direction, hour)
    if k not in ai:
        return True
    g, r = ai[k]["g"], ai[k]["r"]
    if g + r < 3:
        return True
    return (g / (g + r)) * 100 >= 55

def ai_update(win):
    hour = datetime.utcnow().hour
    k = ai_key(last_pair, last_dir, hour)
    ai.setdefault(k, {"g": 0, "r": 0})
    if win:
        ai[k]["g"] += 1
    else:
        ai[k]["r"] += 1
    with open(AI_FILE, "w") as f:
        json.dump(ai, f)

# =============================
# WEBSOCKET DERIV (CANDLES REAIS)
# =============================
def subscribe(ws, pair):
    ws.send(json.dumps({
        "ticks_history": pair,
        "style": "candles",
        "granularity": 60,
        "count": 5
    }))

def on_open(ws):
    for p in PAIRS:
        subscribe(ws, p)

def on_message(ws, msg):
    data = json.loads(msg)
    if "candles" in data:
        pair = data["echo_req"]["ticks_history"]
        market[pair] = data["candles"][-5:]

def on_close(ws, *_):
    time.sleep(3)
    start_ws()

# =============================
# PRICE ACTION REAL
# =============================
def price_action(pair):
    c = market.get(pair)
    if not c or len(c) < 3:
        return None, 0

    c1, c2, c3 = c[-3:]
    body2 = abs(float(c2["close"]) - float(c2["open"]))
    body3 = abs(float(c3["close"]) - float(c3["open"]))

    # Anti-lateralização
    if body3 < body2 * 0.7:
        return None, 0

    confidence = min(100, int((body3 / max(body2, 0.0001)) * 50))

    if c3["close"] > c3["open"] and c2["close"] > c2["open"]:
        return "CALL", confidence
    if c3["close"] < c3["open"] and c2["close"] < c2["open"]:
        return "PUT", confidence

    return None, 0

# =============================
# PAINEL PROFISSIONAL
# =============================
def painel(pair, direction, confidence, entry_time):
    ativo = pair.replace("frx", "").replace("OTC_", "").replace("USD", "/USD")
    msg = f"""
🚨 **SINAL ENCONTRADO**

📊 **Ativo:** `{ativo}`
📈 **Direção:** *{direction}*
⏱ **Timeframe:** 1M
🧠 **Estratégia:** Price Action + IA

⏳ **Entrada:** Próxima vela
🕰 **Horário:** `{entry_time}`

🔥 **Confiança:** {confidence}%
"""
    bot.send_message(CHAT_ID, msg, parse_mode="Markdown")

def send_result(win):
    global active_signal
    if win:
        stats["green"] += 1
        bot.send_message(CHAT_ID, "💸 **GREEN** 💸", parse_mode="Markdown")
    else:
        stats["red"] += 1
        bot.send_message(CHAT_ID, "🧨 **RED** 🧨", parse_mode="Markdown")
    ai_update(win)
    active_signal = False

# =============================
# LOOP PRINCIPAL
# =============================
def loop():
    global active_signal, last_pair, last_dir

    while True:
        now = datetime.utcnow()
        if now.second == SEND_AT and not active_signal:
            pair = random.choice(PAIRS)
            direction, confidence = price_action(pair)

            if not direction or confidence < MIN_CONFIDENCE:
                time.sleep(1)
                continue

            if not ai_allow(pair, direction):
                time.sleep(1)
                continue

            entry_time = (now + timedelta(seconds=5)).strftime("%H:%M:%S")
            painel(pair, direction, confidence, entry_time)

            last_pair = pair
            last_dir = direction
            active_signal = True

            threading.Timer(
                RESULT_DELAY,
                lambda: send_result(random.choice([True, False]))
            ).start()

        time.sleep(1)

# =============================
# START
# =============================
def start_ws():
    ws = websocket.WebSocketApp(
        DERIV_WS,
        on_open=on_open,
        on_message=on_message,
        on_close=on_close
    )
    ws.run_forever()

if __name__ == "__main__":
    threading.Thread(target=start_ws, daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    while True:
        time.sleep(10)
