import websocket
import json
import time
import requests
import threading
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 180  # M3
BR_TZ = timezone(timedelta(hours=-3))
PORT = int(os.environ.get("PORT", 8080))

ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD",
    "frxUSDCHF","frxEURJPY","frxGBPJPY","frxEURGBP","frxAUDJPY"
]

# ===============================
# ESTADO
# ===============================
bot_iniciado = False
ws_ativo = False
ws = None

ativo_index = 0
ativo_atual = ATIVOS[0]

sinal_aberto = False
dados_sinal = {}
ultimo_epoch = None

modo = "CONSERVADOR"

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
# START
# ===============================
def iniciar_bot():
    global bot_iniciado
    if not bot_iniciado:
        send_telegram(
            f"🤖 <b>Troia-IA V16.3 ONLINE</b>\n"
            f"⏱️ M3 | Mercado REAL\n"
            f"📊 Ativos: {len(ATIVOS)}\n"
            f"🕒 {datetime.now(BR_TZ).strftime('%d/%m %H:%M')} (BR)"
        )
        bot_iniciado = True

# ===============================
# ESTRATÉGIA
# ===============================
def analisar(candles):
    c = candles[-1]
    corpo = abs(c["close"] - c["open"])

    if modo == "CONSERVADOR" and corpo < 0.00005:
        return None

    return "CALL" if c["close"] > c["open"] else "PUT"

# ===============================
# PROCESSAMENTO
# ===============================
def avancar_ativo():
    global ativo_index, ativo_atual
    ativo_index = (ativo_index + 1) % len(ATIVOS)
    ativo_atual = ATIVOS[ativo_index]
    time.sleep(1)
    solicitar_candles()

def processar_candle(candles):
    global sinal_aberto, dados_sinal, modo

    c = candles[-1]

    if sinal_aberto:
        green = (
            (dados_sinal["direcao"] == "CALL" and c["close"] > c["open"]) or
            (dados_sinal["direcao"] == "PUT" and c["close"] < c["open"])
        )

        send_telegram(
            f"{'🟢' if green else '🔴'} <b>RESULTADO</b>\n"
            f"📌 {ativo_atual}\n"
            f"🎯 {dados_sinal['direcao']}\n"
            f"📊 <b>{'GREEN' if green else 'RED'}</b>"
        )

        modo = "AGRESSIVO" if green else "CONSERVADOR"
        sinal_aberto = False
        dados_sinal = {}
        avancar_ativo()
        return

    direcao = analisar(candles)
    if direcao:
        sinal_aberto = True
        dados_sinal = {"direcao": direcao}
        send_telegram(
            f"📊 <b>SINAL M3</b>\n"
            f"📌 {ativo_atual}\n"
            f"🎯 <b>{direcao}</b>\n"
            f"🕒 {datetime.now(BR_TZ).strftime('%H:%M')}\n"
            f"⚙️ Modo: {modo}"
        )
        return

    avancar_ativo()

# ===============================
# WS
# ===============================
def solicitar_candles():
    if ws:
        ws.send(json.dumps({
            "ticks_history": ativo_atual,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": 10
        }))

def on_message(ws_, msg):
    global ultimo_epoch
    data = json.loads(msg)

    if "candles" not in data:
        return

    candles = data["candles"]
    for c in candles:
        c["open"] = float(c["open"])
        c["close"] = float(c["close"])

    epoch = candles[-1]["epoch"]
    if epoch == ultimo_epoch:
        return

    ultimo_epoch = epoch
    processar_candle(candles)

def on_open(ws_):
    global ws, ws_ativo
    ws = ws_
    ws_ativo = True
    iniciar_bot()
    solicitar_candles()

def on_close(ws_, *a):
    global ws_ativo
    ws_ativo = False
    send_telegram("⚠️ WebSocket caiu. Reconectando...")

# ===============================
# LOOP WS
# ===============================
def ws_loop():
    while True:
        try:
            websocket.enableTrace(False)
            app = websocket.WebSocketApp(
                DERIV_WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_close=on_close
            )
            app.run_forever(ping_interval=30, ping_timeout=10)
        except:
            time.sleep(5)

# ===============================
# WATCHDOG SAFE
# ===============================
def watchdog():
    while True:
        print("💓 Bot vivo", datetime.now(BR_TZ).strftime("%H:%M:%S"))
        time.sleep(60)

# ===============================
# HTTP
# ===============================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"TROIA-IA V16.3 ONLINE")

def iniciar_http():
    HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    threading.Thread(target=iniciar_http, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()
    ws_loop()
