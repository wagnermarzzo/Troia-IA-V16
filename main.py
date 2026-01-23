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

ATIVOS_FOREX = ["frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD","frxUSDCHF","frxNZDUSD","frxEURGBP"]
ATIVOS_OTC = ["OTC_US500","OTC_US30","OTC_DE30","OTC_FRA40","OTC_FTI100","OTC_AUS200","OTC_JPN225"]

NUM_CANDLES_ANALISE = 20
TIMEFRAME = 60  # segundos
CONF_MIN = 55
WAIT_BUFFER = 5
ESTRATEGIA = "Análise últimos 20 candles 1M"
BR_TZ = timezone(timedelta(hours=-3))
HIST_FILE = "historico_sinais.json"
RECONNECT_DELAY = 5
HEARTBEAT_INTERVAL = 30  # segundos

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
# PEGAR CANDLES COM RETRY
# ===============================
def pegar_candles_ws(ws, ativo, count=NUM_CANDLES_ANALISE, max_retries=5):
    for tentativa in range(max_retries):
        try:
            end_timestamp = int(time.time())
            ws.send(json.dumps({
                "ticks_history": ativo,
                "style": "candles",
                "granularity": TIMEFRAME,
                "count": count,
                "end": end_timestamp
            }))
            data = json.loads(ws.recv())
            if "candles" in data:
                return data["candles"][-count:]
            else:
                print(f"⚠️ Dados incompletos para {ativo}, tentativa {tentativa+1}")
                time.sleep(2 ** tentativa)
        except Exception as e:
            wait = 2 ** tentativa
            print(f"❌ Erro pegar_candles({ativo}): {e}, tentando novamente em {wait}s")
            time.sleep(wait)
    print(f"⚠️ Falha ao pegar candles de {ativo} após {max_retries} tentativas")
    return None

# ===============================
# HEARTBEAT PARA WEBSOCKET
# ===============================
def manter_conexao_viva(ws):
    while True:
        try:
            ws.send(json.dumps({"ping": 1}))
        except Exception as e:
            print(f"❌ Erro heartbeat WebSocket: {e}")
            break
        time.sleep(HEARTBEAT_INTERVAL)

# ===============================
# CHECAR OTC
# ===============================
def otc_ativo():
    return True  # Placeholder

# ===============================
# HISTÓRICO
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
# LOOP POR ATIVO (THREAD)
# ===============================
def loop_ativo(ativo):
    try:
        ws = websocket.create_connection(
            "wss://ws.derivws.com/websockets/v3?app_id=1089",
            timeout=20
        )
        ws.send(json.dumps({"authorize": DERIV_API_KEY}))
    except Exception as e:
        print(f"❌ Falha ao iniciar WebSocket para {ativo}: {e}")
        return

    # Inicia heartbeat em thread separada
    Thread(target=manter_conexao_viva, args=(ws,), daemon=True).start()

    while True:
        if ativo in ATIVOS_OTC and not otc_ativo():
            time.sleep(5)
            continue

        candles = pegar_candles_ws(ws, ativo)
        if not candles:
            time.sleep(5)
            continue

        direcao = direcao_candle(candles[-1])
        conf = calcular_confianca(candles)
        horario_entrada = datetime.now(BR_TZ).strftime("%H:%M:%S")

        if conf >= CONF_MIN:
            msg = (f"💥 <b>SINAL PARA PRÓXIMA VELA!</b>\n"
                   f"📊 <b>Ativo:</b> {ativo}\n"
                   f"🎯 <b>Direção:</b> {direcao}\n"
                   f"⏱️ <b>Entrada:</b> próxima vela\n"
                   f"🧠 <b>Estratégia:</b> {ESTRATEGIA}\n"
                   f"📈 <b>Confiança:</b> {conf}%\n\n"
                   f"⌛ Aguardando fechamento da próxima vela...")
            message_id = tg_send(msg)

            time.sleep(TIMEFRAME + WAIT_BUFFER)

            candle_proxima = pegar_candles_ws(ws, ativo, count=1)
            if candle_proxima:
                candle_proxima = candle_proxima[-1]
                resultado = "💸 Green" if direcao_candle(candle_proxima) == direcao else "🧨 Red"
            else:
                resultado = "⚠️ Sem dados"

            msg_edit = msg.replace("⌛ Aguardando fechamento da próxima vela...", f"✅ Resultado: {resultado}")
            tg_edit(message_id, msg_edit)

            registrar_historico(ativo, direcao, conf, horario_entrada, resultado)

        time.sleep(1)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    todos_ativos = ATIVOS_FOREX + ATIVOS_OTC
    tg_send("🤖 Troia V19 PRO FINAL iniciado - Analisando todos os ativos continuamente (sinal para próxima vela).")

    for i, ativo in enumerate(todos_ativos):
        Thread(target=loop_ativo, args=(ativo,), daemon=True).start()
        time.sleep(1)  # evita iniciar todas threads ao mesmo tempo

    while True:
        time.sleep(10)
