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
    "frxEURUSD","frxGBPUSD","frxUSDJPY",
    "frxAUDUSD","frxUSDCAD","frxUSDCHF",
    "frxEURJPY","frxGBPJPY"
]

# ===============================
# ESTADO GLOBAL
# ===============================
sinal_ativo = None
modo_atual = "CONSERVADOR"
bot_iniciado = False

modo_teste = True
teste_realizado = False
ativo_teste = "frxEURUSD"

last_ws_msg = time.time()
boot_time = time.time()

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
        send_telegram(
            f"🤖 <b>Troia-IA V17.1</b> ONLINE\n"
            f"🕒 {datetime.now(BR_TZ).strftime('%d/%m %H:%M')} (BR)"
        )
        bot_iniciado = True

# ===============================
# ESTRATÉGIA
# ===============================
def analisar_candles(candles):
    global modo_atual
    ult = candles[-6:]
    altas = sum(1 for c in ult if float(c["close"]) > float(c["open"]))
    baixas = 6 - altas

    corpos = [abs(float(c["close"]) - float(c["open"])) for c in ult]
    modo_atual = "AGRESSIVO" if sum(corpos)/6 > corpos[-1]*0.8 else "CONSERVADOR"

    if altas >= 4:
        return "CALL"
    if baixas >= 4:
        return "PUT"
    return None

def calcular_resultado(direcao, candle):
    o = float(candle["open"])
    cl = float(candle["close"])
    return "GREEN ✅" if (cl > o if direcao == "CALL" else cl < o) else "RED ❌"

# ===============================
# WEBSOCKET
# ===============================
def on_open(ws):
    global last_ws_msg
    last_ws_msg = time.time()
    iniciar_bot()

    for ativo in ATIVOS:
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": 20
        }))
        time.sleep(0.25)

def on_message(ws, msg):
    global sinal_ativo, modo_teste, teste_realizado, last_ws_msg
    last_ws_msg = time.time()

    data = json.loads(msg)
    if "candles" not in data:
        return

    ativo = data["echo_req"]["ticks_history"]
    candles = data["candles"]

    # ===============================
    # TESTE INICIAL (somente EURUSD)
    # ===============================
    if modo_teste and not teste_realizado and ativo == ativo_teste:
        if sinal_ativo is None:
            direcao = analisar_candles(candles)
            if not direcao:
                return

            sinal_ativo = {
                "ativo": ativo,
                "direcao": direcao,
                "teste": True
            }

            send_telegram(
                f"🧪 <b>TESTE DE INICIALIZAÇÃO</b>\n"
                f"📌 {ativo}\n"
                f"🎯 {direcao}\n"
                f"⏱️ M3"
            )
            return

        if sinal_ativo.get("teste") and ativo == sinal_ativo["ativo"]:
            res = calcular_resultado(sinal_ativo["direcao"], candles[-1])
            send_telegram(
                f"🧪 <b>RESULTADO DO TESTE</b>\n"
                f"📌 {ativo}\n"
                f"{res}"
            )
            sinal_ativo = None
            modo_teste = False
            teste_realizado = True
            send_telegram("✅ Teste concluído. Bot operando normalmente.")
            return

    # ===============================
    # FLUXO NORMAL
    # ===============================
    if sinal_ativo and ativo == sinal_ativo["ativo"]:
        res = calcular_resultado(sinal_ativo["direcao"], candles[-1])
        send_telegram(
            f"📊 <b>RESULTADO</b>\n"
            f"📌 {ativo}\n"
            f"🎯 {sinal_ativo['direcao']}\n"
            f"{res}"
        )
        sinal_ativo = None
        return

    if sinal_ativo:
        return

    direcao = analisar_candles(candles)
    if not direcao:
        return

    sinal_ativo = {"ativo": ativo, "direcao": direcao}
    send_telegram(
        f"📢 <b>SINAL M3</b>\n"
        f"📌 {ativo}\n"
        f"🎯 {direcao}\n"
        f"⚙️ Modo: {modo_atual}\n"
        f"🕒 {datetime.now(BR_TZ).strftime('%H:%M')}"
    )

def ws_loop():
    while True:
        try:
            ws = websocket.WebSocketApp(
                DERIV_WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=lambda w, e: None,
                on_close=lambda w, *a: None
            )
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except:
            pass
        time.sleep(5)

# ===============================
# WATCHDOG
# ===============================
def watchdog():
    while True:
        if time.time() - last_ws_msg > 150 and time.time() - boot_time > 120:
            send_telegram("⚠️ WebSocket inativo. Reiniciando serviço...")
            os._exit(1)
        time.sleep(30)

# ===============================
# HTTP
# ===============================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Troia-IA V17.1 ONLINE")

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=ws_loop, daemon=True).start()
    HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()
