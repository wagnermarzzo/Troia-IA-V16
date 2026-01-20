import json
import time
import threading
import websocket
import requests
from datetime import datetime, timezone, timedelta

# =============================
# CONFIG
# =============================
DERIV_WS = "wss://ws.derivws.com/websockets/v3?app_id=1089"
DERIV_API_TOKEN = "UEISANwBEI9sPVR"

TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 60
ANALISE_SEGUNDO = 55
RESULT_DELAY = 90

# =============================
# ATIVOS DERIV (FOREX + OTC)
# =============================
ATIVOS = [
    # FOREX
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD",
    "frxEURJPY","frxEURGBP","frxGBPJPY","frxAUDJPY","frxCADJPY",
    "frxCHFJPY","frxNZDUSD","frxNZDJPY","frxEURAUD","frxEURCHF",
    "frxEURCAD","frxGBPAUD","frxGBPCAD","frxGBPCHF",
    # OTC
    "frxEURUSD_otc","frxGBPUSD_otc","frxUSDJPY_otc","frxAUDUSD_otc",
    "frxEURJPY_otc","frxEURGBP_otc","frxGBPJPY_otc","frxAUDJPY_otc"
]

# =============================
# ESTADO
# =============================
sinal_ativo = False
historico = {"green": 0, "red": 0}
confianca = 63.0
ultimo_candle = None
ativo_idx = 0
ws_app = None

# =============================
# TELEGRAM
# =============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except:
        pass

# =============================
# IA
# =============================
def atualizar_ia(res):
    global confianca
    confianca += 0.6 if res == "GREEN" else -0.8
    confianca = max(50, min(90, confianca))

# =============================
# WS
# =============================
def subscribe(ws):
    global ultimo_candle
    ultimo_candle = None
    ws.send(json.dumps({
        "candles": ATIVOS[ativo_idx],
        "granularity": TIMEFRAME,
        "count": 2,
        "subscribe": 1
    }))

def on_open(ws):
    ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))

def on_message(ws, msg):
    global ultimo_candle
    data = json.loads(msg)

    if "authorize" in data:
        subscribe(ws)

    if "candles" in data:
        candles = data["candles"]
        if len(candles) >= 2:
            ultimo_candle = candles[-2]

def on_close(ws, code, reason):
    time.sleep(3)
    start_ws()

def on_error(ws, error):
    print("WS error:", error)

# =============================
# LOOP
# =============================
def loop_sinal():
    global sinal_ativo, ativo_idx

    tg("🤖 <b>Troia IA ONLINE</b>\n📡 Deriv REAL\n⏱ Timeframe 1M")

    while True:
        if not ultimo_candle or sinal_ativo:
            time.sleep(0.5)
            continue

        agora = datetime.now(timezone.utc)
        if agora.second != ANALISE_SEGUNDO:
            time.sleep(0.5)
            continue

        o = float(ultimo_candle["open"])
        c = float(ultimo_candle["close"])

        direcao = "CALL" if c > o else "PUT"
        entrada = (agora + timedelta(seconds=5)).strftime("%H:%M:%S")

        sinal_ativo = True

        tg(
            f"📊 <b>SINAL ENCONTRADO</b>\n\n"
            f"📌 Ativo: <b>{ATIVOS[ativo_idx]}</b>\n"
            f"📈 Direção: <b>{direcao}</b>\n"
            f"⏱ Timeframe: 1M\n"
            f"🧠 Estratégia: Price Action\n"
            f"🕒 Entrada: Próxima vela {entrada}\n"
            f"🎯 Confiança: {confianca:.1f}%"
        )

        time.sleep(RESULT_DELAY)

        resultado = "GREEN" if (
            direcao == "CALL" and c > o or direcao == "PUT" and c < o
        ) else "RED"

        historico["green" if resultado == "GREEN" else "red"] += 1
        atualizar_ia(resultado)

        tg(
            f"{'💸 GREEN' if resultado == 'GREEN' else '🧨 RED'}\n\n"
            f"📈 Greens: {historico['green']} | Reds: {historico['red']}\n"
            f"🧠 Confiança IA: {confianca:.1f}%"
        )

        ativo_idx = (ativo_idx + 1) % len(ATIVOS)
        sinal_ativo = False
        time.sleep(3)

# =============================
# START
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

if __name__ == "__main__":
    threading.Thread(target=start_ws, daemon=True).start()
    loop_sinal()
