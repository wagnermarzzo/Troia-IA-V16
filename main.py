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
# CONFIGURAÇÃO – AGRESSIVO
# =====================================================
TIMEFRAME = 60
NUM_CANDLES = 15
HEARTBEAT = 20
CONF_MIN = 52
BR_TZ = timezone(timedelta(hours=-3))
HIST_FILE = "historico_sentinel.json"

# janela antecipada ampliada
ANTECIPADO_DE = 40
ANTECIPADO_ATE = 59

# cooldown por ativo (segundos)
COOLDOWN = 120
ultimo_sinal = {}

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
            time.sleep(3)

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
# ANÁLISE – AGRESSIVA
# =====================================================
def direcao(candles):
    ult = candles[-3:]
    altas = sum(1 for c in ult if c["close"] > c["open"])
    baixas = sum(1 for c in ult if c["close"] < c["open"])
    return "CALL" if altas >= baixas else "PUT"

def confianca(candles):
    call = sum(1 for c in candles if c["close"] > c["open"])
    return int(call / len(candles) * 100)

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
# LOOP PRINCIPAL
# =====================================================
def loop():
    ws = conectar_ws()
    Thread(target=heartbeat, args=(ws,), daemon=True).start()
    tg_send("🔥 <b>SENTINEL IA V18</b>\n⚡ MODO AGRESSIVO ATIVO")

    while True:
        try:
            sec = int(time.time()) % 60
            if not (ANTECIPADO_DE <= sec <= ANTECIPADO_ATE):
                time.sleep(0.25)
                continue

            for cod, nome in FOREX.items():
                agora_ts = time.time()
                if cod in ultimo_sinal and agora_ts - ultimo_sinal[cod] < COOLDOWN:
                    continue

                candles = pegar_candles(ws, cod, NUM_CANDLES)
                if not candles:
                    continue

                conf = confianca(candles)
                if conf < CONF_MIN:
                    continue

                d = direcao(candles)
                preco_ent = pegar_tick(ws, cod)
                if not preco_ent:
                    continue

                ultimo_sinal[cod] = agora_ts

                msg = f"""
━━━━━━━━━━━━━━━━━━
🔥 <b>SENTINEL IA • AGRESSIVO</b>

📌 Ativo: <b>{nome}</b>
🎯 Direção: <b>{d}</b>
⏱ Expiração: 1 Min

🕒 Entrada: <b>{agora()}</b>
💰 Preço Entrada: <b>{preco_ent}</b>

⚡ Confiança: {conf}%
━━━━━━━━━━━━━━━━━━
""".strip()

                msg_id = tg_send(msg)

                fim = time.time() + TIMEFRAME
                while time.time() < fim:
                    time.sleep(0.4)

                preco_fim = pegar_tick(ws, cod)

                if preco_fim:
                    if preco_fim > preco_ent:
                        res = "Green" if d == "CALL" else "Red"
                    elif preco_fim < preco_ent:
                        res = "Green" if d == "PUT" else "Red"
                    else:
                        res = "Empate"

                    salvar_hist({
                        "ativo": nome,
                        "direcao": d,
                        "resultado": res,
                        "entrada": preco_ent,
                        "fechamento": preco_fim,
                        "hora": agora()
                    })

                    tg_edit(msg_id, msg + f"""

━━━━━━━━━━━━━━━━━━
<b>RESULTADO: {res}</b>
🕒 Fechamento: {agora()}
💰 Preço Final: {preco_fim}
━━━━━━━━━━━━━━━━━━
""")

                time.sleep(0.6)

            time.sleep(0.3)

        except Exception as e:
            print("ERRO:", e)
            time.sleep(2)

# =====================================================
# START
# =====================================================
if __name__ == "__main__":
    threading.Thread(target=start_http, daemon=True).start()
    loop()
