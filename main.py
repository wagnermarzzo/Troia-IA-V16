import websocket, json, time, requests, csv, os
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
WAIT_BUFFER = 10  # segundos extras
RECONNECT_DELAY = 3
LOG_FILE = "sinais_log.csv"
sinal_em_analise = threading.Lock()

# ===============================
# ATIVOS (FOREX + OTC)
# ===============================
ATIVOS_FOREX = [
    "frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD",
    "frxUSDCAD", "frxUSDCHF", "frxNZDUSD", "frxEURGBP",
    "frxEURJPY", "frxEURCHF", "frxEURAUD", "frxEURCAD",
    "frxEURNZD", "frxGBPJPY", "frxGBPCHF", "frxGBPAUD",
    "frxGBPCAD", "frxGBPNZD", "frxAUDJPY", "frxAUDNZD",
    "frxAUDCAD", "frxAUDCHF", "frxCADJPY", "frxCADCHF",
    "frxCHFJPY", "frxNZDJPY", "frxNZDCAD", "frxNZDCHF"
]

ATIVOS_OTC = [
    "frxUSDTRY", "frxUSDRUB", "frxUSDZAR", "frxUSDMXN",
    "frxUSDHKD", "frxUSDKRW", "frxUSDSEK", "frxUSDNOK",
    "frxUSDDKK", "frxUSDPLN", "frxUSDHUF"
]

ATIVOS = ATIVOS_FOREX + ATIVOS_OTC

# ===============================
# TELEGRAM
# ===============================
def enviar_sinal(ativo, direcao, confianca, estrategia, entrada="Próxima vela", resultado=None):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    nome_bot = "SENTINEL IA – SINAL ENCONTRADO"

    msg = f"💥 <b>{nome_bot}</b>\n" \
          f"📊 <b>Ativo:</b> {ativo}\n" \
          f"🎯 <b>Direção:</b> {direcao}\n" \
          f"🧠 <b>Estratégia:</b> {estrategia}\n" \
          f"⏱️ <b>Entrada:</b> {entrada}\n" \
          f"🧮 <b>Confiança:</b> {confianca}%\n"

    if resultado:
        cor = "🟢 Green" if resultado == "Green" else "🔴 Red"
        msg += f"✅ <b>Resultado:</b> {cor}"

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except Exception as e:
        print("Erro ao enviar Telegram:", e)

# ===============================
# DIREÇÃO E CONFIANÇA
# ===============================
def direcao_candle(candle):
    return "CALL" if candle["close"] > candle["open"] else "PUT"

def calcular_confianca(candles):
    """Calcula confiança real baseada em histórico de 20 candles."""
    call = sum(1 for c in candles if c["close"] > c["open"])
    put = sum(1 for c in candles if c["close"] < c["open"])
    total = len(candles)
    maior = max(call, put)
    confianca = int(maior / total * 100) if total > 0 else 0
    return confianca

# ===============================
# CONFIRMAÇÃO DE CANDLES
# ===============================
def direcao_confirmada(candles, n=3):
    ultimos = candles[-n:]
    calls = sum(1 for c in ultimos if c["close"] > c["open"])
    puts = sum(1 for c in ultimos if c["close"] < c["open"])
    if calls == n:
        return "CALL"
    elif puts == n:
        return "PUT"
    else:
        return None

# ===============================
# TENDÊNCIA DE MÉDIO PRAZO
# ===============================
def tendencia_medio_prazo(candles, periodo=20):
    if len(candles) < periodo:
        periodo = len(candles)
    fechamento_inicio = candles[-periodo]["close"]
    fechamento_fim = candles[-1]["close"]
    return "CALL" if fechamento_fim > fechamento_inicio else "PUT"

# ===============================
# FILTRO DE VOLATILIDADE
# ===============================
def candle_valido(candle, min_pct=0.0003):
    diff = abs(candle["close"] - candle["open"])
    return diff / candle["open"] >= min_pct

# ===============================
# SUPORTE/RESISTÊNCIA SIMPLES
# ===============================
def suporte_resistencia(candles, periodo=50):
    highs = [c["high"] for c in candles[-periodo:]]
    lows = [c["low"] for c in candles[-periodo:]]
    resistencia = max(highs)
    suporte = min(lows)
    return suporte, resistencia

