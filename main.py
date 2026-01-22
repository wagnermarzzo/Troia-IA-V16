import websocket
import json
import time
import requests
import threading
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"

TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

TIMEFRAME = 300
CONF_MIN = 46
PROB_MIN = 53

MAX_SINAIS_HORA = 8
COOLDOWN_ATIVO = 240

BR_TZ = timezone(timedelta(hours=-3))

PORT = int(os.environ.get("PORT", 8080))

# ===============================
# ATIVOS
# ===============================
ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD",
    "frxUSDCHF","frxEURJPY","frxGBPJPY","frxEURGBP","frxAUDJPY"
]

# ===============================
# CONTROLE
# ===============================
ultimo_sinal = defaultdict(int)
sinais_hora = deque()
bot_iniciado = False

# ===============================
# TELEGRAM
# ===============================
def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except:
        pass

# ===============================
# BOT START
# ===============================
def iniciar_bot():
    global bot_iniciado
    if not bot_iniciado:
        hora = datetime.now(BR_TZ).strftime("%d/%m %H:%M")
        send_telegram(f"🤖 <b>Troia-IA V16 iniciado</b>\n🕒 {hora} (BR)")
        bot_iniciado = True

# ===============================
# ANÁLISE
# ===============================
def analisar(ativo, closes):
    if len(closes) < 6:
        return None

    ult = closes[-5:]
    alta = sum(1 for i in range(1,5) if ult[i] > ult[i-1])
    baixa = 4 - alta

    direcao = "CALL" if alta >= 3 else "PUT"
    conf = 45 + (alta if direcao == "CALL" else baixa) * 2
    prob = conf + 7

    print(f"[CHECK] {ativo} {direcao} conf={conf} prob={prob}")

    if conf >= CONF_MIN and prob >= PROB_MIN:
        return direcao, conf, prob
    return None

# ===============================
# WEBSOCKET
# ===============================
def on_message(ws, message):
    data = json.loads(message)
    if "candles" not in data:
        return

    ativo = data["echo_req"]["ticks_history"]
    closes = [float(c["close"]) for c in data["candles"]]
    agora = int(time.time())

    if agora - ultimo_sinal[ativo] < COOLDOWN_ATIVO:
        return

    sinais_hora.append(agora)
    while sinais_hora and agora - sinais_hora[0] > 3600:
        sinais_hora.popleft()

    if len(sinais_hora) >= MAX_SINAIS_HORA:
        return

    r = analisar(ativo, closes)
    if not r:
        return

    direcao, conf, prob = r
    ultimo_sinal[ativo] = agora
    hora = datetime.now(BR_TZ).strftime("%H:%M")

    send_telegram(
        f"📊 <b>SINAL FOREX</b>\n"
        f"📌 <b>{ativo}</b>\n"
        f"⏱️ {TIMEFRAME//60}m | {hora}\n"
        f"🎯 <b>{direcao}</b>\n"
        f"📈 Conf: {conf}% | Prob: {prob}%"
    )

def on_open(ws):
    iniciar_bot()
    for ativo in ATIVOS:
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": 20
        }))
        time.sleep(0.25)

def on_error(ws, error):
    print("Erro WebSocket:", error)

def on_close(ws, *args):
    print("WebSocket fechado. Reconectando...")
    threading.Thread(target=reconectar_ws, daemon=True).start()

def reconectar_ws():
    time.sleep(5)
    iniciar_ws()

def iniciar_ws():
    ws = websocket.WebSocketApp(
        DERIV_WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever(ping_interval=30, ping_timeout=10)

# ===============================
# HTTP KEEP ALIVE
# ===============================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Troia-IA V16 ONLINE")

def iniciar_http():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    threading.Thread(target=iniciar_http, daemon=True).start()
    iniciar_ws()
