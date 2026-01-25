import websocket, json, time, requests, os, threading
from datetime import datetime, timezone, timedelta
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# =====================================================
# CREDENCIAIS
# =====================================================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

# =====================================================
# CONFIGURAÇÃO
# =====================================================
TIMEFRAME = 60
NUM_CANDLES = 20
HEARTBEAT = 25
CONF_MIN = 58
BR_TZ = timezone(timedelta(hours=-3))
HIST_FILE = "historico_sentinel.json"

# janela segura p/ sinal antecipado
ANTECIPADO_DE = 45
ANTECIPADO_ATE = 58

# =====================================================
# ATIVOS FOREX
# =====================================================
FOREX = {
    "frxEURUSD": "EUR/USD",
    "frxGBPUSD": "GBP/USD",
    "frxUSDJPY": "USD/JPY",
    "frxAUDUSD": "AUD/USD",
    "frxEURGBP": "EUR/GBP",
    "frxUSDCAD": "USD/CAD",
    "frxUSDCHF": "USD/CHF",
    "frxNZDUSD": "NZD/USD",
    "frxEURJPY": "EUR/JPY",
    "frxGBPJPY": "GBP/JPY"
}

# =====================================================
# KEEP ALIVE
# =====================================================
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sentinel IA Online")

def start_http():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), KeepAlive).serve_forever()

# =====================================================
# TELEGRAM
# =====================================================
def tg_send(msg):
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
        timeout=10
    ).json()
    return r["result"]["message_id"]

def tg_edit(msg_id, msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
        data={"chat_id": TELEGRAM_CHAT_ID, "message_id": msg_id, "text": msg, "parse_mode": "HTML"},
        timeout=10
    )

# =====================================================
# DERIV WS
# =====================================================
def conectar_ws():
    while True:
        try:
            ws = websocket.create_connection(
                "wss://ws.derivws.com/websockets/v3?app_id=1089",
                timeout=10
            )
            ws.send(json.dumps({"authorize": DERIV_API_KEY}))
            ws.recv()
            return ws
        except:
            time.sleep(5)

def heartbeat(ws):
    while True:
        try:
            ws.send(json.dumps({"ping": 1}))
            time.sleep(HEARTBEAT)
        except:
            return

# =====================================================
# DADOS
# =====================================================
def pegar_candles(ws, ativo, count):
    try:
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": count,
            "end": "latest"
        }))
        return json.loads(ws.recv()).get("candles")
    except:
        return None

def pegar_tick(ws, ativo):
    try:
        ws.send(json.dumps({"ticks": ativo}))
        r = json.loads(ws.recv())
        return r["tick"]["quote"]
    except:
        return None

def agora():
    return datetime.now(BR_TZ).strftime("%H:%M:%S")

# =====================================================
# ANÁLISE
# =====================================================
def direcao_majoritaria(candles):
    ult = candles[-5:]
    altas = sum(1 for c in ult if c["close"] > c["open"])
    baixas = sum(1 for c in ult if c["close"] < c["open"])

    if altas > baixas:
        return "CALL"
    elif baixas > altas:
        return "PUT"
    else:
        return "CALL"

def confianca(candles):
    call = sum(1 for c in candles if c["close"] > c["open"])
    put = len(candles) - call
    return int(max(call, put) / len(candles) * 100)

# =====================================================
# HISTÓRICO
# =====================================================
def carregar_hist():
    return json.load(open(HIST_FILE)) if os.path.exists(HIST_FILE) else []

def salvar_hist(d):
    h = carregar_hist()
    h.append(d)
    json.dump(h, open(HIST_FILE, "w"), indent=2)

# =====================================================
# LOOP PRINCIPAL (SEM BLOQUEIO)
# =====================================================
def loop():
    ws = conectar_ws()
    Thread(target=heartbeat, args=(ws,), daemon=True).start()
    tg_send("🏆 <b>SENTINEL IA V17</b>\n🤖 Forex PRO • Tick Real")

    while True:
        try:
            sec = int(time.time()) % 60
            if not (ANTECIPADO_DE <= sec <= ANTECIPADO_ATE):
                time.sleep(0.3)
                continue

            for cod, nome in FOREX.items():
                candles = pegar_candles(ws, cod, NUM_CANDLES)
                if not candles:
                    continue

                conf = confianca(candles)
                if conf < CONF_MIN:
                    continue

                direcao = direcao_majoritaria(candles)
                preco_ent = pegar_tick(ws, cod)
                if not preco_ent:
                    continue

                msg_base = f"""
━━━━━━━━━━━━━━━━━━
🏆 <b>SENTINEL IA • FOREX</b>

📊 <b>SINAL ANTECIPADO</b>
📌 Ativo: <b>{nome}</b>
🎯 Direção: <b>{direcao}</b>
⏱ Expiração: 1 Min

🕒 Entrada: <b>{agora()}</b>
💰 Preço Entrada: <b>{preco_ent}</b>

🧠 Confiança: {conf}%
━━━━━━━━━━━━━━━━━━
""".strip()

                msg_id = tg_send(msg_base)

                fechamento = time.time() + TIMEFRAME
                while time.time() < fechamento:
                    time.sleep(0.5)

                preco_fim = pegar_tick(ws, cod)
                if not preco_fim:
                    continue

                if preco_fim > preco_ent:
                    res = "Green" if direcao == "CALL" else "Red"
                elif preco_fim < preco_ent:
                    res = "Green" if direcao == "PUT" else "Red"
                else:
                    res = "Empate"

                salvar_hist({
                    "ativo": nome,
                    "direcao": direcao,
                    "resultado": res,
                    "entrada": preco_ent,
                    "fechamento": preco_fim,
                    "hora": agora()
                })

                tg_edit(msg_id, msg_base + f"""

━━━━━━━━━━━━━━━━━━
<b>RESULTADO: {res}</b>
🕒 Fechamento: {agora()}
💰 Preço Final: {preco_fim}
━━━━━━━━━━━━━━━━━━
""")

                time.sleep(1)

            time.sleep(0.5)

        except Exception as e:
            print("ERRO LOOP:", e)
            time.sleep(3)

# =====================================================
# START
# =====================================================
if __name__ == "__main__":
    threading.Thread(target=start_http, daemon=True).start()
    loop()
