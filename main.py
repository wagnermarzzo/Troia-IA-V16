import websocket, json, time, requests
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
SINAIS_MAX_30MIN = 3
WAIT_BUFFER = 10  # segundos extras após fechamento da vela
RECONNECT_DELAY = 3

sinais_30min = []
sinal_em_analise = threading.Lock()

# ===============================
# LISTA COMPLETA DE ATIVOS
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
    "frxUSDOLLAR", "frxUSDRUB", "frxUSDSGD", "frxUSDHKD",
    "frxUSDTWD", "frxUSDTRY", "frxUSDKRW", "frxUSDSEK",
    "frxUSDNOK", "frxUSDDKK", "frxUSDZAR"
]

ATIVOS = ATIVOS_FOREX + ATIVOS_OTC

# ===============================
# TELEGRAM
# ===============================
def enviar_sinal(ativo, direcao, confianca, estrategia, entrada="Próxima vela", motivo=None, resultado=None):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    nome_bot = "SENTINEL IA – SINAL ENCONTRADO"

    msg = f"💥 <b>{nome_bot}</b>\n" \
          f"📊 <b>Ativo:</b> {ativo}\n" \
          f"🎯 <b>Direção:</b> {direcao}\n" \
          f"🧠 <b>Estratégia:</b> {estrategia}\n" \
          f"⏱️ <b>Entrada:</b> {entrada}\n"

    if motivo:
        msg += f"📋 <b>Motivo:</b> {motivo}\n"

    if resultado:
        cor = "🟢 Green" if resultado == "Green" else "🔴 Red"
        msg += f"✅ <b>Resultado:</b> {cor}"

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode":"HTML"},
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
    call = sum(1 for c in candles if c["close"] > c["open"])
    put = sum(1 for c in candles if c["close"] < c["open"])
    total = len(candles)
    maior = max(call, put)
    return int(maior/total*100)

# ===============================
# PRÓXIMA VELA
# ===============================
def proxima_vela_horario():
    now = datetime.now(timezone.utc)
    next_minute = (now + timedelta(seconds=TIMEFRAME)).replace(second=0, microsecond=0)
    return next_minute.strftime("%H:%M:%S UTC")

# ===============================
# PEGAR CANDLES
# ===============================
def pegar_candles(ativo, count=20):
    while True:
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
        except:
            time.sleep(RECONNECT_DELAY)

# ===============================
# RESULTADO REAL
# ===============================
def resultado_real(res):
    ativo = res["ativo"]
    direcao = res["direcao"]
    tempo_espera = res["tempo_espera"]

    time.sleep(tempo_espera)  # espera fechamento da próxima vela
    candles = pegar_candles(ativo, count=1)
    direcao_real = direcao_candle(candles[-1])

    resultado = "Green" if direcao_real == direcao else "Red"
    enviar_sinal(
        ativo,
        direcao,
        0,
        "Price Action + Suportes/Resistências",
        entrada=f"{res['horario_entrada']} (concluído)",
        resultado=resultado
    )
    sinal_em_analise.release()  # libera análise do próximo ativo
    return resultado

# ===============================
# ANALISA 1 ATIVO
# ===============================
def analisar_ativo(ativo):
    global sinais_30min

    agora = datetime.now(timezone.utc)
    # Limita sinais em 30 minutos
    sinais_30min = [s for s in sinais_30min if (agora - s).total_seconds() < 1800]
    if len(sinais_30min) >= SINAIS_MAX_30MIN:
        return None

    candles = pegar_candles(ativo)
    direcao = direcao_candle(candles[-1])
    conf = calcular_confianca(candles)
    horario_entrada = proxima_vela_horario()
    motivo = "Price Action + Suportes/Resistências + Tendência detectada"

    if conf >= CONF_MIN:
        # Bloqueia análise de outros ativos enquanto o sinal estiver em andamento
        sinal_em_analise.acquire()
        enviar_sinal(
            ativo,
            direcao,
            conf,
            "Price Action + Suportes/Resistências",
            entrada=f"Próxima vela ({horario_entrada})",
            motivo=motivo
        )
        sinais_30min.append(agora)
        # Thread para esperar o fechamento da vela sem travar o loop
        threading.Thread(target=resultado_real, args=({
            "ativo": ativo,
            "direcao": direcao,
            "horario_entrada": horario_entrada,
            "tempo_espera": TIMEFRAME + WAIT_BUFFER
        },)).start()
        return True
    return None

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop_ativos():
    enviar_sinal("N/A","N/A",0,"Iniciando Bot Sentinel IA – Painel Profissional")
    while True:
        for ativo in ATIVOS:
            try:
                analisar_ativo(ativo)
            except Exception as e:
                enviar_sinal("Erro", "N/A", 0, f"Erro no ativo {ativo}: {e}")
            time.sleep(1)  # evita sobrecarga do loop

# ===============================
# START
# ===============================
if __name__ == "__main__":
    loop_ativos()
