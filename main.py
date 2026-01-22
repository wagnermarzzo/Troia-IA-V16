import websocket, json, time, requests, threading, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
from http.server import HTTPServer, BaseHTTPRequestHandler

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 300
CONF_MIN = 46
PROB_MIN = 53
MAX_SINAIS_HORA = 8
COOLDOWN_ATIVO = 240

BR_TZ = timezone(timedelta(hours=-3))
PORT = int(os.environ.get("PORT", 8080))

ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD",
    "frxUSDCHF","frxEURJPY","frxGBPJPY","frxEURGBP","frxAUDJPY"
]

# ===============================
# CONTROLE GLOBAL
# ===============================
ultimo_sinal = defaultdict(int)
sinais_hora = deque()
bot_iniciado = False
ultimo_trafego = time.time()

# ===============================
# TELEGRAM
# ===============================
def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except:
        pass

# ===============================
# START BOT
# ===============================
def iniciar_bot():
    global bot_iniciado
    if not bot_iniciado:
        hora = datetime.now(BR_TZ).strftime("%d/%m %H:%M")
        send_telegram(f"🤖 <b>Troia-IA V16 iniciado</b>\n🕒 {hora} (BR)")
        bot_iniciado = True

# ===============================
# ANÁLISE
# ===============================
def analisar(ativo, closes):
    if len(closes) < 6:
        return None

    ult = closes[-5:]
    alta = sum(1 for i in range(1, 5) if ult[i] > ult[i-1])
    baixa = 4 - alta

    direcao = "CALL" if alta >= 3 else "PUT"
    conf = 45 + (alta if direcao == "CALL" else baixa) * 2
    prob = conf + 7

    if conf >= CONF_MIN and prob >= PROB_MIN:
        return direcao, conf, prob
    return None

# ===============================
# WS CALLBACKS
# ===============================
def on_message(ws, message):
    global ultimo_trafego
    ultimo_trafego = time.time()

    data = json.loads(message)
    if "candles" not in data:
        return

    ativo = data["echo_req"]["ticks_history"]
    closes = [float(c["close"]) for c in data["candles"]]
    agora = int(time.time())

    if agora - ultimo_sinal[ativo] < COOLDOWN_ATIVO:
        return

    sinais_hora.append(agora)
    while sinais_hora and agora - sinais_hora[0] > 3600:
        sinais_hora.popleft()
    if len(sinais_hora) >= MAX_SINAIS_HORA:
        return

    r = analisar(ativo, closes)
    if not r:
        return

    direcao, conf, prob = r
    ultimo_sinal[ativo] = agora
    hora = datetime.now(BR_TZ).strftime("%H:%M")

    send_telegram(
        f"📊 <b>SINAL FOREX</b>\n"
        f"📌 <b>{ativo}</b>\n"
        f"⏱️ {TIMEFRAME//60}m | {hora}\n"
        f"🎯 <b>{direcao}</b>\n"
        f"📈 Conf: {conf}% | Prob: {prob}%"
    )

def on_open(ws):
    iniciar_bot()
    for ativo in ATIVOS:
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": 20
        }))
        time.sleep(0.3)

def on_error(ws, error):
    print("❌ WS erro:", error)

def on_close(ws, code, reason):
    print("🔴 WS fechado:", code, reason)

# ===============================
# GERENCIADOR WS (ÚNICO)
# ===============================
def iniciar_ws():
    while True:
        try:
            ws = websocket.WebSocketApp(
                DERIV_WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever(ping_interval=25, ping_timeout=10)
        except Exception as e:
            print("Erro crítico WS:", e)
        time.sleep(5)

# ===============================
# WATCHDOG
# ===============================
def watchdog():
    while True:
        if time.time() - ultimo_trafego > 90:
            send_telegram("⚠️ Troia-IA reiniciado (WS inativo)")
            os._exit(1)
        time.sleep(15)

# ===============================
# HTTP KEEP ALIVE
# ===============================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Troia-IA V16 ONLINE")

def iniciar_http():
    HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    threading.Thread(target=iniciar_http, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()
    iniciar_ws()
