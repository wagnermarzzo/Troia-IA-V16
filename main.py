import websocket, json, time, requests, threading, sqlite3
from datetime import datetime, timezone
from collections import defaultdict
from flask import Flask, render_template_string

# ===============================
# CONFIG FIXA
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD",
    "frxUSDCAD","frxUSDCHF","frxNZDUSD","frxEURGBP"
]

TIMEFRAME = 300
CANDLES_ANALISE = 100
RESULT_WAIT = 310

# ===============================
# BANCO
# ===============================
conn = sqlite3.connect("troia_v21.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS sinais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT,
    ativo TEXT,
    tendencia TEXT,
    padrao TEXT,
    direcao TEXT,
    resultado TEXT
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
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode":"HTML"},
            timeout=5
        )
    except:
        pass

# ===============================
# DERIV
# ===============================
def pegar_candles(ativo, count=CANDLES_ANALISE):
    ws = websocket.create_connection("wss://ws.derivws.com/websockets/v3?app_id=1089", timeout=10)
    ws.send(json.dumps({"authorize": DERIV_API_KEY}))
    ws.send(json.dumps({
        "ticks_history": ativo,
        "style": "candles",
        "granularity": TIMEFRAME,
        "count": count,
        "end": "latest"
    }))
    data = json.loads(ws.recv())
    ws.close()
    return data.get("candles", [])

# ===============================
# ANÁLISES
# ===============================
def tendencia(c):
    h = [x["high"] for x in c[-10:]]
    l = [x["low"] for x in c[-10:]]
    if h[-1] > h[-2] and l[-1] > l[-2]:
        return "ALTA"
    if h[-1] < h[-2] and l[-1] < l[-2]:
        return "BAIXA"
    return "LATERAL"

def padrao(c):
    corpo = abs(c["close"] - c["open"])
    total = c["high"] - c["low"]
    if total > 0 and corpo / total >= 0.6:
        return "FORTE"
    return None

# ===============================
# BANCO HELPERS
# ===============================
def salvar_sinal(ativo, tendencia_, padrao_, direcao):
    cursor.execute(
        "INSERT INTO sinais VALUES (NULL,?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), ativo, tendencia_, padrao_, direcao, "PENDENTE")
    )
    conn.commit()
    return cursor.lastrowid

def atualizar_resultado(id_, res):
    cursor.execute("UPDATE sinais SET resultado=? WHERE id=?", (res, id_))
    conn.commit()

def resultado_real(ativo, direcao):
    candle = pegar_candles(ativo, 1)[-1]
    real = "CALL" if candle["close"] > candle["open"] else "PUT"
    return "GREEN" if real == direcao else "RED"

# ===============================
# ANALISAR
# ===============================
def analisar_ativo(ativo):
    candles = pegar_candles(ativo)
    if len(candles) < 30:
        return

    t = tendencia(candles)
    p = padrao(candles[-1])

    if t == "LATERAL" or not p:
        return

    direcao = "CALL" if t == "ALTA" else "PUT"
    sinal_id = salvar_sinal(ativo, t, p, direcao)

    tg(
        f"🚀 <b>TROIA v21</b>\n"
        f"📊 {ativo}\n"
        f"📈 {t}\n"
        f"🔥 {p}\n"
        f"🎯 {direcao}\n"
        f"⏱ Entrada: Agora / Próx. 5M"
    )

    time.sleep(RESULT_WAIT)
    res = resultado_real(ativo, direcao)
    atualizar_resultado(sinal_id, res)

    tg(f"🧾 <b>RESULTADO</b>\n{ativo}\n{direcao}\n{res}")

# ===============================
# LOOP
# ===============================
def loop():
    tg("🧠 TROIA v21 — FASE 2.1 (PAINEL ATIVO)")
    while True:
        for ativo in ATIVOS:
            try:
                analisar_ativo(ativo)
                time.sleep(5)
            except:
                time.sleep(3)

# ===============================
# PAINEL WEB
# ===============================
app = Flask(__name__)

HTML = """
<!doctype html>
<title>Troia v21</title>
<h1>🚀 Troia v21 - Painel</h1>
<p>Status: <b>ONLINE</b></p>
<p>Total sinais: {{total}}</p>
<p>Greens: {{greens}}</p>
<p>Reds: {{reds}}</p>
<p>Winrate: {{winrate}}%</p>
<p>Último sinal: {{ultimo}}</p>
"""

@app.route("/")
def painel():
    cursor.execute("SELECT COUNT(*) FROM sinais")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sinais WHERE resultado='GREEN'")
    greens = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sinais WHERE resultado='RED'")
    reds = cursor.fetchone()[0]

    winrate = round((greens / total) * 100, 2) if total > 0 else 0

    cursor.execute("SELECT ativo || ' ' || direcao || ' ' || resultado FROM sinais ORDER BY id DESC LIMIT 1")
    u = cursor.fetchone()
    ultimo = u[0] if u else "Nenhum"

    return render_template_string(
        HTML,
        total=total,
        greens=greens,
        reds=reds,
        winrate=winrate,
        ultimo=ultimo
    )

# ===============================
# START
# ===============================
def start():
    threading.Thread(target=loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    start()
