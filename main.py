import websocket
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"

TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

TIMEFRAME = 300  # 5 minutos
CONF_MIN = 46
PROB_MIN = 53

MAX_SINAIS_HORA = 8
COOLDOWN_ATIVO = 240  # 4 minutos

BR_TZ = timezone(timedelta(hours=-3))

# ===============================
# ATIVOS FOREX (10)
# ===============================
ATIVOS = [
    "frxEURUSD",
    "frxGBPUSD",
    "frxUSDJPY",
    "frxAUDUSD",
    "frxUSDCAD",
    "frxUSDCHF",
    "frxEURJPY",
    "frxGBPJPY",
    "frxEURGBP",
    "frxAUDJPY"
]

# ===============================
# CONTROLE
# ===============================
ultimo_sinal_ativo = defaultdict(int)
sinais_hora = deque()
bot_iniciado = False

# ===============================
# TELEGRAM
# ===============================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=data, timeout=5)
    except:
        pass

# ===============================
# START BOT (UMA VEZ)
# ===============================
def iniciar_bot():
    global bot_iniciado
    if not bot_iniciado:
        agora = datetime.now(BR_TZ).strftime("%d/%m %H:%M")
        send_telegram(
            f"🤖 <b>Troia-IA V16 iniciado</b>\n"
            f"📊 Modo: SIGNAL MODE\n"
            f"🕒 {agora} (BR)"
        )
        bot_iniciado = True

# ===============================
# LÓGICA DE ANÁLISE
# ===============================
def analisar_ativo(ativo, closes):
    if len(closes) < 6:
        return None

    ultimos = closes[-5:]
    altas = sum(1 for i in range(1, 5) if ultimos[i] > ultimos[i - 1])
    baixas = 4 - altas

    if altas >= 3:
        direcao = "CALL"
        conf = 45 + altas * 2
    else:
        direcao = "PUT"
        conf = 45 + baixas * 2

    prob = conf + 7

    print(f"[CHECK] {ativo} {direcao} conf={conf} prob={prob}")

    if conf >= CONF_MIN and prob >= PROB_MIN:
        return direcao, conf, prob

    return None

# ===============================
# WEBSOCKET CALLBACKS
# ===============================
def on_message(ws, message):
    data = json.loads(message)

    if "candles" not in data:
        return

    ativo = data["echo_req"].get("ticks_history")
    closes = [float(c["close"]) for c in data["candles"]]

    agora_ts = int(time.time())

    # cooldown por ativo
    if agora_ts - ultimo_sinal_ativo[ativo] < COOLDOWN_ATIVO:
        return

    # limite por hora
    sinais_hora.append(agora_ts)
    while sinais_hora and agora_ts - sinais_hora[0] > 3600:
        sinais_hora.popleft()

    if len(sinais_hora) >= MAX_SINAIS_HORA:
        return

    resultado = analisar_ativo(ativo, closes)
    if not resultado:
        return

    direcao, conf, prob = resultado
    ultimo_sinal_ativo[ativo] = agora_ts

    hora_br = datetime.now(BR_TZ).strftime("%H:%M")

    send_telegram(
        f"📊 <b>SINAL FOREX</b>\n"
        f"📌 <b>{ativo}</b>\n"
        f"⏱️ {TIMEFRAME//60}m | {hora_br}\n"
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
        time.sleep(0.2)

def on_error(ws, error):
    print("Erro WebSocket:", error)

def on_close(ws):
    print("WebSocket fechado. Reconectando em 5s...")
    time.sleep(5)
    iniciar_ws()

# ===============================
# INICIAR WS
# ===============================
def iniciar_ws():
    ws = websocket.WebSocketApp(
        DERIV_WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    iniciar_ws()
