import websocket, json, time, requests, os
from datetime import datetime, timezone, timedelta
from threading import Thread, Event

# =====================================================
# CREDENCIAIS (FIXAS – NUNCA REMOVER)
# =====================================================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

# =====================================================
# CONFIGURAÇÃO GERAL
# =====================================================
TIMEFRAME = 60               # 1 minuto
NUM_CANDLES = 20
CONF_MIN = 55
WAIT_BUFFER = 2
HEARTBEAT = 25
MAX_SINAIS_HORA = 5
BR_TZ = timezone(timedelta(hours=-3))
HIST_FILE = "historico_v19.json"

# =====================================================
# ATIVOS 100% REAIS – DERIV
# =====================================================
ATIVOS_FOREX = [
    "frxEURUSD",
    "frxGBPUSD",
    "frxUSDJPY",
    "frxAUDUSD",
    "frxEURGBP"
]

ATIVOS_OTC = [
    "OTC_DJI",
    "OTC_SPC",
    "OTC_NDX",
    "OTC_FTSE",
    "OTC_N225"
]

# =====================================================
# TELEGRAM
# =====================================================
def tg_send(msg):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=8
        ).json()
        if r.get("ok"):
            return r["result"]["message_id"]
    except Exception as e:
        print("Erro Telegram:", e)
    return None

def tg_edit(msg_id, msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
            data={"chat_id": TELEGRAM_CHAT_ID, "message_id": msg_id, "text": msg, "parse_mode": "HTML"},
            timeout=8
        )
    except Exception as e:
        print("Erro editar Telegram:", e)

# =====================================================
# WEBSOCKET DERIV (ÚNICO)
# =====================================================
def conectar_ws():
    ws = websocket.create_connection(
        "wss://ws.derivws.com/websockets/v3?app_id=1089",
        timeout=10
    )
    ws.send(json.dumps({"authorize": DERIV_API_KEY}))
    ws.recv()
    return ws

def heartbeat(ws):
    while True:
        try:
            ws.send(json.dumps({"ping": 1}))
        except:
            break
        time.sleep(HEARTBEAT)

# =====================================================
# FUNÇÕES DE MERCADO REAL
# =====================================================
def mercado_aberto(ws, ativo):
    ws.send(json.dumps({"active_symbols": "brief"}))
    data = json.loads(ws.recv())
    for s in data.get("active_symbols", []):
        if s["symbol"] == ativo:
            return s.get("exchange_is_open") == 1 and not s.get("is_trading_suspended")
    return False

def pegar_candles(ws, ativo, count):
    ws.send(json.dumps({
        "ticks_history": ativo,
        "style": "candles",
        "granularity": TIMEFRAME,
        "count": count,
        "end": "latest"
    }))
    data = json.loads(ws.recv())
    return data.get("candles")

def direcao(c):
    return "CALL" if c["close"] > c["open"] else "PUT"

def confianca(candles):
    call = sum(1 for c in candles if c["close"] > c["open"])
    put = len(candles) - call
    return int(max(call, put) / len(candles) * 100)

# =====================================================
# HISTÓRICO + ESTATÍSTICA (SEM LOOP)
# =====================================================
def salvar_hist(d):
    hist = []
    if os.path.exists(HIST_FILE):
        hist = json.load(open(HIST_FILE))
    hist.append(d)
    json.dump(hist, open(HIST_FILE, "w"), indent=2)

def estatisticas():
    if not os.path.exists(HIST_FILE):
        return ""
    hist = json.load(open(HIST_FILE))
    stats = {}
    for h in hist:
        a = h["ativo"]
        stats.setdefault(a, {"G": 0, "R": 0})
        if "Green" in h["resultado"]:
            stats[a]["G"] += 1
        elif "Red" in h["resultado"]:
            stats[a]["R"] += 1

    msg = "\n📊 <b>Estatística por Ativo</b>\n"
    for a, s in stats.items():
        t = s["G"] + s["R"]
        if t > 0:
            msg += f"{a}: {s['G']}G / {s['R']}R → {int(s['G']/t*100)}%\n"
    return msg

# =====================================================
# LOOP PRINCIPAL (PRÓXIMA VELA – HORÁRIO REAL)
# =====================================================
def loop():
    ws = conectar_ws()
    Thread(target=heartbeat, args=(ws,), daemon=True).start()

    sinais_hora = 0
    hora_ref = datetime.now(BR_TZ).hour

    tg_send("🤖 <b>TROIA-IA V19 ATIVO</b>\nMercado REAL • Próxima vela • Free Safe")

    while True:
        agora = datetime.now(BR_TZ)

        if agora.hour != hora_ref:
            sinais_hora = 0
            hora_ref = agora.hour

        if sinais_hora >= MAX_SINAIS_HORA:
            time.sleep(10)
            continue

        for ativo in ATIVOS_FOREX + ATIVOS_OTC:
            if ativo in ATIVOS_OTC and not mercado_aberto(ws, ativo):
                continue

            candles = pegar_candles(ws, ativo, NUM_CANDLES)
            if not candles:
                continue

            conf = confianca(candles)
            if conf < CONF_MIN:
                continue

            dirc = direcao(candles[-1])

            # calcula abertura da próxima vela
            next_epoch = candles[-1]["epoch"] + TIMEFRAME
            entrada = datetime.fromtimestamp(next_epoch, BR_TZ).strftime("%H:%M:%S")

            msg = (
                f"💥 <b>SINAL V19</b>\n"
                f"📊 Ativo: {ativo}\n"
                f"🎯 Direção: {dirc}\n"
                f"⏱ Entrada: {entrada}\n"
                f"📈 Confiança: {conf}%\n"
                f"⌛ Aguardando fechamento..."
            )

            msg_id = tg_send(msg)
            sinais_hora += 1

            # espera fechamento da vela da entrada
            time.sleep(TIMEFRAME + WAIT_BUFFER)

            resultado_candle = pegar_candles(ws, ativo, 1)
            if resultado_candle:
                res = "💸 Green" if direcao(resultado_candle[0]) == dirc else "🧨 Red"
            else:
                res = "⚠️ Sem dados"

            msg_final = msg.replace("⌛ Aguardando fechamento...", f"✅ Resultado: {res}")
            msg_final += estatisticas()

            tg_edit(msg_id, msg_final)

            salvar_hist({
                "ativo": ativo,
                "direcao": dirc,
                "conf": conf,
                "resultado": res,
                "hora": datetime.now(BR_TZ).strftime("%Y-%m-%d %H:%M:%S")
            })

            time.sleep(5)

        time.sleep(2)

# =====================================================
# START
# =====================================================
if __name__ == "__main__":
    loop()
