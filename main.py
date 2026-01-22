import json, time, requests, threading, websocket
from collections import deque, defaultdict
from datetime import datetime, timezone, timedelta

# ===============================
# CONFIGURAÇÃO
# ===============================
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 300
WAIT_BUFFER = 10
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

SCAN_DELAY = 3
MAX_SINAIS_HORA = 5

# UTC-3 (Brasil)
BR_TZ = timezone(timedelta(hours=-3))

sinal_em_analise = threading.Event()
bot_iniciado = False

# ===============================
# MODOS
# ===============================
MODO = "AGRESSIVO"

MODOS = {
    "AGRESSIVO": {"CONF_MIN":46,"PROB_MIN":52,"CONFIRM":1,"TEND":6,"MINPCT":0.00008},
    "MODERADO":  {"CONF_MIN":50,"PROB_MIN":55,"CONFIRM":2,"TEND":10,"MINPCT":0.00012},
    "CONSERVADOR":{"CONF_MIN":55,"PROB_MIN":60,"CONFIRM":3,"TEND":14,"MINPCT":0.00018}
}

CFG = MODOS[MODO]

# ===============================
# ATIVOS
# ===============================
ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD",
    "frxUSDCHF","frxNZDUSD","frxEURJPY","frxGBPJPY",
    "R_10","R_25","R_50","R_75","R_100"
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
    if r >= 4: novo = "CONSERVADOR"
    elif g >= 4: novo = "AGRESSIVO"

    if novo != MODO:
        MODO = novo
        CFG = MODOS[MODO]
        tg(
            f"🧠 <b>IA ADAPTATIVA</b>\n"
            f"Modo: <b>{MODO}</b>\n"
            f"Últimos 5: {''.join(historico_resultados)}"
        )

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
    return int(max(
        sum(1 for x in c if direcao(x) == "CALL"),
        sum(1 for x in c if direcao(x) == "PUT")
    ) / len(c) * 100)

def tendencia(c):
    if len(c) < CFG["TEND"]:
        return None
    return "CALL" if c[-1]["close"] > c[-CFG["TEND"]]["close"] else "PUT"

def candle_ok(c):
    return abs(c["close"] - c["open"]) / c["open"] >= CFG["MINPCT"]

def prob(c, d):
    return int(sum(1 for x in c if direcao(x) == d) / len(c) * 100)

# ===============================
# DERIV WS
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
        f"{'🟢 GREEN' if win else '🔴 RED'}\n"
        f"Ativo: {res['ativo']}\n"
        f"🎯 Assertividade: {acc}%\n"
        f"Modo: {MODO}"
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
                f"Green: {stats['green']} | Red: {stats['red']}\n"
                f"Modo: {MODO}"
            )
            sinais_por_hora[agora] = 0
            hora_atual = agora

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop_principal():
    global bot_iniciado

    if not bot_iniciado:
        tg("🚀 <b>TROIA-IA-V16 INICIADO</b>\n5 sinais/h • M5 • OTC ATIVO")
        bot_iniciado = True

    ultimo = {}

    while True:
        try:
            agora = datetime.now(BR_TZ).hour

            if sinais_por_hora[agora] >= MAX_SINAIS_HORA:
                time.sleep(30)
                continue

            for ativo in ATIVOS:
                if sinal_em_analise.is_set():
                    break

                c = candles_ws(ativo)
                if len(c) < 30:
                    continue

                d = direcao_confirmada(c)
                if not d or not candle_ok(c[-1]):
                    continue

                t = tendencia(c)
                if not t or d != t:
                    continue

                if confianca(c[-20:]) < CFG["CONF_MIN"]:
                    continue

                if prob(c, d) < CFG["PROB_MIN"]:
                    continue

                ultimo_t = ultimo.get(f"{ativo}_t", 0)
                if time.time() - ultimo_t < 600:
                    continue

                ultimo[f"{ativo}_t"] = time.time()
                sinal_em_analise.set()
                sinais_por_hora[agora] += 1

                tg(
                    f"💥 <b>SINAL</b>\n"
                    f"Ativo: {ativo}\n"
                    f"Direção: {d}\n"
                    f"Hora BR: {datetime.now(BR_TZ).strftime('%H:%M')}\n"
                    f"Sinais/h: {sinais_por_hora[agora]}/{MAX_SINAIS_HORA}"
                )

                threading.Thread(
                    target=resultado,
                    args=({"ativo":ativo,"dir":d,"tempo":TIMEFRAME+WAIT_BUFFER},),
                    daemon=True
                ).start()

            time.sleep(SCAN_DELAY)

        except Exception as e:
            print("ERRO LOOP:", e)
            time.sleep(10)

# ===============================
# KEEP ALIVE
# ===============================
def keep_alive():
    while True:
        print("🟢 Bot rodando...")
        time.sleep(30)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    threading.Thread(target=loop_principal, daemon=True).start()
    threading.Thread(target=relatorio_hora, daemon=True).start()
    keep_alive()
