import websocket, json, time, requests, threading
from datetime import datetime, timezone
from collections import defaultdict
from flask import Flask

# ===============================
# CONFIG FIXA – TROIA v21 FASE 1
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD",
    "frxUSDCAD","frxUSDCHF","frxNZDUSD","frxEURGBP"
]

TIMEFRAME = 300  # 5 minutos
CANDLES_ANALISE = 100

# ===============================
# TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": msg,
                "parse_mode": "HTML"
            },
            timeout=5
        )
    except:
        pass

# ===============================
# PEGAR CANDLES DERIV
# ===============================
def pegar_candles(ativo, count=CANDLES_ANALISE):
    ws = websocket.create_connection(
        "wss://ws.derivws.com/websockets/v3?app_id=1089", timeout=10
    )
    ws.send(json.dumps({"authorize": DERIV_API_KEY}))
    ws.send(json.dumps({
        "ticks_history": ativo,
        "style": "candles",
        "granularity": TIMEFRAME,
        "count": count,
        "end": "latest"
    }))
    data = json.loads(ws.recv())
    ws.close()
    return data.get("candles", [])

# ===============================
# ANÁLISES
# ===============================
def detectar_tendencia(candles):
    h = [c["high"] for c in candles[-10:]]
    l = [c["low"] for c in candles[-10:]]
    if h[-1] > h[-2] and l[-1] > l[-2]:
        return "ALTA"
    if h[-1] < h[-2] and l[-1] < l[-2]:
        return "BAIXA"
    return "LATERAL"

def detectar_zonas(candles):
    zonas = defaultdict(int)
    for c in candles:
        nivel = round((c["high"] + c["low"]) / 2, 5)
        zonas[nivel] += 1
    return {k:v for k,v in zonas.items() if v >= 3}

def padrao_candle(c):
    corpo = abs(c["close"] - c["open"])
    total = c["high"] - c["low"]
    if total == 0:
        return None
    if corpo / total >= 0.6:
        return "CANDLE FORTE"
    return None

# ===============================
# ANALISAR ATIVO
# ===============================
def analisar_ativo(ativo):
    candles = pegar_candles(ativo)
    if len(candles) < 30:
        return

    tendencia = detectar_tendencia(candles)
    zonas = detectar_zonas(candles)
    padrao = padrao_candle(candles[-1])

    if tendencia == "LATERAL" or not zonas or not padrao:
        return

    direcao = "CALL" if tendencia == "ALTA" else "PUT"
    horario = datetime.now(timezone.utc).strftime("%H:%M UTC")

    tg(
        f"🚀 <b>TROIA v21 — FASE 1</b>\n"
        f"📊 <b>Ativo:</b> {ativo}\n"
        f"📈 <b>Tendência:</b> {tendencia}\n"
        f"🧱 <b>Zonas fortes:</b> {len(zonas)}\n"
        f"🔥 <b>Padrão:</b> {padrao}\n"
        f"🎯 <b>Direção:</b> {direcao}\n"
        f"⏱ <b>Entrada:</b> Agora / Próx. vela 5M\n"
        f"🕒 <b>Horário:</b> {horario}"
    )

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop():
    tg("🧠 TROIA v21 — FASE 1 (5M PRO) INICIADO")
    while True:
        for ativo in ATIVOS:
            try:
                analisar_ativo(ativo)
                time.sleep(5)
            except:
                time.sleep(3)

# ===============================
# HTTP KEEP ALIVE (RAILWAY)
# ===============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Troia v21 Fase 1 Online"

def start():
    threading.Thread(target=loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    start()
