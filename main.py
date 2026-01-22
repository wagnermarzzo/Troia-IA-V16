import json, time, requests, threading, websocket
from collections import deque, defaultdict
from datetime import datetime, timezone, timedelta

# ===============================
# CONFIGURAÇÃO FIXA (SUAS CREDENCIAIS)
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"

TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 300  # M5
WAIT_BUFFER = 10
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

SCAN_DELAY = 3
MAX_SINAIS_HORA = 8

# UTC-3 (Brasil)
BR_TZ = timezone(timedelta(hours=-3))

sinal_em_analise = threading.Event()
bot_iniciado = False

# ===============================
# MODO – FOCO EM SINAIS
# ===============================
MODO = "AGRESSIVO"

CFG = {
    "CONF_MIN": 42,
    "PROB_MIN": 48,
    "CONFIRM": 1,
    "TEND": 3,
    "MINPCT": 0.00002
}

# ===============================
# ATIVOS — SOMENTE MERCADO REAL
# ===============================
ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD",
    "frxUSDCHF","frxNZDUSD","frxEURJPY","frxGBPJPY"
]

# ===============================
# ESTATÍSTICAS
# ===============================
stats = {"total":0,"green":0,"red":0}
historico_resultados = deque(maxlen=5)
sinais_por_hora = defaultdict(int)

hora_atual = datetime.now(BR_TZ).hour

# ===============================
# TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": msg,
                "parse_mode": "HTML"
            },
            timeout=5
        )
    except:
        pass

# ===============================
# ANÁLISES
# ===============================
def direcao(c):
    return "CALL" if c["close"] > c["open"] else "PUT"

def direcao_confirmada(c):
    ult = c[-CFG["CONFIRM"]:]
    if all(direcao(x) == "CALL" for x in ult): return "CALL"
    if all(direcao(x) == "PUT" for x in ult): return "PUT"
    return None

def confianca(c):
    call = sum(1 for x in c if direcao(x) == "CALL")
    put  = sum(1 for x in c if direcao(x) == "PUT")
    return int(max(call, put) / len(c) * 100)

def tendencia(c):
    if len(c) < CFG["TEND"]:
        return None
    return "CALL" if c[-1]["close"] > c[-CFG["TEND"]]["close"] else "PUT"

def candle_ok(c):
    return abs(c["close"] - c["open"]) / c["open"] >= CFG["MINPCT"]

def prob(c, d):
    return int(sum(1 for x in c if direcao(x) == d) / len(c) * 100)

# ===============================
# DERIV WS (SEM OTC)
# ===============================
def candles_ws(ativo, count=50):
    try:
        ws = websocket.create_connection(DERIV_WS_URL, timeout=6)
        ws.send(json.dumps({
            "authorize": DERIV_API_KEY
        }))
        ws.recv()

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

    acc = int(stats["green"] / stats["total"] * 100)

    tg(
        f"📊 <b>RESULTADO</b>\n"
        f"{'🟢 GREEN' if win else '🔴 RED'}\n"
        f"Ativo: {res['ativo']}\n"
        f"Assertividade: {acc}%"
    )

    sinal_em_analise.clear()

# ===============================
# RELATÓRIO POR HORA
# ===============================
def relatorio_hora():
    global hora_atual
    while True:
        time.sleep(60)
        agora = datetime.now(BR_TZ).hour
        if agora != hora_atual:
            tg(
                f"⏰ <b>RELATÓRIO DA HORA</b>\n"
                f"Sinais: {sinais_por_hora[hora_atual]}\n"
                f"Green: {stats['green']} | Red: {stats['red']}"
            )
            sinais_por_hora[agora] = 0
            hora_atual = agora

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop_principal():
    global bot_iniciado

    if not bot_iniciado:
        tg("🚀 <b>TROIA-IA-V16 INICIADO</b>\nMercado REAL • M5 • Foco em sinais")
        bot_iniciado = True

    ultimo = {}

    while True:
        try:
            agora = datetime.now(BR_TZ).hour

            if sinais_por_hora[agora] >= MAX_SINAIS_HORA:
                time.sleep(20)
                continue

            for ativo in ATIVOS:
                if sinal_em_analise.is_set():
                    break

                c = candles_ws(ativo)
                if len(c) < 20:
                    continue

                d = direcao_confirmada(c)
                if not d or not candle_ok(c[-1]):
                    continue

                t = tendencia(c)
                if not t or d != t:
                    continue

                if confianca(c[-15:]) < CFG["CONF_MIN"]:
                    continue

                if prob(c, d) < CFG["PROB_MIN"]:
                    continue

                ultimo_t = ultimo.get(ativo, 0)
                if time.time() - ultimo_t < 240:
                    continue

                ultimo[ativo] = time.time()
                sinal_em_analise.set()
                sinais_por_hora[agora] += 1

                tg(
                    f"💥 <b>SINAL</b>\n"
                    f"Ativo: {ativo}\n"
                    f"Direção: {d}\n"
                    f"Hora BR: {datetime.now(BR_TZ).strftime('%H:%M')}\n"
                    f"{sinais_por_hora[agora]}/{MAX_SINAIS_HORA} sinais/h"
                )

                threading.Thread(
                    target=resultado,
                    args=({"ativo":ativo,"dir":d,"tempo":TIMEFRAME+WAIT_BUFFER},),
                    daemon=True
                ).start()

            time.sleep(SCAN_DELAY)

        except Exception as e:
            print("ERRO:", e)
            time.sleep(5)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    threading.Thread(target=loop_principal, daemon=True).start()
    threading.Thread(target=relatorio_hora, daemon=True).start()

    while True:
        print("🟢 TROIA-IA rodando (Mercado REAL)…")
        time.sleep(30)
