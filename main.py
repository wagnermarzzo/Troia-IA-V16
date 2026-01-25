import websocket, json, time, requests, os, threading
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

# =====================================================
# BOOT LOG (PROVA DE VERSÃO)
# =====================================================
print("### SENTINEL RAILWAY-SAFE V1 INICIADO ###", flush=True)

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
NUM_CANDLES = 10
CONF_MIN = 48
HEARTBEAT = 20
BR_TZ = timezone(timedelta(hours=-3))

ANTECIPADO_DE = 40
ANTECIPADO_ATE = 58

# =====================================================
# ATIVOS
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

TICKS = {}

# =====================================================
# KEEP ALIVE HTTP (MAIN THREAD)
# =====================================================
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sentinel IA Online")

def start_http():
    port = int(os.environ.get("PORT", 8080))
    print(f"HTTP SERVER NA PORTA {port}", flush=True)
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
    ws = websocket.create_connection(
        "wss://ws.derivws.com/websockets/v3?app_id=1089",
        timeout=15
    )
    ws.send(json.dumps({"authorize": DERIV_API_KEY}))
    ws.recv()
    return ws

def heartbeat(ws):
    while True:
        try:
            ws.send(json.dumps({"ping": 1}))
            time.sleep(HEARTBEAT)
        except:
            break

# =====================================================
# SUBSCRIBE TICKS (PROTEGIDO)
# =====================================================
def subscrever_ticks():
    while True:
        try:
            ws = conectar_ws()
            threading.Thread(target=heartbeat, args=(ws,), daemon=True).start()

            for ativo in FOREX:
                ws.send(json.dumps({"ticks": ativo, "subscribe": 1}))

            print("✔ SUBSCRIÇÃO DE TICKS ATIVA", flush=True)

            while True:
                r = json.loads(ws.recv())
                if "tick" in r:
                    sym = r["tick"]["symbol"]
                    TICKS[sym] = (r["tick"]["quote"], r["tick"]["epoch"])
        except Exception as e:
            print("⚠ ERRO WS TICK → reconectando", e, flush=True)
            time.sleep(3)

# =====================================================
# CANDLES
# =====================================================
def pegar_candles(ws, ativo):
    try:
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": NUM_CANDLES,
            "end": "latest"
        }))
        r = json.loads(ws.recv())
        return r.get("candles")
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
    return "CALL" if altas > baixas else "PUT" if baixas > altas else None

def confianca(candles):
    call = sum(1 for c in candles if c["close"] > c["open"])
    put = len(candles) - call
    return int(max(call, put) / len(candles) * 100)

# =====================================================
# LOOP PRINCIPAL
# =====================================================
def loop():
    estados = {}
    ws_candle = conectar_ws()
    threading.Thread(target=heartbeat, args=(ws_candle,), daemon=True).start()

    tg_send("🚀 <b>SENTINEL IA ONLINE</b>\n🔥 Railway Safe • Ticks Reais")

    while True:
        for cod, nome in FOREX.items():
            if cod not in TICKS:
                continue

            preco_tick, epoch = TICKS[cod]
            vela_atual = epoch // 60
            sec = epoch % 60

            # limpa estados travados
            for k in list(estados.keys()):
                if vela_atual - estados[k]["vela_base"] > 3:
                    del estados[k]

            # PRÉ-SINAL
            if ANTECIPADO_DE <= sec <= ANTECIPADO_ATE and cod not in estados:
                candles = pegar_candles(ws_candle, cod)
                if not candles:
                    continue

                conf = confianca(candles)
                if conf < CONF_MIN:
                    continue

                ult = candles[-3:]
                if abs(
                    sum(1 for c in ult if c["close"] > c["open"]) -
                    sum(1 for c in ult if c["close"] < c["open"])
                ) == 0:
                    continue

                dirc = direcao(candles)
                if not dirc:
                    continue

                msg_id = tg_send(
                    f"📊 <b>PRÉ-SINAL</b>\n📌 {nome}\n🎯 {dirc}\n🧠 {conf}%"
                )

                estados[cod] = {
                    "fase": "ARMADO",
                    "dir": dirc,
                    "msg_id": msg_id,
                    "vela_base": vela_atual
                }

            # CONFIRMA
            if cod in estados and estados[cod]["fase"] == "ARMADO":
                if vela_atual > estados[cod]["vela_base"]:
                    candles = pegar_candles(ws_candle, cod)
                    conf = confianca(candles)
                    dirc = direcao(candles)

                    if conf < CONF_MIN or dirc != estados[cod]["dir"]:
                        tg_edit(estados[cod]["msg_id"], f"❌ <b>SINAL CANCELADO</b>\n📌 {nome}")
                        del estados[cod]
                        continue

                    estados[cod]["fase"] = "CONFIRMADO"
                    estados[cod]["preco_ent"] = preco_tick
                    tg_edit(estados[cod]["msg_id"], f"✅ <b>ENTRADA CONFIRMADA</b>\n📌 {nome}")

            # RESULTADO
            if cod in estados and estados[cod]["fase"] == "CONFIRMADO":
                if vela_atual > estados[cod]["vela_base"] + 1:
                    preco_fim, _ = TICKS.get(cod, (None, None))
                    ent = estados[cod]["preco_ent"]
                    dirc = estados[cod]["dir"]

                    res = (
                        "GREEN" if (preco_fim > ent and dirc == "CALL") or
                                   (preco_fim < ent and dirc == "PUT")
                        else "RED" if preco_fim != ent else "EMPATE"
                    )

                    tg_edit(
                        estados[cod]["msg_id"],
                        f"📊 <b>RESULTADO FINAL</b>\n📌 {nome}\n🏁 {res}"
                    )

                    del estados[cod]

        time.sleep(0.5)

# =====================================================
# START (RAILWAY SAFE)
# =====================================================
if __name__ == "__main__":
    threading.Thread(target=subscrever_ticks, daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    start_http()  # MAIN THREAD
