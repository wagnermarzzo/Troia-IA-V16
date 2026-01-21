import json, time, requests, csv, os
from datetime import datetime, timezone, timedelta
import threading

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 300  # 5 minutos
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
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
    print(msg)

# ===============================
# TELEGRAM
# ===============================
def enviar_sinal(ativo, direcao, confianca, estrategia, entrada="Próxima vela", resultado=None):
    try:
        now = datetime.now(timezone.utc).strftime("%H:%M UTC")
        nome_bot = "SENTINEL IA – SINAL ENCONTRADO"
        msg = f"💥 <b>{nome_bot}</b>\n" \
              f"📊 <b>Ativo:</b> {ativo}\n" \
              f"🎯 <b>Direção:</b> {direcao}\n" \
              f"🧠 <b>Estratégia:</b> {estrategia}\n" \
              f"⏱️ <b>Entrada:</b> {entrada}\n" \
              f"🧮 <b>Confiança:</b> {confianca}%\n"
        if resultado:
            cor = "🟢 Green" if resultado=="Green" else "🔴 Red"
            msg += f"✅ <b>Resultado:</b> {cor}"
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except Exception as e:
        log_error(f"Erro ao enviar Telegram: {e}")

# ===============================
# FUNÇÕES DE ANÁLISE
# ===============================
def direcao_candle(candle):
    return "CALL" if candle["close"] > candle["open"] else "PUT"

def calcular_confianca(candles):
    call = sum(1 for c in candles if c["close"] > c["open"])
    put  = sum(1 for c in candles if c["close"] < c["open"])
    total = len(candles)
    return int(max(call, put)/total*100) if total else 0

def direcao_confirmada(candles, n=3):
    ultimos = candles[-n:]
    calls = sum(1 for c in ultimos if c["close"] > c["open"])
    puts  = sum(1 for c in ultimos if c["close"] < c["open"])
    if calls==n: return "CALL"
    if puts==n:  return "PUT"
    return None

def tendencia_medio_prazo(candles, periodo=20):
    if len(candles)<periodo: periodo=len(candles)
    return "CALL" if candles[-1]["close"] > candles[-periodo]["close"] else "PUT"

def candle_valido(candle, min_pct=0.0003):
    return abs(candle["close"]-candle["open"])/candle["open"] >= min_pct

def probabilidade_real(candles, direcao):
    total = len(candles)
    if total==0: return 0
    verdes = sum(1 for c in candles if direcao_candle(c)==direcao)
    return int(verdes/total*100)

def proxima_vela_horario():
    now = datetime.now(timezone.utc)
    next_time = now + timedelta(seconds=TIMEFRAME - now.timestamp() % TIMEFRAME)
    return next_time.strftime("%H:%M:%S UTC")

# ===============================
# PEGAR CANDLES HTTP COM RETRY
# ===============================
def pegar_candles_http(ativo, count=50, max_retry=3):
    url = f"https://api.deriv.com/api/v1/ticks_history?symbol={ativo}&count={count}&granularity={TIMEFRAME}&style=candles"
    retries = 0
    while retries < max_retry:
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            if "candles" in data: 
                return data["candles"][-count:]
            else:
                log_error(f"{ativo} retornou dados inválidos: {data}")
                return None
        except requests.exceptions.RequestException as e:
            retries += 1
            log_error(f"Falha ao pegar candles {ativo}, tentativa {retries}/{max_retry}: {e}")
            time.sleep(RECONNECT_DELAY*retries)
    log_error(f"{ativo} pulado após {max_retry} tentativas")
    return None

# ===============================
# LOG DE SINAIS
# ===============================
def log_sinal(ativo, direcao, confianca, resultado):
    exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["Data","Ativo","Direcao","Confianca","Resultado"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),ativo,direcao,confianca,resultado or "Em análise"])

# ===============================
# RESULTADO REAL
# ===============================
def resultado_real(res):
    try:
        time.sleep(res["tempo_espera"])
        candles = pegar_candles_http(res["ativo"], count=1)
        if not candles:
            resultado = "Erro"
        else:
            direcao_real = direcao_candle(candles[-1])
            resultado = "Green" if direcao_real==res["direcao"] else "Red"

        enviar_sinal(
            res["ativo"], res["direcao"], res["confianca"],
            "Price Action + Suportes/Resistências + Probabilidade Avançada",
            entrada=f"{res['horario_entrada']} (concluído)",
            resultado=resultado
        )
        log_sinal(res["ativo"], res["direcao"], res["confianca"], resultado)
    finally:
        if sinal_em_analise.locked():
            sinal_em_analise.release()

# ===============================
# LOOP PRINCIPAL FINAL
# ===============================
def loop_ativos_final():
    enviar_sinal("N/A","N/A",0,"Iniciando Bot Sentinel IA – Painel Profissional")
    cooldowns = {ativo:0 for ativo in ATIVOS}
    ultimo_sinal = {ativo:None for ativo in ATIVOS}

    while True:
        now_ts = time.time()
        for ativo in ATIVOS:
            if now_ts < cooldowns[ativo]:
                continue

            candles = pegar_candles_http(ativo, count=50)
            if not candles:
                continue

            direcao = direcao_confirmada(candles, n=3)
            if not direcao:
                continue

            if not candle_valido(candles[-1]):
                continue

            confianca = calcular_confianca(candles[-20:])
            tendencia = tendencia_medio_prazo(candles)
            if direcao != tendencia:
                continue

            min_conf = CONF_MIN + (15 if ativo in ATIVOS_OTC else 0)
            if confianca < min_conf:
                continue

            prob_real = probabilidade_real(candles,direcao)
            if prob_real < PROB_MIN:
                continue

            if ultimo_sinal[ativo] == direcao:
                continue

            if sinal_em_analise.acquire(blocking=False):
                horario_entrada = proxima_vela_horario()
                enviar_sinal(
                    ativo,direcao,confianca,
                    "Price Action + Suportes/Resistências + Probabilidade Avançada",
                    entrada=f"Agora ({horario_entrada})"
                )
                log_sinal(ativo,direcao,confianca,None)

                threading.Thread(target=resultado_real,args=({
                    "ativo":ativo,
                    "direcao":direcao,
                    "horario_entrada":horario_entrada,
                    "tempo_espera":TIMEFRAME+WAIT_BUFFER,
                    "confianca":confianca
                },)).start()

                cooldowns[ativo] = now_ts + TIMEFRAME
                ultimo_sinal[ativo] = direcao

        time.sleep(0.1)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    while True:
        try:
            loop_ativos_final()
        except Exception as e:
            log_error(f"[FATAL] Loop principal travou, reiniciando em {RECONNECT_DELAY}s: {e}")
            time.sleep(RECONNECT_DELAY)
