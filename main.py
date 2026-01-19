import time, json, statistics, threading, requests, websocket
from datetime import datetime

# ==================================================
# 🔐 CREDENCIAIS (SUBSTITUA LOCALMENTE)
# ==================================================
DERIV_API_KEY = "COLE_SUA_API_AQUI"
TELEGRAM_TOKEN = "COLE_SEU_TOKEN_AQUI"
CHAT_ID = "COLE_SEU_CHAT_ID_AQUI"

# ==================================================
# ⚙️ CONFIGURAÇÕES
# ==================================================
TIMEFRAME = 60
CANDLES = 30
BASE_SCORE = 0.65
HEARTBEAT_INTERVAL = 1800  # 30 min

ATIVOS_FOREX = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxEURJPY","frxAUDUSD",
    "frxUSDCAD","frxUSDCHF","frxNZDUSD","frxEURGBP","frxEURAUD",
    "frxEURCHF","frxGBPJPY","frxAUDJPY","frxCADJPY","frxCHFJPY"
]

ATIVOS_OTC = [
    "frxEURUSD_otc","frxGBPUSD_otc","frxUSDJPY_otc",
    "frxAUDUSD_otc","frxUSDCAD_otc"
]

signal_active = False
signal_data = {}
stats = {"green": 0, "red": 0}
score_min = BASE_SCORE
blocked_asset = None
block_until = 0
asset_index = 0

# ==================================================
# 📩 TELEGRAM
# ==================================================
def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

# ==================================================
# 💓 HEARTBEAT
# ==================================================
def heartbeat():
    while True:
        send("💓 TROIA BOT ONLINE\nMonitorando mercado Deriv...")
        time.sleep(HEARTBEAT_INTERVAL)

# ==================================================
# ⏰ OTC FILTER
# ==================================================
def otc_allowed():
    utc = datetime.utcnow()
    return utc.weekday() >= 5 or utc.hour < 6 or utc.hour >= 21

# ==================================================
# 📊 ANÁLISE
# ==================================================
def analyze(c):
    closes = [x["close"] for x in c]
    bodies = [abs(x["close"] - x["open"]) for x in c]

    direction = "CALL" if closes[-1] > closes[-5] else "PUT"
    force = bodies[-1] / statistics.mean(bodies)
    score = min(force / 2, 1)

    if score >= score_min:
        return direction, score
    return None, None

# ==================================================
# 🧮 RESULTADO
# ==================================================
def check_result(c):
    e = signal_data["entry"]
    last = c[-1]["close"]
    d = signal_data["dir"]
    return "GREEN" if (last > e if d == "CALL" else last < e) else "RED"

# ==================================================
# 🌐 WEBSOCKET
# ==================================================
def on_open(ws):
    send("🟢 TROIA BOT CONECTADO À DERIV")
    ws.send(json.dumps({"authorize": DERIV_API_KEY}))
    ws.send(json.dumps({
        "candles": ATIVOS_FOREX[0],
        "interval": TIMEFRAME,
        "count": CANDLES,
        "end": "latest"
    }))

def on_message(ws, msg):
    global signal_active, signal_data, score_min
    global blocked_asset, block_until, asset_index

    data = json.loads(msg)
    if "candles" not in data:
        return

    candles = data["candles"]
    asset = data["echo_req"]["candles"]

    # ===== RESULTADO =====
    if signal_active:
        result = check_result(candles)
        stats[result.lower()] += 1

        if result == "RED":
            score_min = min(score_min + 0.05, 0.85)
            blocked_asset = asset
            block_until = time.time() + 300
        else:
            score_min = BASE_SCORE

        send(
            f"📊 RESULTADO TROIA BOT\n"
            f"Ativo: {asset}\n"
            f"Resultado: {result}\n"
            f"📈 Green: {stats['green']} | 🔴 Red: {stats['red']}"
        )

        signal_active = False
        signal_data = {}
        time.sleep(2)

    # ===== LISTA DE ATIVOS =====
    ativos = ATIVOS_FOREX + (ATIVOS_OTC if otc_allowed() else [])
    asset_index = (asset_index + 1) % len(ativos)
    next_asset = ativos[asset_index]

    if next_asset == blocked_asset and time.time() < block_until:
        return

    # ===== ANÁLISE =====
    if not signal_active:
        direction, score = analyze(candles)
        if direction:
            signal_active = True
            signal_data = {
                "asset": asset,
                "dir": direction,
                "entry": candles[-1]["close"]
            }

            send(
                f"🚨 SINAL TROIA BOT\n\n"
                f"Ativo: {asset}\n"
                f"Direção: {direction}\n"
                f"⏭ Entrada na PRÓXIMA vela\n"
                f"TF: 1M | Score: {round(score*100)}%"
            )

    ws.send(json.dumps({
        "candles": next_asset,
        "interval": TIMEFRAME,
        "count": CANDLES,
        "end": "latest"
    }))

def on_error(ws, error):
    send(f"🔴 ERRO NO BOT\n{error}")

def on_close(ws):
    send("🔴 CONEXÃO FECHADA\nReconectando em 5s...")
    time.sleep(5)
    start_ws()

def start_ws():
    ws = websocket.WebSocketApp(
        "wss://ws.derivws.com/websockets/v3?app_id=1089",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# ==================================================
# ▶️ MAIN
# ==================================================
if __name__ == "__main__":
    send("🟢 TROIA BOT ONLINE\nSistema iniciado")
    threading.Thread(target=heartbeat, daemon=True).start()
    start_ws()