# ===============================
# PRÓXIMA VELA
# ===============================
def proxima_vela_horario():
    now = datetime.now(timezone.utc)
    next_time = now + timedelta(seconds=TIMEFRAME - now.timestamp() % TIMEFRAME)
    return next_time.strftime("%H:%M:%S UTC")

# ===============================
# PEGAR CANDLES COM RETRY
# ===============================
def pegar_candles(ativo, count=50):
    tentativas = 0
    while tentativas < 5:
        try:
            ws = websocket.create_connection("wss://ws.derivws.com/websockets/v3?app_id=1089", timeout=10)
            ws.send(json.dumps({"authorize": DERIV_API_KEY}))
            end_timestamp = int(time.time())
            ws.send(json.dumps({
                "ticks_history": ativo,
                "style": "candles",
                "granularity": TIMEFRAME,
                "count": count,
                "end": end_timestamp
            }))
            data = json.loads(ws.recv())
            ws.close()
            if "candles" in data:
                return data["candles"][-count:]
        except Exception:
            tentativas += 1
            time.sleep(RECONNECT_DELAY)
    return []

# ===============================
# LOG DE SINAIS
# ===============================
def log_sinal(ativo, direcao, confianca, resultado):
    exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["Data", "Ativo", "Direcao", "Confianca", "Resultado"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ativo, direcao, confianca, resultado or "Em análise"])

# ===============================
# RESULTADO REAL
# ===============================
def resultado_real(res):
    try:
        time.sleep(res["tempo_espera"])
        candles = pegar_candles(res["ativo"], count=1)
        if not candles:
            resultado = "Erro"
        else:
            direcao_real = direcao_candle(candles[-1])
            resultado = "Green" if direcao_real == res["direcao"] else "Red"

        enviar_sinal(
            res["ativo"],
            res["direcao"],
            res["confianca"],
            "Price Action + Suportes/Resistências + Probabilidade Avançada",
            entrada=f"{res['horario_entrada']} (concluído)",
            resultado=resultado
        )
        log_sinal(res["ativo"], res["direcao"], res["confianca"], resultado)
    finally:
        if sinal_em_analise.locked():
            sinal_em_analise.release()

# ===============================
# LOOP PRINCIPAL AVANÇADO COM PROBABILIDADE
# ===============================
def loop_ativos_probabilidade():
    enviar_sinal("N/A", "N/A", 0, "Iniciando Bot Sentinel IA – Painel Profissional")
    cooldowns = {ativo: 0 for ativo in ATIVOS}
    ultimo_sinal = {ativo: None for ativo in ATIVOS}

    while True:
        now_ts = time.time()
        for ativo in ATIVOS:
            if now_ts < cooldowns[ativo]:
                continue

            candles = pegar_candles(ativo, count=50)
            if not candles:
                continue

            # FILTROS AVANÇADOS
            direcao = direcao_confirmada(candles, n=3)
            if not direcao:
                continue

            if not candle_valido(candles[-1]):
                continue

            confianca = calcular_confianca(candles[-20:])
            tendencia = tendencia_medio_prazo(candles)
            if direcao != tendencia:
                continue

            min_conf = CONF_MIN
            if ativo in ATIVOS_OTC:
                min_conf += 15
            if confianca < min_conf:
                continue

            if ultimo_sinal[ativo] == direcao:
                continue

            # SUPORTE/RESISTÊNCIA (para cálculo interno, sem enviar)
            suporte, resistencia = suporte_resistencia(candles)

            if sinal_em_analise.acquire(blocking=False):
                horario_entrada = proxima_vela_horario()
                enviar_sinal(
                    ativo,
                    direcao,
                    confianca,
                    "Price Action + Suportes/Resistências + Probabilidade Avançada",
                    entrada=f"Agora ({horario_entrada})"
                )
                log_sinal(ativo, direcao, confianca, None)

                threading.Thread(target=resultado_real, args=({
                    "ativo": ativo,
                    "direcao": direcao,
                    "horario_entrada": horario_entrada,
                    "tempo_espera": TIMEFRAME + WAIT_BUFFER,
                    "confianca": confianca
                },)).start()

                cooldowns[ativo] = now_ts + TIMEFRAME
                ultimo_sinal[ativo] = direcao

        time.sleep(0.1)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    loop_ativos_probabilidade()
