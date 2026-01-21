import json, time, requests, csv, os, threading, websocket
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
LOG_FILE = "sinais_log.csv"
ERROR_LOG = "error_log.txt"

sinal_em_analise = threading.Lock()

# ===============================
# ATIVOS
# ===============================
ATIVOS_FOREX = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD",
    "frxUSDCAD","frxUSDCHF","frxNZDUSD","frxEURGBP",
    "frxEURJPY","frxEURCHF","frxEURAUD","frxEURCAD",
    "frxEURNZD","frxGBPJPY","frxGBPCHF","frxGBPAUD",
    "frxGBPCAD","frxGBPNZD","frxAUDJPY","frxAUDNZD",
    "frxAUDCAD","frxAUDCHF","frxCADJPY","frxCADCHF",
    "frxCHFJPY","frxNZDJPY","frxNZDCAD","frxNZDCHF"
]

ATIVOS_OTC = [
    "frxUSDTRY","frxUSDRUB","frxUSDZAR","frxUSDMXN",
    "frxUSDHKD","frxUSDKRW","frxUSDSEK","frxUSDNOK",
    "frxUSDDKK","frxUSDPLN","frxUSDHUF"
]

ATIVOS = ATIVOS_FOREX + ATIVOS_OTC

# ===============================
# LOG DE ERROS
# ===============================
def log_error(msg):
    with open(ERROR_LOG, "a") as f:
        f.write(f"{datetime.utcnow()} - {msg}\n")
    print(msg)

# ===============================
# TELEGRAM
# ===============================
def enviar_sinal(ativo, direcao, confianca, estrategia, entrada="Próxima vela", resultado=None):
    try:
        msg = (
            f"💥 <b>SENTINEL IA – SINAL ENCONTRADO</b>\n"
            f"📊 <b>Ativo:</b> {ativo}\n"
            f"🎯 <b>Direção:</b> {direcao}\n"
            f"🧠 <b>Estratégia:</b> {estrategia}\n"
            f"⏱️ <b>Entrada:</b> {entrada}\n"
            f"🧮 <b>Confiança:</b> {confianca}%\n"
        )
        if resultado:
            msg += f"✅ <b>Resultado:</b> {'🟢 Green' if resultado=='Green' else '🔴 Red'}"

        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except Exception as e:
        log_error(f"Telegram erro: {e}")

# ===============================
# ANÁLISES
# ===============================
def direcao_candle(c): return "CALL" if c["close"] > c["open"] else "PUT"

def calcular_confianca(candles):
    return int(max(
        sum(1 for c in candles if c["close"] > c["open"]),
        sum(1 for c in candles if c["close"] < c["open"])
    ) / len(candles) * 100) if candles else 0

def direcao_confirmada(candles, n=3):
    ult = candles[-n:]
    if all(c["close"] > c["open"] for c in ult): return "CALL"
    if all(c["close"] < c["open"] for c in ult): return "PUT"
    return None

def tendencia_medio_prazo(candles, p=20):
    return "CALL" if candles[-1]["close"] > candles[-p]["close"] else "PUT"

def candle_valido(c, min_pct=0.0003):
    return abs(c["close"] - c["open"]) / c["open"] >= min_pct

def probabilidade_real(candles, d):
    return int(sum(1 for c in candles if direcao_candle(c) == d) / len(candles) * 100)

def proxima_vela_horario():
    now = datetime.now(timezone.utc)
    nxt = now + timedelta(seconds=TIMEFRAME - now.timestamp() % TIMEFRAME)
    return nxt.strftime("%H:%M:%S UTC")

# ===============================
# WEBSOCKET DERIV (ÚNICO E SEGURO)
# ===============================
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"
ws = None
ws_lock = threading.Lock()

def pegar_candles_ws(ativo, count=50):
    global ws
    try:
        with ws_lock:
            if ws is None:
                ws = websocket.create_connection(DERIV_WS_URL, timeout=10)

            ws.send(json.dumps({
                "ticks_history": ativo,
                "style": "candles",
                "granularity": TIMEFRAME,
                "count": count
            }))

            data = json.loads(ws.recv())
            if "candles" in data:
                return data["candles"][-count:]
    except Exception as e:
        log_error(f"WS erro {ativo}: {e}")
        try: ws.close()
        except: pass
        ws = None
    return None

# ===============================
# RESULTADO REAL
# ===============================
def resultado_real(res):
    try:
        time.sleep(res["tempo_espera"])
        candles = pegar_candles_ws(res["ativo"], count=1)
        resultado = "Green" if candles and direcao_candle(candles[-1]) == res["direcao"] else "Red"
        enviar_sinal(res["ativo"], res["direcao"], res["confianca"],
                     "Price Action + Probabilidade Avançada",
                     entrada=f"{res['horario_entrada']} (concluído)",
                     resultado=resultado)
    finally:
        if sinal_em_analise.locked():
            sinal_em_analise.release()

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop_ativos_final():
    enviar_sinal("N/A","N/A",0,"Iniciando Bot Sentinel IA – Produção")
    cooldowns = {a:0 for a in ATIVOS}
    ultimo = {a:None for a in ATIVOS}

    while True:
        for ativo in ATIVOS:
            if time.time() < cooldowns[ativo]: continue

            candles = pegar_candles_ws(ativo)
            if not candles: continue

            direcao = direcao_confirmada(candles)
            if not direcao or not candle_valido(candles[-1]): continue

            confianca = calcular_confianca(candles[-20:])
            if direcao != tendencia_medio_prazo(candles): continue

            min_conf = CONF_MIN + (15 if ativo in ATIVOS_OTC else 0)
            if confianca < min_conf or probabilidade_real(candles, direcao) < PROB_MIN: continue
            if ultimo[ativo] == direcao: continue

            if sinal_em_analise.acquire(False):
                horario = proxima_vela_horario()
                enviar_sinal(ativo, direcao, confianca,
                             "Price Action + Probabilidade Avançada",
                             entrada=f"Agora ({horario})")

                threading.Thread(target=resultado_real, args=({
                    "ativo":ativo,"direcao":direcao,
                    "horario_entrada":horario,
                    "tempo_espera":TIMEFRAME+WAIT_BUFFER,
                    "confianca":confianca
                },)).start()

                cooldowns[ativo] = time.time() + TIMEFRAME
                ultimo[ativo] = direcao

        time.sleep(0.2)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    while True:
        try:
            loop_ativos_final()
        except Exception as e:
            log_error(f"[FATAL] Reiniciando: {e}")
            time.sleep(RECONNECT_DELAY)
