import websocket, json, time, requests
from datetime import datetime, timezone, timedelta
from threading import Thread
import os

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

ATIVOS_FOREX = [
    "frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD",
    "frxUSDCAD", "frxUSDCHF", "frxNZDUSD", "frxEURGBP"
]

ATIVOS_OTC = [
    "OTC_US500", "OTC_US30", "OTC_DE30", "OTC_FRA40",
    "OTC_FTI100", "OTC_AUS200", "OTC_JPN225"
]

NUM_CANDLES_ANALISE = 20
TIMEFRAME = 60  # 1 minuto
CONF_MIN = 55
WAIT_AFTER_VELA = 65  # espera 1m05s
ESTRATEGIA = "Análise últimos 20 candles 1M"
RECONNECT_DELAY = 3  # segundos caso WS caia
BR_TZ = timezone(timedelta(hours=-3))

HIST_FILE = "historico_sinais.json"

# ===============================
# TELEGRAM
# ===============================
def tg_send(msg):
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5
        ).json()
        time.sleep(1)
        if resp.get("ok"):
            return resp["result"]["message_id"]
    except Exception as e:
        print(f"❌ Erro enviar Telegram: {e}")
    return None

def tg_edit(message_id, msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
            data={"chat_id": TELEGRAM_CHAT_ID, "message_id": message_id, "text": msg, "parse_mode": "HTML"}, timeout=5
        )
    except Exception as e:
        print(f"❌ Erro editar Telegram: {e}")

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
    return int(maior / total * 100)

# ===============================
# PEGAR CANDLES
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
            else:
                print(f"⚠️ Dados incompletos para {ativo}, tentando novamente")
                time.sleep(RECONNECT_DELAY)
        except Exception as e:
            print(f"❌ Erro pegar_candles({ativo}): {e}")
            time.sleep(RECONNECT_DELAY)

# ===============================
# CHECAR OTC
# ===============================
def otc_ativo():
    return True  # ajustar depois se necessário

# ===============================
# REGISTRAR HISTÓRICO
# ===============================
def registrar_historico(ativo, direcao, conf, horario, resultado):
    historico = []
    if os.path.exists(HIST_FILE):
        with open(HIST_FILE, "r") as f:
            try:
                historico = json.load(f)
            except:
                historico = []

    historico.append({
        "ativo": ativo,
        "direcao": direcao,
        "conf": conf,
        "horario_entrada": horario,
        "resultado": resultado,
        "timestamp": datetime.now(BR_TZ).strftime("%Y-%m-%d %H:%M:%S")
    })

    with open(HIST_FILE, "w") as f:
        json.dump(historico, f, indent=4)

# ===============================
# ANALISAR E ENVIAR SINAL COM RESULTADO
# ===============================
def analisar_e_enviar(ativo):
    if ativo in ATIVOS_OTC and not otc_ativo():
        print(f"{ativo} OTC fechado, ignorando")
        return

    candles = pegar_candles(ativo)
    direcao = direcao_candle(candles[-1])
    conf = calcular_confianca(candles)
    horario_entrada = (datetime.now(BR_TZ) + timedelta(seconds=5)).strftime("%H:%M:%S")

    if conf >= CONF_MIN:
        msg = (f"💥 <b>SINAL ENCONTRADO!</b>\n"
               f"📊 <b>Ativo:</b> {ativo}\n"
               f"🎯 <b>Direção:</b> {direcao}\n"
               f"⏱️ <b>Entrada:</b> {horario_entrada}\n"
               f"🧠 <b>Estratégia:</b> {ESTRATEGIA}\n"
               f"📈 <b>Confiança:</b> {conf}%\n\n"
               f"⌛ Aguardando resultado...")
        message_id = tg_send(msg)

        time.sleep(WAIT_AFTER_VELA)

        candle_final = pegar_candles(ativo, count=1)[-1]
        resultado = "💸 Green" if direcao_candle(candle_final) == direcao else "🧨 Red"

        # Edita mensagem com resultado
        msg_edit = msg.replace("⌛ Aguardando resultado...", f"✅ Resultado: {resultado}")
        tg_edit(message_id, msg_edit)

        # Registra histórico
        registrar_historico(ativo, direcao, conf, horario_entrada, resultado)

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop_ativos():
    todos_ativos = ATIVOS_FOREX + ATIVOS_OTC
    tg_send("🤖 Troia V19 PRO FINAL - Painel Profissional iniciado.\nAnalise múltiplos ativos em paralelo.")

    while True:
        threads = []
        for ativo in todos_ativos:
            t = Thread(target=analisar_e_enviar, args=(ativo,))
            t.start()
            threads.append(t)
            time.sleep(1)

        for t in threads:
            t.join()

if __name__ == "__main__":
    loop_ativos()
