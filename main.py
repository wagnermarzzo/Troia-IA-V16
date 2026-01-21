import threading, time, json, sqlite3
from datetime import datetime
import requests, websocket
from flask import Flask

# ===============================
# CREDENCIAIS
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

# ===============================
# ATIVOS (FOREX + OTC)
# ===============================
ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD",
    "frxUSDCAD","frxUSDCHF","frxNZDUSD","frxEURGBP",
    "frxEURJPY","frxGBPJPY",
    "OTC_EURUSD","OTC_GBPUSD","OTC_USDJPY",
    "OTC_AUDUSD","OTC_USDCAD","OTC_USDCHF",
    "OTC_EURGBP","OTC_EURJPY","OTC_GBPJPY"
]

TIMEFRAME = 300  # 5 MIN
VELAS_ANALISE = 50
CONF_MIN = 65

# ===============================
# BANCO DE DADOS
# ===============================
conn = sqlite3.connect("troia.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS velas (
    ativo TEXT, open REAL, high REAL, low REAL, close REAL, epoch INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sinais (
    ativo TEXT, direcao TEXT, confianca INTEGER,
    resultado TEXT, horario TEXT
)
""")
conn.commit()

# ===============================
# TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode":"HTML"},
            timeout=5
        )
    except:
        pass

# ===============================
# IA — FUNÇÕES
# ===============================
def tendencia(candles):
    altas = sum(1 for c in candles if c["close"] > c["open"])
    baixas = len(candles) - altas
    if altas > baixas: return "CALL"
    if baixas > altas: return "PUT"
    return None

def suporte_resistencia(candles):
    lows = [c["low"] for c in candles]
    highs = [c["high"] for c in candles]
    return min(lows), max(highs)

def padrao_candle(c):
    corpo = abs(c["close"] - c["open"])
    pavio = (c["high"] - c["low"]) - corpo
    if corpo > pavio * 1.5:
        return "FORTE"
    return "FRACO"

def calcular_confianca(tend, padrao):
    conf = 50
    if tend: conf += 15
    if padrao == "FORTE": conf += 15
    return conf

# ===============================
# DECISÃO FINAL
# ===============================
def analisar_ativo(ativo):
    cursor.execute("""
        SELECT open,high,low,close FROM velas
        WHERE ativo=? ORDER BY epoch DESC LIMIT ?
    """,(ativo,VELAS_ANALISE))
    rows = cursor.fetchall()
    if len(rows) < VELAS_ANALISE: return

    candles = [{"open":o,"high":h,"low":l,"close":c} for o,h,l,c in rows[::-1]]

    tend = tendencia(candles)
    sup, res = suporte_resistencia(candles)
    ultimo = candles[-1]
    pad = padrao_candle(ultimo)
    conf = calcular_confianca(tend, pad)

    if conf >= CONF_MIN and tend:
        enviar_sinal(ativo, tend, conf)

# ===============================
# ENVIO DE SINAL
# ===============================
sinal_ativo = False

def enviar_sinal(ativo, direcao, conf):
    global sinal_ativo
    if sinal_ativo: return
    sinal_ativo = True

    horario = datetime.utcnow().strftime("%H:%M UTC")
    cursor.execute("""
        INSERT INTO sinais VALUES (?,?,?,?,?)
    """,(ativo,direcao,conf,"PENDENTE",horario))
    conn.commit()

    tg(
        f"🔥 <b>SINAL IA TROIA v21</b>\n"
        f"📊 <b>Ativo:</b> {ativo}\n"
        f"🎯 <b>Direção:</b> {direcao}\n"
        f"🧠 <b>Confiança:</b> {conf}%\n"
        f"⏱️ <b>Timeframe:</b> M5\n"
        f"🚀 <b>Entrada:</b> AGORA"
    )

    threading.Timer(300, avaliar_resultado, args=[ativo,direcao]).start()

def avaliar_resultado(ativo,direcao):
    global sinal_ativo
    cursor.execute("""
        SELECT close,open FROM velas
        WHERE ativo=? ORDER BY epoch DESC LIMIT 1
    """,(ativo,))
    c,o = cursor.fetchone()
    real = "CALL" if c>o else "PUT"
    res = "GREEN" if real==direcao else "RED"

    cursor.execute("""
        UPDATE sinais SET resultado=?
        WHERE resultado='PENDENTE'
    """,(res,))
    conn.commit()

    tg(f"🧾 RESULTADO: <b>{res}</b> — {ativo}")
    sinal_ativo = False

# ===============================
# WEBSOCKET DERIV
# ===============================
def on_message(ws,msg):
    data = json.loads(msg)
    if "ohlc" in data:
        c = data["ohlc"]
        cursor.execute("""
            INSERT INTO velas VALUES (?,?,?,?,?,?)
        """,(c["symbol"],c["open"],c["high"],c["low"],c["close"],c["epoch"]))
        conn.commit()
        analisar_ativo(c["symbol"])

def on_open(ws):
    ws.send(json.dumps({"authorize":DERIV_API_KEY}))
    time.sleep(1)
    for a in ATIVOS:
        ws.send(json.dumps({
            "ticks_history":a,
            "style":"candles",
            "granularity":TIMEFRAME,
            "count":120,
            "end":"latest"
        }))

def iniciar_ws():
    websocket.WebSocketApp(
        "wss://ws.derivws.com/websockets/v3?app_id=1089",
        on_open=on_open,
        on_message=on_message
    ).run_forever()

# ===============================
# PAINEL WEB
# ===============================
app = Flask(__name__)

@app.route("/")
def painel():
    cursor.execute("SELECT COUNT(*) FROM sinais WHERE resultado='GREEN'")
    g = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sinais WHERE resultado='RED'")
    r = cursor.fetchone()[0]
    total = g+r
    win = (g/total*100) if total>0 else 0

    return f"""
    <h2>🚀 TROIA v21 — FASE 4</h2>
    <p>Greens: {g}</p>
    <p>Reds: {r}</p>
    <p>Winrate: {win:.2f}%</p>
    """

# ===============================
# START
# ===============================
tg("🚀 Troia v21 Fase 4 ONLINE | IA de decisão ativa")

threading.Thread(target=iniciar_ws, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
