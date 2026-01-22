import websocket
import json
import time
import requests
import threading
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import sys

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
# ESTADO GLOBAL
# ===============================
bot_iniciado = False
sinal_aberto = False
dados_sinal = {}
ultimo_candle = {}
modo = "CONSERVADOR"
ws_ativo = False

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
        hora = datetime.now(BR_TZ).strftime("%d/%m %H:%M")
        send_telegram(
            f"🤖 <b>Troia-IA V16.2 ONLINE</b>\n"
            f"⏱️ M3 | Mercado REAL\n"
            f"📊 Ativos: {len(ATIVOS)}\n"
            f"🕒 {hora} (BR)"
        )
        bot_iniciado = True

# ===============================
# ESTRATÉGIA
# ===============================
def analisar(candles):
    if len(candles) < 3:
        return None

    c = candles[-1]
    direcao = "CALL" if c["close"] > c["open"] else "PUT"

    corpo = abs(c["close"] - c["open"])
    if modo == "CONSERVADOR" and corpo < 0.00005:
        return None

    return direcao

# ===============================
# FECHAMENTO DE CANDLE
# ===============================
def processar_candle(ativo, candles):
    global sinal_aberto, dados_sinal, modo

    # ===== RESULTADO =====
    if sinal_aberto:
        c = candles[-1]
        green = (
            (dados_sinal["direcao"] == "CALL" and c["close"] > c["open"]) or
            (dados_sinal["direcao"] == "PUT" and c["close"] < c["open"])
        )

        send_telegram(
            f"{'🟢' if green else '🔴'} <b>RESULTADO</b>\n"
            f"📌 {ativo}\n"
            f"🎯 {dados_sinal['direcao']}\n"
            f"📊 <b>{'GREEN' if green else 'RED'}</b>"
        )

        modo = "AGRESSIVO" if green else "CONSERVADOR"
        sinal_aberto = False
        dados_sinal = {}
        return

    # ===== NOVO SINAL =====
    direcao = analisar(candles)
    if not direcao:
        return

    sinal_aberto = True
    dados_sinal = {"direcao": direcao}

    hora = datetime.now(BR_TZ).strftime("%H:%M")
    send_telegram(
        f"📊 <b>SINAL M3</b>\n"
        f"📌 {ativo}\n"
        f"🎯 <b>{direcao}</b>\n"
        f"🕒 {hora}\n"
        f"⚙️ Modo: {modo}"
    )

# ===============================
# WEBSOCKET
# ===============================
def on_message(ws, msg):
    data = json.loads(msg)
    if "candles" not in data:
        return

    ativo = data["echo_req"]["ticks_history"]
    candles = data["candles"]

    for c in candles:
        c["open"] = float(c["open"])
        c["close"] = float(c["close"])

    epoch = candles[-1]["epoch"]
    if ultimo_candle.get(ativo) == epoch:
        return

    ultimo_candle[ativo] = epoch
    processar_candle(ativo, candles)

def on_open(ws):
    global ws_ativo
    ws_ativo = True
    iniciar_bot()

    for ativo in ATIVOS:
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": 10
        }))
        time.sleep(0.25)

def on_error(ws, err):
    print("WS ERRO:", err)

def on_close(ws, *args):
    global ws_ativo
    ws_ativo = False
    send_telegram("⚠️ WebSocket desconectado. Tentando reconectar...")

# ===============================
# LOOP WS BLINDADO
# ===============================
def ws_loop():
    while True:
        try:
            ws = websocket.WebSocketApp(
                DERIV_WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except:
            send_telegram("🚨 Falha crítica no WebSocket. Reiniciando...")
            time.sleep(5)

# ===============================
# WATCHDOG (RAILWAY)
# ===============================
def watchdog():
    while True:
        if not ws_ativo:
            send_telegram("⚠️ WebSocket inativo. Reiniciando serviço...")
            os._exit(1)
        time.sleep(60)

# ===============================
# HTTP KEEP ALIVE
# ===============================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"TROIA-IA V16.2 ONLINE")

def iniciar_http():
    HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    threading.Thread(target=iniciar_http, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()
    ws_loop()
