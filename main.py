import websocket, json, time, requests, csv, os
from datetime import datetime, timezone
import threading
import traceback

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2HTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 300  # 5 minutos
WAIT_BUFFER = 10
RECONNECT_MAX = 5
RECONNECT_DELAY = 3

CONF_DEFAULT = 55
CONF_MIN = 50
CONF_MAX = 70

LOG_FILE = "sinais_log.csv"
HISTORICO_RESULTADOS = []  # Green/Red
TOTAL_SINAIS = 0

# ===============================
# ATIVOS
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
# LOCK GLOBAL
# ===============================
sinal_em_analise = threading.Lock()

# ===============================
# FUNÇÕES TELEGRAM
# ===============================
def enviar_ou_editar_sinal(message_id=None, ativo=None, direcao=None, confianca=0,
                           estrategia=None, entrada="Agora", motivo=None, resultado=None,
                           horario_fechamento=None, dashboard=False):
    try:
        nome_bot = "SENTINEL IA – SINAL ENCONTRADO"
        msg = f"💥 <b>{nome_bot}</b>\n"
        if dashboard:
            greens = HISTORICO_RESULTADOS.count("Green")
            reds = HISTORICO_RESULTADOS.count("Red")
            total = len(HISTORICO_RESULTADOS)
            taxa = int((greens/total)*100) if total > 0 else 0
            msg += f"📊 <b>Mini Dashboard</b>\n" \
                   f"🧮 Total sinais: {TOTAL_SINAIS}\n" \
                   f"🟢 Green: {greens} | 🔴 Red: {reds}\n" \
                   f"🎯 Taxa de acerto: {taxa}%\n"
            if ativo:
                msg += f"📌 Último sinal: {ativo} ({direcao}, {confianca}%)\n"
        else:
            msg += f"📊 <b>Ativo:</b> {ativo}\n" \
                   f"🎯 <b>Direção:</b> {direcao}\n" \
                   f"🧠 <b>Estratégia:</b> {estrategia}\n" \
                   f"⏱️ <b>Entrada:</b> {entrada}\n" \
                   f"🧮 <b>Confiança:</b> {confianca}%\n"
            if motivo:
                msg += f"📋 <b>Motivo:</b> {motivo}\n"
            if resultado:
                cor = "🟢 Green" if resultado == "Green" else "🔴 Red"
                if horario_fechamento:
                    msg += f"⏱️ <b>Fechamento da vela:</b> {horario_fechamento}\n"
                msg += f"✅ <b>Resultado:</b> {cor}"

        if message_id:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
                data={"chat_id": TELEGRAM_CHAT_ID, "message_id": message_id, "text": msg, "parse_mode": "HTML"},
                timeout=5
            )
        else:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=5
            )
            return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print("Erro Telegram:", e)

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
    return int(maior / total * 100) if total > 0 else 0

def atualizar_conf_dinamica():
    if len(HISTORICO_RESULTADOS) < 5:
        return CONF_DEFAULT
    greens = HISTORICO_RESULTADOS.count("Green")
    taxa_acerto = greens / len(HISTORICO_RESULTADOS)
    if taxa_acerto > 0.7:
        return min(CONF_MAX, CONF_DEFAULT + 5)
    elif taxa_acerto < 0.4:
        return max(CONF_MIN, CONF_DEFAULT - 5)
    else:
        return CONF_DEFAULT

# ===============================
# PEGAR CANDLES COM RETRY
# ===============================
def pegar_candles(ativo, count=20):
    for tentativa in range(1, RECONNECT_MAX + 1):
        try:
            ws = websocket.create_connection("wss://ws.derivws.com/websockets/v3?app_id=1089", timeout=20)
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
        except Exception as e:
            print(f"Tentativa {tentativa} falhou para {ativo}: {e}")
            time.sleep(RECONNECT_DELAY * tentativa)
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
def resultado_real(ativo, direcao, message_id, confianca):
    global TOTAL_SINAIS
    try:
        time.sleep(TIMEFRAME + WAIT_BUFFER)
        candles = pegar_candles(ativo, count=1)
        if not candles:
            resultado = "Erro"
            horario_fechamento = None
        else:
            candle_fechamento = candles[-1]
            direcao_real = direcao_candle(candle_fechamento)
            resultado = "Green" if direcao_real == direcao else "Red"
            horario_fechamento = datetime.fromtimestamp(candle_fechamento["epoch"], tz=timezone.utc).strftime("%H:%M:%S UTC")

        if resultado in ["Green", "Red"]:
            HISTORICO_RESULTADOS.append(resultado)
            if len(HISTORICO_RESULTADOS) > 20:
                HISTORICO_RESULTADOS.pop(0)
        enviar_ou_editar_sinal(
            message_id=message_id,
            ativo=ativo,
            direcao=direcao,
            resultado=resultado,
            horario_fechamento=horario_fechamento,
            confianca=confianca
        )
        log_sinal(ativo, direcao, confianca, resultado)
        TOTAL_SINAIS += 1
        # Atualiza mini-dashboard
        enviar_ou_editar_sinal(dashboard=True, ativo=ativo, direcao=direcao, confianca=confianca)
    finally:
        sinal_em_analise.release()

# ===============================
# ANALISA 1 ATIVO
# ===============================
def analisar_ativo(ativo):
    candles = pegar_candles(ativo)
    if not candles:
        print(f"Não foi possível pegar candles para {ativo}. Pulando...")
        return False

    direcao = direcao_candle(candles[-1])
    conf_atual = calcular_confianca(candles)
    conf_min = atualizar_conf_dinamica()
    horario_entrada = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    
    motivo = "Price Action + Suportes/Resistências + Tendência detectada"
    if ativo in ATIVOS_OTC:
        motivo += " ⚠ OTC: baixa liquidez"

    if conf_atual >= conf_min:
        sinal_em_analise.acquire()
        msg_id = enviar_ou_editar_sinal(
            ativo=ativo,
            direcao=direcao,
            confianca=conf_atual,
            estrategia="Price Action + Suportes/Resistências",
            entrada=horario_entrada,
            motivo=motivo
        )
        log_sinal(ativo, direcao, conf_atual, None)
        threading.Thread(target=resultado_real, args=(ativo, direcao, msg_id, conf_atual)).start()
        return True
    return False

# ===============================
# LOOP PRINCIPAL COM AUTO-RESTART
# ===============================
def loop_ativos():
    while True:
        try:
            # Envia dashboard inicial
            enviar_ou_editar_sinal(dashboard=True)
            for ativo in ATIVOS:
                sinal_em_analise.acquire()
                sinal_em_analise.release()
                sucesso = analisar_ativo(ativo)
                if sucesso:
                    # Aguarda o fechamento do ativo atual antes de continuar
                    while sinal_em_analise.locked():
                        time.sleep(1)
                time.sleep(1)
        except Exception as e:
            print("Erro no loop principal:", e)
            print(traceback.format_exc())
            time.sleep(5)
            print("Tentando reiniciar loop...")

# ===============================
# START
# ===============================
if __name__ == "__main__":
    loop_ativos()
