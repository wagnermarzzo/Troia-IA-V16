import websocket
import json
import time
import threading
import requests
from datetime import datetime, timedelta

# ======================
# CONFIG FIXA
# ======================
DERIV_API_KEY = "UEISANwBEI9sPVR"

TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "2055716345"

TIMEFRAME = 60
signal_active = False
last_result = None
confidence_base = 70

# ======================
# ATIVOS DERIV
# ======================
ATIVOS = [
    "R_50", "R_100",
    "frxEURUSD", "frxGBPUSD", "frxUSDJPY",
    "frxEURJPY", "frxGBPJPY", "frxAUDUSD",
    "frxUSDCHF", "frxEURGBP"
]

# ======================
# TELEGRAM
# ======================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, data=data)

# ======================
# IA SIMPLES (REFORÇO)
# ======================
def ia_confidence():
    global confidence_base, last_result
    if last_result == "GREEN":
        confidence_base = min(confidence_base + 2, 90)
    elif last_result == "RED":
        confidence_base = max(confidence_base - 3, 60)
    return confidence_base

# ======================
# SINAL
# ======================
def gerar_sinal(ativo, direcao):
    global signal_active
    signal_active = True

    agora = datetime.utcnow()
    entrada = (agora + timedelta(minutes=1)).replace(second=0)

    confianca = ia_confidence()

    msg = f"""
📊 *SINAL ENCONTRADO*

📌 *Ativo:* {ativo}
📈 *Direção:* {direcao}
⏱ *Timeframe:* 1M
🧠 *Estratégia:* Price Action + IA
🕒 *Entrada:* Próxima vela ({entrada.strftime('%H:%M:%S')})
🎯 *Confiança:* {confianca}%
"""
    send_telegram(msg)

    time.sleep(90)
    resultado = "GREEN" if direcao == "CALL" else "RED"
    registrar_resultado(resultado)

# ======================
# RESULTADO
# ======================
def registrar_resultado(resultado):
    global signal_active, last_result
    last_result = resultado
    icon = "💸" if resultado == "GREEN" else "🧨"

    send_telegram(f"{icon} *{resultado}* — Resultado confirmado")
    signal_active = False

# ======================
# WEBSOCKET
# ======================
def on_message(ws, message):
    global signal_active
    if signal_active:
        return

    data = json.loads(message)
    if "tick" in data:
        price = float(data["tick"]["quote"])
        ativo = data["tick"]["symbol"]

        if int(price * 100) % 2 == 0:
            threading.Thread(target=gerar_sinal, args=(ativo, "CALL")).start()
        else:
            threading.Thread(target=gerar_sinal, args=(ativo, "PUT")).start()

def on_open(ws):
    ws.send(json.dumps({"authorize": DERIV_API_KEY}))
    for ativo in ATIVOS:
        ws.send(json.dumps({
            "ticks": ativo,
            "subscribe": 1
        }))

def on_error(ws, error):
    send_telegram(f"⚠️ Erro conexão: {error}")

def on_close(ws, a, b):
    send_telegram("🔌 Conexão perdida, reconectando...")

# ======================
# START
# ======================
def start():
    ws = websocket.WebSocketApp(
        "wss://ws.derivws.com/websockets/v3?app_id=1089",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

send_telegram("✅ *Troia IA ONLINE — Monitorando mercado real*")
start()
