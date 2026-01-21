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
WAIT_BUFFER = 10  # segundos extras para garantir fechamento da vela
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
def enviar_sinal(ativo, direcao, confianca, estrategia, entrada="Próxima vela", motivo=None, resultado=None):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    nome_bot = "SENTINEL IA – SINAL ENCONTRADO"

    msg = f"💥 <b>{nome_bot}</b>\n" \
          f"📊 <b>Ativo:</b> {ativo}\n" \
          f"🎯 <b>Direção:</b> {direcao}\n" \
          f"🧠 <b>Estratégia:</b> {estrategia}\n" \
          f"⏱️ <b>Entrada:</b> {entrada}\n" \
          f"🧮 <b>Confiança:</b> {confianca}%\n"

    if motivo:
        msg += f"📋 <b>Motivo:</b> {motivo}\n"

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
    call = sum(1 for c in candles if c["close"] > c["open"])
    put = sum(1 for c in candles if c["close"] < c["open"])
    total = len(candles)
    maior = max(call, put)
    confianca = int(maior / total * 100) if total > 0 else 0
    return confianca

# ===============================
# PRÓXIMA VELA
# ===============================
def proxima_vela_horario():
    now = datetime.now(timezone.utc)
    remainder = TIMEFRAME - (now.minute*60 + now.second) % TIMEFRAME
    next_time = now + timedelta(seconds=remainder)
    return next_time.strftime("%H:%M:%S UTC")

# ===============================
# PEGAR CANDLES COM RETRY
# ===============================
def pegar_candles(ativo, count=20):
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
            "Price Action + Suportes/Resistências",
            entrada=f"{res['horario_entrada']} (concluído)",
            resultado=resultado
        )
        log_sinal(res["ativo"], res["direcao"], res["confianca"], resultado)
    finally:
        sinal_em_analise.release()

# ===============================
# ANALISA 1 ATIVO POR VEZ
# ===============================
def analisar_ativo(ativo):
    candles = pegar_candles(ativo)
    if not candles:
        return None

    direcao = direcao_candle(candles[-1])
    confianca = calcular_confianca(candles)
    horario_entrada = proxima_vela_horario()

    motivo = "Price Action + Suportes/Resistências"
    if ativo in ATIVOS_OTC:
        motivo += " ⚠ OTC: baixa liquidez"

    if confianca >= CONF_MIN:
        sinal_em_analise.acquire()
        enviar_sinal(
            ativo,
            direcao,
            confianca,
            "Price Action + Suportes/Resistências",
            entrada=f"Agora ({horario_entrada})",
            motivo=motivo
        )
        log_sinal(ativo, direcao, confianca, None)
        threading.Thread(target=resultado_real, args=({
            "ativo": ativo,
            "direcao": direcao,
            "horario_entrada": horario_entrada,
            "tempo_espera": TIMEFRAME + WAIT_BUFFER,
            "confianca": confianca
        },)).start()
        return True
    return None

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop_ativos():
    enviar_sinal("N/A", "N/A", 0, "Iniciando Bot Sentinel IA – Painel Profissional")
    while True:
        for ativo in ATIVOS:
            if not sinal_em_analise.locked():
                analisar_ativo(ativo)
                break  # só analisar 1 ativo por vez
        time.sleep(1)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    loop_ativos()
