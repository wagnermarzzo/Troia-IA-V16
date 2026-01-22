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
DERIV_API_KEY = "UEISANwBEI9sPVR"

TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

TIMEFRAME = 180  # M3
BR_TZ = timezone(timedelta(hours=-3))
PORT = int(os.environ.get("PORT", 8080))

ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD"
]

# ===============================
# ESTADO GLOBAL
# ===============================
bot_iniciado = False
sinal_aberto = False
dados_sinal = {}
ultimo_candle = {}
modo = "CONSERVADOR"  # muda automaticamente

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
        send_telegram(f"🤖 <b>Troia-IA V16 ONLINE</b>\n⏱️ M3 | Mercado REAL\n🕒 {hora} (BR)")
        bot_iniciado = True

# ===============================
# ESTRATÉGIA
# ===============================
def analisar_candle(candles):
    if len(candles) < 3:
        return None

    c1, c2 = candles[-2], candles[-1]

    direcao = "CALL" if c2["close"] > c2["open"] else "PUT"
    forca = abs(c2["close"] - c2["open"])

    if modo == "CONSERVADOR" and forca < 0.00005:
        return None

    return direcao

# ===============================
# PROCESSA FECHAMENTO
# ===============================
def processar_fechamento(ativo, candles):
    global sinal_aberto, dados_sinal, modo

    if sinal_aberto:
        c = candles[-1]
        resultado = "GREEN" if (
            (dados_sinal["direcao"] == "CALL" and c["close"] > c["open"]) or
            (dados_sinal["direcao"] == "PUT" and c["close"] < c["open"])
        ) else "RED"

        send_telegram(
            f"{'🟢' if resultado=='GREEN' else '🔴'} <b>RESULTADO</b>\n"
            f"📌 {ativo}\n"
            f"🎯 {dados_sinal['direcao']}\n"
            f"📊 <b>{resultado}</b>"
        )

        modo = "AGRESSIVO" if resultado == "GREEN" else "CONSERVADOR"
        sinal_aberto = False
        dados_sinal = {}
        return

    direcao = analisar_candle(candles)
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
def on_message(ws, message):
    data = json.loads(message)
    if "candles" not in data:
        return

    ativo = data["echo_req"]["ticks_history"]
    candles = data["candles"]

    for c in candles:
        c["open"] = float(c["open"])
        c["close"] = float(c["close"])

    ultimo = candles[-1]["epoch"]
    if ultimo_candle.get(ativo) == ultimo:
        return

    ultimo_candle[ativo] = ultimo
    processar_fechamento(ativo, candles)

def on_open(ws):
    iniciar_bot()
    for ativo in ATIVOS:
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": 10
        }))
        time.sleep(0.2)

def on_error(ws, error):
    print("WS ERRO:", error)

def on_close(ws, *args):
    send_telegram("⚠️ WebSocket caiu. Reconectando...")
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
# HTTP RAILWAY
# ===============================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"TROIA-IA V16 ONLINE")

def iniciar_http():
    HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    threading.Thread(target=iniciar_http, daemon=True).start()
    iniciar_ws()
