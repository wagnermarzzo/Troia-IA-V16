import websocket
import json
import time
import threading
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify

# ===============================
# CREDENCIAIS (JÁ INSERIDAS)
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 300  # 5 minutos
MAX_SINAIS_30M = 3

# ===============================
# ATIVOS (FOREX + OTC)
# ===============================
ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD",
    "frxUSDCHF","frxEURJPY","frxGBPJPY","frxEURGBP",
    "frxEURUSD_otc","frxGBPUSD_otc","frxUSDJPY_otc",
    "frxAUDUSD_otc","frxUSDCAD_otc","frxEURJPY_otc"
]

# ===============================
# CONTROLE GLOBAL
# ===============================
SINAL_ATIVO = False
ATIVO_ATUAL = None
DIRECAO_ATUAL = None
HORARIO_ENTRADA = None

SINAIS_30M = []
STATS = {a: {"win": 0, "loss": 0} for a in ATIVOS}

# ===============================
# FLASK – PAINEL WEB REAL
# ===============================
app = Flask(__name__)

@app.route("/")
def painel():
    return jsonify({
        "bot": "TROIA v24 STABLE",
        "status": "ONLINE",
        "sinal_ativo": SINAL_ATIVO,
        "ativo_atual": ATIVO_ATUAL,
        "direcao": DIRECAO_ATUAL,
        "sinais_ultimos_30m": len(SINAIS_30M),
        "stats": STATS
    })

def run_flask():
    app.run(host="0.0.0.0", port=8080)

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
# DERIV – CANDLES REAIS
# ===============================
def get_candles(symbol, count=20):
    ws = websocket.create_connection(
        "wss://ws.deriv.com/websockets/v3?app_id=1089",
        timeout=10
    )
    ws.send(json.dumps({"authorize": DERIV_API_KEY}))
    ws.recv()

    ws.send(json.dumps({
        "ticks_history": symbol,
        "count": count,
        "granularity": TIMEFRAME,
        "style": "candles"
    }))
    r = json.loads(ws.recv())
    ws.close()
    return r["candles"]

# ===============================
# ANÁLISE (PRICE ACTION)
# ===============================
def analisar_ativo(ativo):
    candles = get_candles(ativo, 10)
    verdes = sum(1 for c in candles if c["close"] > c["open"])
    vermelhos = len(candles) - verdes

    if verdes >= 7:
        return "CALL", 70 + verdes * 3
    if vermelhos >= 7:
        return "PUT", 70 + vermelhos * 3
    return None

# ===============================
# MOTOR PRINCIPAL (ESTÁVEL)
# ===============================
def iniciar_troia():
    global SINAL_ATIVO, ATIVO_ATUAL, DIRECAO_ATUAL

    tg("🤖 TROIA v24 STABLE ONLINE")
    idx = 0

    while True:

        agora = datetime.utcnow()
        SINAIS_30M[:] = [t for t in SINAIS_30M if (agora - t).seconds < 1800]

        # LIMITE 1–3 SINAIS / 30 MIN
        if len(SINAIS_30M) >= MAX_SINAIS_30M:
            time.sleep(20)
            continue

        # BLOQUEIO SE EXISTE SINAL
        if SINAL_ATIVO:
            time.sleep(TIMEFRAME)
            try:
                candle = get_candles(ATIVO_ATUAL, 1)[-1]
                real = "CALL" if candle["close"] > candle["open"] else "PUT"
                green = real == DIRECAO_ATUAL
                STATS[ATIVO_ATUAL]["win" if green else "loss"] += 1

                tg(f"📊 RESULTADO\n{ATIVO_ATUAL}\n{'GREEN 🟢' if green else 'RED 🔴'}")
            except:
                pass

            SINAL_ATIVO = False
            time.sleep(10)
            continue

        # FILA DE ATIVOS
        ativo = ATIVOS[idx % len(ATIVOS)]
        idx += 1

        try:
            r = analisar_ativo(ativo)
            if r:
                direcao, conf = r
                SINAL_ATIVO = True
                ATIVO_ATUAL = ativo
                DIRECAO_ATUAL = direcao
                SINAIS_30M.append(datetime.utcnow())

                entrada = (datetime.utcnow() + timedelta(seconds=TIMEFRAME)).strftime("%H:%M UTC")

                tg(
                    f"🔥 SINAL TROIA\n"
                    f"Ativo: {ativo}\n"
                    f"Direção: {direcao}\n"
                    f"Entrada: {entrada}\n"
                    f"Confiança: {conf}%"
                )
        except:
            pass

        time.sleep(3)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    iniciar_troia()
