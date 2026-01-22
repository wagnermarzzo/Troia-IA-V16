import json, time, requests, threading, websocket
from collections import deque
from datetime import datetime

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 300
WAIT_BUFFER = 10
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

sinal_em_analise = threading.Event()

# ===============================
# MODOS
# ===============================
MODO = "MODERADO"

MODOS = {
    "AGRESSIVO":  {"CONF_MIN":48,"PROB_MIN":52,"CONFIRM":1,"TEND":8,"MINPCT":0.0001},
    "MODERADO":   {"CONF_MIN":50,"PROB_MIN":55,"CONFIRM":2,"TEND":12,"MINPCT":0.00015},
    "CONSERVADOR":{"CONF_MIN":55,"PROB_MIN":60,"CONFIRM":3,"TEND":20,"MINPCT":0.00025}
}

CFG = MODOS[MODO]

# ===============================
# ATIVOS
# ===============================
ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD",
    "frxUSDCHF","frxNZDUSD","frxEURGBP","frxEURJPY","frxGBPJPY",
    "frxUSDTRY","frxUSDZAR","frxUSDMXN"
]

# ===============================
# ESTATÍSTICAS
# ===============================
stats = {"total":0,"green":0,"red":0}
historico_resultados = deque(maxlen=5)

# ===============================
# TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except:
        pass

# ===============================
# IA ADAPTATIVA
# ===============================
def ia_adaptativa():
    global MODO, CFG

    if len(historico_resultados) < 5:
        return

    g = historico_resultados.count("G")
    r = historico_resultados.count("R")

    novo = "MODERADO"
    if r >= 4:
        novo = "CONSERVADOR"
    elif g >= 4:
        novo = "AGRESSIVO"

    if novo != MODO:
        MODO = novo
        CFG = MODOS[MODO]
        tg(
            f"🧠 <b>IA ADAPTATIVA</b>\n"
            f"Modo ajustado para: <b>{MODO}</b>\n"
            f"Últimos 5: {''.join(historico_resultados)}"
        )

# ===============================
# ANÁLISES
# ===============================
def direcao(c): return "CALL" if c["close"] > c["open"] else "PUT"

def direcao_confirmada(c):
    ult = c[-CFG["CONFIRM"]:]
    if all(direcao(x) == "CALL" for x in ult): return "CALL"
    if all(direcao(x) == "PUT" for x in ult): return "PUT"
    return None

def confianca(c):
    return int(max(
        sum(1 for x in c if direcao(x) == "CALL"),
        sum(1 for x in c if direcao(x) == "PUT")
    ) / len(c) * 100)

def tendencia(c):
    return "CALL" if c[-1]["close"] > c[-CFG["TEND"]]["close"] else "PUT"

def candle_ok(c):
    return abs(c["close"] - c["open"]) / c["open"] >= CFG["MINPCT"]

def prob(c, d):
    return int(sum(1 for x in c if direcao(x) == d) / len(c) * 100)

# ===============================
# DERIV
# ===============================
def candles_ws(ativo, count=50):
    try:
        ws = websocket.create_connection(DERIV_WS_URL, timeout=6)
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
def resultado(res):
    time.sleep(res["tempo"])
    c = candles_ws(res["ativo"], 1)
    win = c and direcao(c[-1]) == res["dir"]

    stats["total"] += 1
    if win:
        stats["green"] += 1
        historico_resultados.append("G")
    else:
        stats["red"] += 1
        historico_resultados.append("R")

    ia_adaptativa()

    acc = int(stats["green"] / stats["total"] * 100)

    tg(
        f"📊 <b>RESULTADO</b>\n"
        f"{'🟢 GREEN' if win else '🔴 RED'}\n\n"
        f"🎯 Assertividade: {acc}%\n"
        f"📈 Total: {stats['total']}\n"
        f"Modo atual: {MODO}"
    )

    sinal_em_analise.clear()

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop():
    tg("🚀 <b>BOT INICIADO</b>\nIA Adaptativa ATIVA")
    ultimo = {}

    while True:
        for ativo in ATIVOS:
            if sinal_em_analise.is_set():
                break

            c = candles_ws(ativo)
            if len(c) < 30:
                continue

            d = direcao_confirmada(c)
            if not d or not candle_ok(c[-1]):
                continue

            if d != tendencia(c):
                continue

            if confianca(c[-20:]) < CFG["CONF_MIN"]:
                continue

            if prob(c, d) < CFG["PROB_MIN"]:
                continue

            if ultimo.get(ativo) == d:
                continue

            ultimo[ativo] = d
            sinal_em_analise.set()

            tg(
                f"💥 <b>SINAL</b>\n"
                f"Ativo: {ativo}\n"
                f"Direção: {d}\n"
                f"Modo: {MODO}\n"
                f"Entrada: Próxima vela"
            )

            threading.Thread(
                target=resultado,
                args=({"ativo":ativo,"dir":d,"tempo":TIMEFRAME+WAIT_BUFFER},),
                daemon=True
            ).start()

        time.sleep(1)

# ===============================
# START
# ===============================
loop()
