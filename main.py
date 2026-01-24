import websocket, json, time, requests, os
from datetime import datetime, timezone, timedelta
from threading import Thread

# =====================================================
# CREDENCIAIS (FIXAS)
# =====================================================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

# =====================================================
# CONFIG GERAL
# =====================================================
TIMEFRAME = 60
HEARTBEAT = 25
BR_TZ = timezone(timedelta(hours=-3))
HIST_FILE = "historico_v19q.json"

MODO_QUOTEX = True

# =====================================================
# PARÂMETROS QUOTEX FRIENDLY
# =====================================================
FOREX_Q_CANDLES = 5
OTC_Q_CANDLES = 3

FOREX_CONF = 60
OTC_CONF = 68

FOREX_DELAY = (10, 30)
OTC_DELAY = (20, 40)

# =====================================================
# ATIVOS
# =====================================================
ATIVOS_FOREX = ["frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxEURGBP"]
ATIVOS_OTC = ["OTC_DJI","OTC_SPC","OTC_NDX","OTC_FTSE","OTC_N225"]

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
        return r.get("result", {}).get("message_id")
    except:
        return None

def tg_edit(mid, msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
            data={"chat_id": TELEGRAM_CHAT_ID, "message_id": mid, "text": msg, "parse_mode": "HTML"},
            timeout=8
        )
    except:
        pass

# =====================================================
# DERIV WS
# =====================================================
def conectar_ws():
    ws = websocket.create_connection("wss://ws.derivws.com/websockets/v3?app_id=1089", timeout=10)
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

def pegar_candles(ws, ativo, qtd):
    ws.send(json.dumps({
        "ticks_history": ativo,
        "style": "candles",
        "granularity": TIMEFRAME,
        "count": qtd,
        "end": "latest"
    }))
    return json.loads(ws.recv()).get("candles")

# =====================================================
# UTIL
# =====================================================
def direcao(c): 
    return "CALL" if c["close"] > c["open"] else "PUT"

def corpo(c): 
    return abs(c["close"] - c["open"])

def pavio(c):
    return (c["high"] - c["low"]) - corpo(c)

# =====================================================
# LÓGICA FOREX
# =====================================================
def logica_forex(c):
    ult = c[-5:]
    d = [direcao(x) for x in ult]
    if d.count(d[-1]) < 3:
        return None
    r = ult[-1]["high"] - ult[-1]["low"]
    if r == 0: return None
    if corpo(ult[-1]) / r < 0.4:
        return None
    return d[-1]

# =====================================================
# LÓGICA OTC
# =====================================================
def logica_otc(c):
    ult = c[-3:]
    if direcao(ult[0]) != direcao(ult[1]):
        return None
    if corpo(ult[1]) <= corpo(ult[0]):
        return None
    if pavio(ult[1]) > corpo(ult[1]):
        return None
    return direcao(ult[1])

# =====================================================
# LOOP
# =====================================================
def loop():
    ws = conectar_ws()
    Thread(target=heartbeat, args=(ws,), daemon=True).start()

    tg_send("⚡ <b>TROIA-IA V19Q ATIVO</b>\nModo Quotex Friendly\nForex + OTC")

    while True:
        for ativo in ATIVOS_FOREX + ATIVOS_OTC:
            qtd = OTC_Q_CANDLES if ativo in ATIVOS_OTC else FOREX_Q_CANDLES
            candles = pegar_candles(ws, ativo, qtd)
            if not candles: continue

            direc = logica_otc(candles) if ativo in ATIVOS_OTC else logica_forex(candles)
            if not direc: continue

            delay = OTC_DELAY if ativo in ATIVOS_OTC else FOREX_DELAY
            time.sleep(delay[0])

            msg = (
                f"⚡ <b>SINAL QUOTEX FRIENDLY</b>\n"
                f"📊 Ativo: {ativo}\n"
                f"🎯 Direção: {direc}\n"
                f"⏱ Entrada: AGORA\n"
                f"⌛ Aguardando resultado..."
            )
            mid = tg_send(msg)

            time.sleep(TIMEFRAME)
            res_c = pegar_candles(ws, ativo, 1)
            res = "💸 Green" if res_c and direcao(res_c[0]) == direc else "🧨 Red"

            tg_edit(mid, msg.replace("⌛ Aguardando resultado...", f"✅ Resultado: {res}"))
            time.sleep(5)

# =====================================================
# START
# =====================================================
if __name__ == "__main__":
    loop()
