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
# CONFIGURAÇÃO (AGRESSIVO TESTE)
# =====================================================
TIMEFRAME = 60
NUM_CANDLES = 12
CONF_MIN = 48
HEARTBEAT = 20
BR_TZ = timezone(timedelta(hours=-3))
HIST_FILE = "historico_sentinel.json"

ANTECIPADO_DE = 40
ANTECIPADO_ATE = 58

COOLDOWN = 90
ultimo_sinal = {}

# =====================================================
# ATIVOS
# =====================================================
FOREX = {
    "frxEURUSD": "EUR/USD",
    "frxGBPUSD": "GBP/USD",
    "frxUSDJPY": "USD/JPY",
    "frxAUDUSD": "AUD/USD",
    "frxEURGBP": "EUR/GBP",
    "frxUSDCAD": "USD/CAD"
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
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8080))), KeepAlive).serve_forever()

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
# ANÁLISE
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
# LOOP PRINCIPAL — PRÉ → CONFIRMA → RESULTADO
# =====================================================
def loop():
    ws = conectar_ws()
    Thread(target=heartbeat, args=(ws,), daemon=True).start()
    tg_send("⚠️ <b>SENTINEL IA V19.1</b>\n🔎 Pré-sinal com confirmação real de vela")

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
                if not candles or len(candles) < NUM_CANDLES:
                    continue

                conf = confianca(candles)
                if conf < CONF_MIN:
                    continue

                d = direcao(candles)
                ultimo_epoch = candles[-1]["epoch"]
                ultimo_sinal[cod] = agora_ts

                msg_base = f"""
━━━━━━━━━━━━━━━━━━
⚠️ <b>PRÉ-SINAL</b>

📌 Ativo: <b>{nome}</b>
🎯 Direção provável: <b>{d}</b>
⏱ Entrada prevista: <b>próxima vela</b>

🧠 Confiança: {conf}%
Status: Aguardando confirmação
━━━━━━━━━━━━━━━━━━
""".strip()

                msg_id = tg_send(msg_base)

                # aguarda troca REAL da vela
                while True:
                    c2 = pegar_candles(ws, cod, 2)
                    if c2 and c2[-1]["epoch"] != ultimo_epoch:
                        break
                    time.sleep(0.3)

                preco_ent = pegar_tick(ws, cod)
                if not preco_ent:
                    tg_edit(msg_id, msg_base + "\n\n❌ <b>ENTRADA CANCELADA</b>")
                    continue

                tg_edit(msg_id, msg_base + f"""

━━━━━━━━━━━━━━━━━━
✅ <b>ENTRADA CONFIRMADA</b>
🕒 Entrada: {agora()}
💰 Preço Entrada: {preco_ent}
━━━━━━━━━━━━━━━━━━
""")

                fim = time.time() + TIMEFRAME
                while time.time() < fim:
                    time.sleep(0.4)

                preco_fim = pegar_tick(ws, cod)
                if not preco_fim:
                    continue

                if preco_fim > preco_ent:
                    res = "Green" if d == "CALL" else "Red"
                elif preco_fim < preco_ent:
                    res = "Green" if d == "PUT" else "Red"
                else:
                    res = "Empate"

                hist = json.load(open(HIST_FILE)) if os.path.exists(HIST_FILE) else []
                hist.append({
                    "ativo": nome,
                    "direcao": d,
                    "resultado": res,
                    "entrada": preco_ent,
                    "fechamento": preco_fim,
                    "hora": agora()
                })
                json.dump(hist, open(HIST_FILE, "w"), indent=2)

                tg_edit(msg_id, msg_base + f"""

━━━━━━━━━━━━━━━━━━
🏁 <b>RESULTADO: {res}</b>
🕒 Fechamento: {agora()}
💰 Preço Final: {preco_fim}
━━━━━━━━━━━━━━━━━━
""")

                time.sleep(0.6)

            time.sleep(0.4)

        except Exception as e:
            print("ERRO LOOP:", e)
            time.sleep(2)

# =====================================================
# START
# =====================================================
if __name__ == "__main__":
    threading.Thread(target=start_http, daemon=True).start()
    loop()
