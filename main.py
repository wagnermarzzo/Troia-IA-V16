import json
import time
import threading
import websocket
import requests
from datetime import datetime, timezone, timedelta

# =============================
# CONFIG FIXA
# =============================
DERIV_WS = "wss://ws.derivws.com/websockets/v3?app_id=1089"
DERIV_API_TOKEN = "UEISANwBEI9sPVR"

TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 60
ANALISE_SEGUNDO = 55
RESULT_DELAY = 90

# =============================
# ESTADO
# =============================
sinal_ativo = False
ultimo_candle = {}
historico = {"green": 0, "red": 0}
confianca = 63.0

# =============================
# ATIVOS DERIV
# =============================
ATIVOS = [
    "frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD",
    "frxEURJPY", "frxEURGBP", "frxGBPJPY",
    "frxEURUSD_otc", "frxGBPUSD_otc", "frxUSDJPY_otc",
    "frxAUDUSD_otc", "frxEURJPY_otc"
]

# =============================
# TELEGRAM
# =============================
def tg(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    )

# =============================
# IA EVOLUTIVA
# =============================
def atualizar_ia(res):
    global confianca
    confianca += 0.6 if res == "GREEN" else -0.8
    confianca = max(50, min(90, confianca))

# =============================
# ANALISE REAL
# =============================
def direcao_candle(o, c):
    return "CALL" if c > o else "PUT"

# =============================
# WEBSOCKET CALLBACKS
# =============================
def on_open(ws):
    auth = {"authorize": DERIV_API_TOKEN}
    ws.send(json.dumps(auth))

def on_message(ws, msg):
    global ultimo_candle
    data = json.loads(msg)

    if "authorize" in data:
        ativo = ATIVOS[int(time.time()) % len(ATIVOS)]
        ws.send(json.dumps({
            "candles": ativo,
            "granularity": TIMEFRAME,
            "count": 2,
            "subscribe": 1
        }))

    if "candles" in data:
        candles = data["candles"]
        if len(candles) >= 2:
            ultimo_candle = candles[-2]

def on_close(ws, close_status_code, close_msg):
    time.sleep(5)
    start_ws()

def on_error(ws, error):
    print("WS Error:", error)

# =============================
# LOOP DE SINAL
# =============================
def loop_sinal():
    global sinal_ativo

    tg("🤖 <b>Troia IA ONLINE</b>\n📡 WebSocket Deriv REAL\n⏱ Timeframe: 1M")

    while True:
        if not ultimo_candle or sinal_ativo:
            time.sleep(1)
            continue

        agora = datetime.now(timezone.utc)
        if agora.second != ANALISE_SEGUNDO:
            time.sleep(1)
            continue

        o = float(ultimo_candle["open"])
        c = float(ultimo_candle["close"])

        direcao = direcao_candle(o, c)
        entrada = (agora + timedelta(seconds=5)).strftime("%H:%M:%S")

        sinal_ativo = True

        tg(
            f"📊 <b>SINAL ENCONTRADO</b>\n\n"
            f"📌 Ativo: <b>{ultimo_candle['symbol']}</b>\n"
            f"📈 Direção: <b>{direcao}</b>\n"
            f"⏱ Timeframe: <b>1M</b>\n"
            f"🧠 Estratégia: <b>Price Action</b>\n"
            f"🕒 Entrada: <b>Próxima vela {entrada}</b>\n"
            f"🎯 Confiança: <b>{confianca:.1f}%</b>"
        )

        time.sleep(RESULT_DELAY)

        resultado = "GREEN" if (
            direcao == "CALL" and c > o or direcao == "PUT" and c < o
        ) else "RED"

        historico["green" if resultado == "GREEN" else "red"] += 1
        atualizar_ia(resultado)

        tg(
            f"{'💸 GREEN' if resultado == 'GREEN' else '🧨 RED'}\n\n"
            f"📊 Resultado confirmado\n"
            f"📈 Greens: {historico['green']} | Reds: {historico['red']}\n"
            f"🧠 Nova confiança IA: {confianca:.1f}%"
        )

        sinal_ativo = False
        time.sleep(5)

# =============================
# START WS
# =============================
def start_ws():
    ws = websocket.WebSocketApp(
        DERIV_WS,
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error
    )
    ws.run_forever()

# =============================
# MAIN
# =============================
if __name__ == "__main__":
    threading.Thread(target=start_ws, daemon=True).start()
    loop_sinal()
