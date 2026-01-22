import websocket, json, time, threading, requests, os
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 180  # M3
BR_TZ = timezone(timedelta(hours=-3))
PORT = int(os.environ.get("PORT", 8080))

ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD",
    "frxUSDCAD","frxUSDCHF","frxEURJPY","frxGBPJPY"
]

# ===============================
# ESTADO GLOBAL
# ===============================
sinal_ativo = None
modo_atual = "CONSERVADOR"
bot_iniciado = False
ultimo_ws_ping = time.time()

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
# BOT START
# ===============================
def iniciar_bot():
    global bot_iniciado
    if not bot_iniciado:
        hora = datetime.now(BR_TZ).strftime("%d/%m %H:%M")
        send_telegram(f"🤖 <b>Troia-IA V17</b> iniciado\n🕒 {hora} (BR)")
        bot_iniciado = True

# ===============================
# ESTRATÉGIA M3
# ===============================
def analisar_candles(candles):
    global modo_atual

    ult = candles[-6:]
    altas = 0
    baixas = 0
    corpos = []

    for c in ult:
        open_, close = float(c["open"]), float(c["close"])
        corpo = abs(close - open_)
        corpos.append(corpo)
        if close > open_:
            altas += 1
        else:
            baixas += 1

    media_corpo = sum(corpos) / len(corpos)

    # modo automático
    modo_atual = "AGRESSIVO" if media_corpo > corpos[-1] * 0.8 else "CONSERVADOR"

    if altas >= 4:
        return "CALL"
    if baixas >= 4:
        return "PUT"

    return None

# ===============================
# RESULTADO
# ===============================
def verificar_resultado(entrada, candle):
    open_, close = float(candle["open"]), float(candle["close"])
    if entrada == "CALL":
        return "GREEN ✅" if close > open_ else "RED ❌"
    else:
        return "GREEN ✅" if close < open_ else "RED ❌"

# ===============================
# WEBSOCKET
# ===============================
def on_message(ws, msg):
    global sinal_ativo

    data = json.loads(msg)
    if "candles" not in data:
        return

    candles = data["candles"]
    ativo = data["echo_req"]["ticks_history"]

    # Se tem sinal ativo, verificar resultado
    if sinal_ativo and sinal_ativo["ativo"] == ativo:
        resultado = verificar_resultado(sinal_ativo["direcao"], candles[-1])
        hora = datetime.now(BR_TZ).strftime("%H:%M")

        send_telegram(
            f"📊 <b>RESULTADO</b>\n"
            f"📌 {ativo}\n"
            f"🎯 {sinal_ativo['direcao']}\n"
            f"📍 {resultado}\n"
            f"🕒 {hora}"
        )
        sinal_ativo = None
        return

    # Não envia novo sinal se ainda existir um ativo
    if sinal_ativo:
        return

    direcao = analisar_candles(candles)
    if not direcao:
        return

    hora = datetime.now(BR_TZ).strftime("%H:%M")
    sinal_ativo = {"ativo": ativo, "direcao": direcao}

    send_telegram(
        f"📢 <b>SINAL M3</b>\n"
        f"📌 {ativo}\n"
        f"⏱️ 3M\n"
        f"🎯 <b>{direcao}</b>\n"
        f"⚙️ Modo: {modo_atual}\n"
        f"🕒 {hora}"
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

def on_close(ws, *args):
    send_telegram("⚠️ WebSocket caiu. Reconectando...")
    time.sleep(5)
    iniciar_ws()

def on_error(ws, error):
    send_telegram(f"❌ Erro WebSocket: {error}")

def iniciar_ws():
    ws = websocket.WebSocketApp(
        DERIV_WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error
    )
    ws.run_forever(ping_interval=30, ping_timeout=10)

# ===============================
# HTTP HEALTH
# ===============================
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Troia-IA V17 ONLINE")

def iniciar_http():
    HTTPServer(("0.0.0.0", PORT), Health).serve_forever()

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    threading.Thread(target=iniciar_http, daemon=True).start()
    iniciar_ws()
