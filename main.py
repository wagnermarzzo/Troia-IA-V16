import websocket, json, time, sqlite3, threading
from datetime import datetime, timezone
import requests

# ===============================
# CONFIG
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
APP_ID = 1089
ATIVOS = [
    "frxEURUSD", "frxGBPUSD", "frxUSDJPY",
    "frxAUDUSD", "frxUSDCAD", "frxUSDCHF",
    "frxNZDUSD", "frxEURGBP"
]

GRANULARITY = 300  # 5 minutos
DB_NAME = "troia_v20.db"

TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

# ===============================
# TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=5
        )
    except:
        pass

# ===============================
# DATABASE
# ===============================
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS candles_5m (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo TEXT,
    timestamp INTEGER,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    UNIQUE(ativo, timestamp)
)
""")
conn.commit()

# ===============================
# SALVAR CANDLE
# ===============================
def salvar_candle(ativo, c):
    try:
        cur.execute("""
            INSERT OR IGNORE INTO candles_5m
            (ativo, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            ativo,
            c["epoch"],
            c["open"],
            c["high"],
            c["low"],
            c["close"],
            c.get("volume", 0)
        ))
        conn.commit()
    except:
        pass

# ===============================
# HEARTBEAT
# ===============================
def heartbeat():
    while True:
        time.sleep(1800)
        cur.execute("SELECT COUNT(*) FROM candles_5m")
        total = cur.fetchone()[0]
        tg(f"🤖 Troia V20 Online\n📊 Candles 5M coletados: {total}")

# ===============================
# WEBSOCKET
# ===============================
def on_message(ws, message):
    data = json.loads(message)

    if "candles" in data:
        ativo = data.get("echo_req", {}).get("ticks_history")
        for c in data["candles"]:
            salvar_candle(ativo, c)

def on_open(ws):
    ws.send(json.dumps({"authorize": DERIV_API_KEY}))

    for ativo in ATIVOS:
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": GRANULARITY,
            "count": 1,
            "subscribe": 1
        }))

def on_error(ws, error):
    tg(f"⚠️ WS erro: {error}")

def on_close(ws, *_):
    tg("🔴 WebSocket caiu, reconectando...")
    time.sleep(3)
    start_ws()

def start_ws():
    ws = websocket.WebSocketApp(
        f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever(ping_interval=30, ping_timeout=10)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    tg("🚀 Troia V20 – Fase 1 iniciada\nColeta 5M ativa.")
    threading.Thread(target=heartbeat, daemon=True).start()
    start_ws()
