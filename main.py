import json, time, requests, threading, websocket, os
from datetime import datetime, timezone, timedelta

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 300
CONF_MIN = 55
PROB_MIN = 70
WAIT_BUFFER = 10
RECONNECT_DELAY = 5

DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

sinal_em_analise = threading.Event()

# ===============================
# ATIVOS
# ===============================
ATIVOS_FOREX = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD","frxUSDCHF",
    "frxNZDUSD","frxEURGBP","frxEURJPY","frxEURCHF","frxEURAUD","frxEURCAD",
    "frxEURNZD","frxGBPJPY","frxGBPCHF","frxGBPAUD","frxGBPCAD","frxGBPNZD"
]

ATIVOS_OTC = [
    "frxUSDTRY","frxUSDRUB","frxUSDZAR","frxUSDMXN","frxUSDHKD"
]

ATIVOS = ATIVOS_FOREX + ATIVOS_OTC

# ===============================
# TELEGRAM
# ===============================
def enviar_sinal(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except:
        pass

# ===============================
# ANÁLISES (MANTIDAS)
# ===============================
def direcao_candle(c):
    return "CALL" if c["close"] > c["open"] else "PUT"

def direcao_confirmada(candles, n=3):
    ult = candles[-n:]
    if all(c["close"] > c["open"] for c in ult): return "CALL"
    if all(c["close"] < c["open"] for c in ult): return "PUT"
    return None

def calcular_confianca(candles):
    return int(max(
        sum(1 for c in candles if c["close"] > c["open"]),
        sum(1 for c in candles if c["close"] < c["open"])
    ) / len(candles) * 100)

def tendencia_medio_prazo(candles, p=20):
    return "CALL" if candles[-1]["close"] > candles[-p]["close"] else "PUT"

def candle_valido(c, min_pct=0.0003):
    return abs(c["close"] - c["open"]) / c["open"] >= min_pct

def probabilidade_real(candles, d):
    return int(sum(1 for c in candles if direcao_candle(c) == d) / len(candles) * 100)

# ===============================
# DERIV WS (SEGURO)
# ===============================
def pegar_candles_ws(ativo, count=50):
    try:
        ws = websocket.create_connection(DERIV_WS_URL, timeout=8)
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": count
        }))
        data = json.loads(ws.recv())
        ws.close()
        return data.get("candles", [])
    except:
        return []

# ===============================
# RESULTADO
# ===============================
def aguardar_resultado(res):
    time.sleep(res["tempo"])
    candles = pegar_candles_ws(res["ativo"], 1)
    resultado = "🟢 GREEN" if candles and direcao_candle(candles[-1]) == res["dir"] else "🔴 RED"

    enviar_sinal(
        f"📊 <b>RESULTADO</b>\n"
        f"Ativo: {res['ativo']}\n"
        f"Direção: {res['dir']}\n"
        f"{resultado}"
    )
    sinal_em_analise.clear()

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop_principal():
    enviar_sinal("🚀 <b>Sentinel IA iniciado</b>")

    ultimo = {}

    while True:
        for ativo in ATIVOS:
            if sinal_em_analise.is_set():
                break

            candles = pegar_candles_ws(ativo)
            if len(candles) < 30:
                continue

            direcao = direcao_confirmada(candles)
            if not direcao or not candle_valido(candles[-1]):
                continue

            confianca = calcular_confianca(candles[-20:])
            if direcao != tendencia_medio_prazo(candles):
                continue

            if confianca < CONF_MIN or probabilidade_real(candles, direcao) < PROB_MIN:
                continue

            if ultimo.get(ativo) == direcao:
                continue

            sinal_em_analise.set()
            ultimo[ativo] = direcao

            enviar_sinal(
                f"💥 <b>SINAL</b>\n"
                f"Ativo: {ativo}\n"
                f"Direção: {direcao}\n"
                f"Confiança: {confianca}%\n"
                f"Entrada: Próxima vela"
            )

            threading.Thread(
                target=aguardar_resultado,
                args=({"ativo": ativo, "dir": direcao, "tempo": TIMEFRAME + WAIT_BUFFER},),
                daemon=True
            ).start()

        time.sleep(1)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    loop_principal()
