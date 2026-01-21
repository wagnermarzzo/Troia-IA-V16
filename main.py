import websocket, json, time, threading, sqlite3, requests
from flask import Flask
from datetime import datetime, timezone, timedelta

# ===============================
# CONFIGURAÇÕES
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

APP_ID = 1089
GRANULARITY = 300  # 5 minutos
MAX_SINAIS_30M = 3
INTERVALO_30M = 1800

# ===============================
# ATIVOS FOREX + OTC (COMPLETO)
# ===============================
ATIVOS = [
    # FOREX
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD",
    "frxUSDCAD","frxUSDCHF","frxNZDUSD","frxEURGBP",
    "frxEURJPY","frxGBPJPY","frxAUDJPY","frxCADJPY",
    "frxCHFJPY","frxNZDJPY",

    # OTC
    "frxEURUSD_otc","frxGBPUSD_otc","frxUSDJPY_otc",
    "frxAUDUSD_otc","frxUSDCAD_otc","frxUSDCHF_otc",
    "frxNZDUSD_otc","frxEURGBP_otc","frxEURJPY_otc",
    "frxGBPJPY_otc","frxAUDJPY_otc","frxCADJPY_otc",
    "frxCHFJPY_otc","frxNZDJPY_otc"
]

# ===============================
# FLASK KEEP ALIVE
# ===============================
app = Flask(__name__)

@app.route("/")
def home():
    return "TROIA v23 ONLINE"

def start_flask():
    app.run(host="0.0.0.0", port=8080)

# ===============================
# TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode":"HTML"},
            timeout=5
        )
    except:
        pass

# ===============================
# BANCO DE DADOS IA
# ===============================
db = sqlite3.connect("troia_ai.db", check_same_thread=False)
c = db.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS ativos (
    ativo TEXT PRIMARY KEY,
    sinais INTEGER,
    greens INTEGER,
    reds INTEGER,
    score REAL
)
""")
db.commit()

def get_ativo(ativo):
    c.execute("SELECT * FROM ativos WHERE ativo=?", (ativo,))
    r = c.fetchone()
    if not r:
        c.execute("INSERT INTO ativos VALUES (?,?,?,?,?)", (ativo,0,0,0,50))
        db.commit()
        return get_ativo(ativo)
    return r

def update_ativo(ativo, green):
    a = get_ativo(ativo)
    sinais, greens, reds = a[1], a[2], a[3]
    sinais += 1
    greens += 1 if green else 0
    reds += 0 if green else 1
    winrate = (greens / sinais) * 100
    score = winrate - (reds * 5)
    c.execute(
        "UPDATE ativos SET sinais=?, greens=?, reds=?, score=? WHERE ativo=?",
        (sinais, greens, reds, score, ativo)
    )
    db.commit()

# ===============================
# INDICADORES
# ===============================
def ema(valores, periodo):
    k = 2 / (periodo + 1)
    ema_v = valores[0]
    for v in valores[1:]:
        ema_v = v * k + ema_v * (1 - k)
    return ema_v

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
# DERIV MARKET DATA (REAL)
# ===============================
def get_candles(ativo, count=50):
    ws = websocket.create_connection(
        f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}", timeout=10
    )
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
# ANÁLISE REAL
# ===============================
def analisar_ativo(ativo):
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
# LOOP PRINCIPAL TROIA
# ===============================
def iniciar_troia():
    sinais = []
    tg("🤖 TROIA v23 ONLINE — MERCADO REAL 5M")

    while True:
        agora = time.time()
        sinais[:] = [t for t in sinais if agora - t < INTERVALO_30M]

        if len(sinais) >= MAX_SINAIS_30M:
            time.sleep(30)
            continue

        for ativo in ATIVOS:
            try:
                r = analisar_ativo(ativo)
                if r:
                    direcao, conf = r
                    sinais.append(time.time())

                    horario = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%H:%M UTC")

                    tg(
                        f"🔥 <b>SINAL TROIA v23</b>\n"
                        f"📊 {ativo}\n"
                        f"🎯 {direcao}\n"
                        f"⏱ 5M\n"
                        f"🚀 Entrada: {horario}\n"
                        f"📈 Confiança: {conf}%"
                    )

                    time.sleep(10)
            except Exception as e:
                time.sleep(3)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    threading.Thread(target=start_flask).start()
    time.sleep(3)
    iniciar_troia()
