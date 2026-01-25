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
CONF_MIN = 55
HEARTBEAT = 25
BR_TZ = timezone(timedelta(hours=-3))

ANTECIPADO_DE = 52
ANTECIPADO_ATE = 58

# =====================================================
# ATIVOS FOREX REAL
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
            time.sleep(5)

def heartbeat(ws):
    while True:
        try:
            ws.send(json.dumps({"ping": 1}))
            time.sleep(HEARTBEAT)
        except:
            break

def pegar_candles(ws, ativo):
    try:
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": NUM_CANDLES,
            "end": "latest"
        }))
        return json.loads(ws.recv()).get("candles")
    except:
        return None

def pegar_tick(ws, ativo):
    try:
        ws.send(json.dumps({"ticks": ativo}))
        r = json.loads(ws.recv())
        return r["tick"]["quote"], r["tick"]["epoch"]
    except:
        return None, None

def agora():
    return datetime.now(BR_TZ).strftime("%H:%M:%S")

# =====================================================
# ANÁLISE
# =====================================================
def direcao(candles):
    ult = candles[-5:]
    altas = sum(1 for c in ult if c["close"] > c["open"])
    baixas = sum(1 for c in ult if c["close"] < c["open"])
    return "CALL" if altas > baixas else "PUT" if baixas > altas else None

def confianca(candles):
    call = sum(1 for c in candles if c["close"] > c["open"])
    put = len(candles) - call
    return int(max(call, put) / len(candles) * 100)

# =====================================================
# LOOP PRINCIPAL (ESTÁVEL)
# =====================================================
def loop():
    estados = {}
    online_enviado = False

    ws = conectar_ws()
    Thread(target=heartbeat, args=(ws,), daemon=True).start()

    if not online_enviado:
        tg_send("🏆 <b>SENTINEL IA ONLINE</b>\n📡 Forex REAL • Tick real")
        online_enviado = True

    while True:
        for cod, nome in FOREX.items():
            preco_tick, epoch = pegar_tick(ws, cod)
            if not epoch:
                continue

            vela_atual = epoch // 60
            sec = epoch % 60

            # ========= PRÉ-SINAL =========
            if ANTECIPADO_DE <= sec <= ANTECIPADO_ATE and cod not in estados:
                candles = pegar_candles(ws, cod)
                if not candles or len(candles) < NUM_CANDLES:
                    continue

                conf = confianca(candles)
                if conf < CONF_MIN:
                    continue

                dirc = direcao(candles)
                if not dirc:
                    continue

                msg_id = tg_send(
                    f"📊 <b>PRÉ-SINAL</b>\n📌 {nome}\n🎯 {dirc}\n🕒 {agora()}\n🧠 {conf}%"
                )

                estados[cod] = {
                    "fase": "ARMADO",
                    "dir": dirc,
                    "msg_id": msg_id,
                    "vela_base": vela_atual
                }

            # ========= CONFIRMAÇÃO =========
            if cod in estados and estados[cod]["fase"] == "ARMADO":
                if vela_atual > estados[cod]["vela_base"]:
                    candles = pegar_candles(ws, cod)
                    if not candles:
                        continue

                    conf = confianca(candles)
                    dirc = direcao(candles)

                    if conf < CONF_MIN or dirc != estados[cod]["dir"]:
                        tg_edit(estados[cod]["msg_id"], f"❌ <b>SINAL CANCELADO</b>\n📌 {nome}")
                        del estados[cod]
                        continue

                    estados[cod]["fase"] = "CONFIRMADO"
                    estados[cod]["preco_ent"] = preco_tick

                    tg_edit(estados[cod]["msg_id"], f"✅ <b>ENTRADA CONFIRMADA</b>\n📌 {nome}")

            # ========= RESULTADO =========
            if cod in estados and estados[cod]["fase"] == "CONFIRMADO":
                if vela_atual > estados[cod]["vela_base"] + 1:
                    preco_fim, _ = pegar_tick(ws, cod)
                    if not preco_fim:
                        continue

                    ent = estados[cod]["preco_ent"]
                    dirc = estados[cod]["dir"]

                    res = (
                        "GREEN" if (preco_fim > ent and dirc == "CALL") or
                                   (preco_fim < ent and dirc == "PUT")
                        else "RED" if preco_fim != ent else "EMPATE"
                    )

                    tg_edit(estados[cod]["msg_id"],
                            f"📊 <b>RESULTADO FINAL</b>\n📌 {nome}\n🏁 {res}")

                    del estados[cod]

        time.sleep(0.6)

# =====================================================
# START
# =====================================================
if __name__ == "__main__":
    threading.Thread(target=start_http, daemon=True).start()
    loop()
