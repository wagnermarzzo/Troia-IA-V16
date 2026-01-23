import websocket, json, time, requests
from datetime import datetime, timezone, timedelta

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

# Lista de ativos Forex e OTC
ATIVOS_FOREX = [
    "frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD",
    "frxUSDCAD", "frxUSDCHF", "frxNZDUSD", "frxEURGBP"
]

ATIVOS_OTC = [
    "OTC_US500", "OTC_US30", "OTC_DE30", "OTC_FRA40",
    "OTC_FTI100", "OTC_AUS200", "OTC_JPN225"
]

# Configurações de análise
NUM_CANDLES_ANALISE = 20
TIMEFRAME = 60  # 1 minuto
CONF_MIN = 55
WAIT_AFTER_VELA = 65  # espera 1m05s
ESTRATEGIA = "Análise últimos 20 candles 1M"
RECONNECT_DELAY = 3  # segundos caso WS caia

# Timezone Brasil
BR_TZ = timezone(timedelta(hours=-3))

# ===============================
# TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode":"HTML"}, timeout=5
        )
    except: pass

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
    next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    return next_minute.strftime("%H:%M:%S UTC")

# ===============================
# FUNÇÃO PARA PEGAR CANDLES
# ===============================
def pegar_candles(ativo, count=NUM_CANDLES_ANALISE):
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
            time.sleep(RECONNECT_DELAY)  # reconectar se falhar

# ===============================
# CHECAR HORÁRIO OTC
# ===============================
def otc_ativo():
    # Para teste, sempre ativo; depois pode ajustar para horários reais de OTC
    return True

# ===============================
# ANALISA 1 ATIVO
# ===============================
def analisar_ativo(ativo):
    # Ignora OTC se não estiver ativo
    if ativo in ATIVOS_OTC and not otc_ativo():
        print(f"{ativo} OTC fechado, ignorando")
        return None

    candles = pegar_candles(ativo)
    direcao = direcao_candle(candles[-1])
    conf = calcular_confianca(candles)
    horario_entrada = proxima_vela_horario()

    if conf >= CONF_MIN:
        tg(f"💥 <b>SINAL ENCONTRADO!</b>\n"
           f"📊 <b>Ativo:</b> {ativo}\n"
           f"🎯 <b>Direção:</b> {direcao}\n"
           f"⏱️ <b>Timeframe:</b> 1M\n"
           f"🧠 <b>Estratégia:</b> {ESTRATEGIA}\n"
           f"🚀 <b>Entrada:</b> {horario_entrada}\n"
           f"📈 <b>Confiança:</b> {conf}%")
        return {"ativo": ativo, "direcao": direcao, "horario_entrada": horario_entrada}
    return None

# ===============================
# RESULTADO REAL
# ===============================
def resultado_real(ativo, direcao):
    candles = pegar_candles(ativo, count=1)
    candle = candles[-1]
    direcao_real = direcao_candle(candle)
    if direcao_real == direcao:
        return "💸 Green"
    else:
        return "🧨 Red"

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop_ativos():
    todos_ativos = ATIVOS_FOREX + ATIVOS_OTC
    tg("🤖 Troia V19 PRO FINAL - Painel Profissional iniciado.\nAnalise 1 ativo por vez.")
    while True:
        for ativo in todos_ativos:
            try:
                res = analisar_ativo(ativo)
                if res:
                    time.sleep(WAIT_AFTER_VELA)  # espera fechamento vela
                    resultado = resultado_real(res["ativo"], res["direcao"])
                    tg(f"🧾 <b>RESULTADO SINAL</b>\n"
                       f"📊 <b>Ativo:</b> {res['ativo']}\n"
                       f"🎯 <b>Direção:</b> {res['direcao']}\n"
                       f"⏱️ <b>Entrada realizada:</b> {res['horario_entrada']}\n"
                       f"✅ <b>Resultado:</b> {resultado}")
                else:
                    time.sleep(2)
            except Exception as e:
                tg(f"❌ Erro no ativo {ativo}: {e}")
                time.sleep(RECONNECT_DELAY)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    loop_ativos()
