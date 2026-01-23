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
TIMEFRAME = 60
CONF_MIN = 55
WAIT_BUFFER = 5
ESTRATEGIA = "Análise últimos 20 candles 1M"
BR_TZ = timezone(timedelta(hours=-3))
HIST_FILE = "historico_sinais.json"
HEARTBEAT_INTERVAL = 30
RETRY_LIMIT = 5

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
    return int(max(call, put) / total * 100) if total else 0

# ===============================
# WEBSOCKET
# ===============================
def criar_ws():
    for i in range(RETRY_LIMIT):
        try:
            ws = websocket.create_connection(
                "wss://ws.derivws.com/websockets/v3?app_id=1089",
                timeout=10
            )
            ws.send(json.dumps({"authorize": DERIV_API_KEY}))
            return ws
        except Exception as e:
            wait = 2 ** i
            print(f"❌ Erro conectar WS ({i+1}/{RETRY_LIMIT}): {e}, tentando em {wait}s")
            time.sleep(wait)
    return None

def manter_conexao_viva(ws):
    while True:
        try:
            ws.send(json.dumps({"ping": 1}))
        except Exception as e:
            print(f"❌ Erro heartbeat WS: {e}")
            break
        time.sleep(HEARTBEAT_INTERVAL)

# ===============================
# CANDLES
# ===============================
def pegar_candles_ws(ws, ativo, count=NUM_CANDLES_ANALISE):
    for tentativa in range(RETRY_LIMIT):
        try:
            ws.send(json.dumps({
                "ticks_history": ativo,
                "style": "candles",
                "granularity": TIMEFRAME,
                "count": count,
                "end": int(time.time())
            }))
            resp = json.loads(ws.recv())
            if "candles" in resp:
                return resp["candles"][-count:]
        except Exception as e:
            wait = 2 ** tentativa
            print(f"❌ Erro pegar_candles({ativo}): {e}, tentando em {wait}s")
            time.sleep(wait)
    return None

# ===============================
# MERCADO ABERTO
# ===============================
def mercado_aberto(ativo):
    ws = criar_ws()
    if not ws:
        return False
    try:
        ws.send(json.dumps({"active_symbols": "brief"}))
        resp = json.loads(ws.recv())
        ws.close()
        if "active_symbols" in resp:
            for s in resp["active_symbols"]:
                if s["symbol"] == ativo:
                    return s.get("market_status") == "open"
    except Exception as e:
        print(f"❌ Erro verificar mercado aberto {ativo}: {e}")
    return False

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
# ESTATÍSTICAS
# ===============================
def calcular_estatisticas():
    stats = {}
    if os.path.exists(HIST_FILE):
        with open(HIST_FILE, "r") as f:
            try:
                historico = json.load(f)
            except:
                historico = []
        for entry in historico:
            ativo = entry["ativo"]
            resultado = entry["resultado"]
            if ativo not in stats:
                stats[ativo] = {"Green":0,"Red":0}
            if "Green" in resultado:
                stats[ativo]["Green"] +=1
            elif "Red" in resultado:
                stats[ativo]["Red"] +=1
    return stats

def enviar_estatisticas():
    stats = calcular_estatisticas()
    msg = "📊 <b>Estatísticas de Acerto por Ativo</b>\n\n"
    for ativo, data in stats.items():
        total = data["Green"] + data["Red"]
        if total == 0:
            continue
        pct = int(data["Green"]/total*100)
        msg += f"{ativo}: {data['Green']}💸 / {data['Red']}🧨 → {pct}% Green\n"
    tg_send(msg)

# ===============================
# LOOP AVANÇADO
# ===============================
def loop_ativos(ativos):
    ws = criar_ws()
    if not ws:
        return
    Thread(target=manter_conexao_viva, args=(ws,), daemon=True).start()

    while True:
        for ativo in ativos:
            if ativo in ATIVOS_OTC and not mercado_aberto(ativo):
                continue

            candles = pegar_candles_ws(ws, ativo)
            if not candles:
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

        # Atualiza estatísticas a cada 5 sinais
        enviar_estatisticas()
        time.sleep(1)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    tg_send("🤖 Troia V19 FINAL PROFISSIONAL iniciado - Monitorando Forex e OTC!")

    Thread(target=loop_ativos, args=(ATIVOS_FOREX,), daemon=True).start()
    Thread(target=loop_ativos, args=(ATIVOS_OTC,), daemon=True).start()

    while True:
        time.sleep(10)
