import websocket, json, time, threading, sqlite3, requests, math
from datetime import datetime, timezone, timedelta

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

APP_ID = 1089
GRANULARITY = 300  # 5 minutos
MAX_SINAIS_30M = 3
INTERVALO_CONTROLE = 1800

ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD",
    "frxUSDCAD","frxUSDCHF","frxNZDUSD",
    "frxEURUSD_otc","frxGBPUSD_otc","frxUSDJPY_otc"
]

# ===============================
# DB IA
# ===============================
db = sqlite3.connect("troia_ai.db", check_same_thread=False)
c = db.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS ativos (
 ativo TEXT PRIMARY KEY,
 sinais INT, greens INT, reds INT,
 score REAL, cooldown INT
)
""")
db.commit()

# ===============================
# TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode":"HTML"}, timeout=5
        )
    except:
        pass

# ===============================
# INDICADORES
# ===============================
def ema(valores, periodo):
    k = 2 / (periodo + 1)
    ema_val = valores[0]
    for v in valores[1:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val

def suporte_resistencia(candles):
    lows = [c["low"] for c in candles]
    highs = [c["high"] for c in candles]
    return min(lows), max(highs)

def padrao_candle(c):
    corpo = abs(c["close"] - c["open"])
    sombra = abs(c["high"] - c["low"])
    if corpo > sombra * 0.6:
        return "forca"
    if corpo < sombra * 0.3:
        return "indecisao"
    return "neutro"

# ===============================
# IA ATIVO
# ===============================
def get_ativo(ativo):
    c.execute("SELECT * FROM ativos WHERE ativo=?", (ativo,))
    r = c.fetchone()
    if not r:
        c.execute("INSERT INTO ativos VALUES (?,?,?,?,?,?)", (ativo,0,0,0,50,0))
        db.commit()
        return get_ativo(ativo)
    return r

def update_ativo(ativo, green):
    a = get_ativo(ativo)
    sinais, greens, reds = a[1], a[2], a[3]
    sinais += 1
    greens += 1 if green else 0
    reds += 0 if green else 1
    winrate = greens / sinais * 100
    score = winrate - reds * 5
    c.execute("UPDATE ativos SET sinais=?,greens=?,reds=?,score=? WHERE ativo=?",
              (sinais,greens,reds,score,ativo))
    db.commit()

# ===============================
# MERCADO REAL
# ===============================
def get_candles(ativo, count=50):
    ws = websocket.create_connection(f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}")
    ws.send(json.dumps({"authorize": DERIV_API_KEY}))
    ws.send(json.dumps({
        "ticks_history": ativo,
        "style": "candles",
        "granularity": GRANULARITY,
        "count": count
    }))
    data = json.loads(ws.recv())
    ws.close()
    return data["candles"]

# ===============================
# ANALISADOR
# ===============================
def analisar(ativo):
    candles = get_candles(ativo)
    closes = [c["close"] for c in candles]

    ema20 = ema(closes[-20:], 20)
    ema50 = ema(closes[-50:], 50)
    suporte, resistencia = suporte_resistencia(candles[-20:])
    ultimo = candles[-1]

    tendencia = "CALL" if ema20 > ema50 else "PUT"
    if padrao_candle(ultimo) == "indecisao":
        return None

    confianca = 60
    if tendencia == "CALL" and ultimo["close"] > suporte:
        confianca += 10
    if tendencia == "PUT" and ultimo["close"] < resistencia:
        confianca += 10

    if confianca >= 70:
        return tendencia, confianca
    return None

# ===============================
# LOOP
# ===============================
sinais_30m = []

tg("🤖 TROIA v23 ONLINE — MERCADO REAL 5M")

while True:
    now = time.time()
    sinais_30m = [t for t in sinais_30m if now - t < INTERVALO_CONTROLE]

    if len(sinais_30m) >= MAX_SINAIS_30M:
        time.sleep(30)
        continue

    for ativo in ATIVOS:
        try:
            r = analisar(ativo)
            if r:
                direcao, conf = r
                sinais_30m.append(time.time())
                horario = (datetime.now(timezone.utc)+timedelta(minutes=5)).strftime("%H:%M UTC")

                tg(
                    f"🔥 <b>SINAL TROIA v23</b>\n"
                    f"📊 {ativo}\n"
                    f"🎯 {direcao}\n"
                    f"⏱ 5M\n"
                    f"🚀 Entrada: {horario}\n"
                    f"📈 Confiança: {conf}%"
                )
                time.sleep(10)
        except:
            time.sleep(2)
