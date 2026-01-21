import json, time, requests, csv, os, threading
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import websocket

# ===============================
# CONFIGURAÇÃO
# ===============================
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 300
CONF_MIN = 55
PROB_MIN = 70
WAIT_BUFFER = 10
RECONNECT_DELAY = 5

LOG_FILE = "sinais_log.csv"
ERROR_LOG = "error_log.txt"

sinal_em_analise = threading.Lock()

# ===============================
# ATIVOS
# ===============================
ATIVOS_FOREX = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD",
    "frxUSDCAD","frxUSDCHF","frxNZDUSD","frxEURGBP",
    "frxEURJPY","frxEURCHF","frxEURAUD","frxEURCAD",
    "frxEURNZD","frxGBPJPY","frxGBPCHF","frxGBPAUD",
    "frxGBPCAD","frxGBPNZD","frxAUDJPY","frxAUDNZD",
    "frxAUDCAD","frxAUDCHF","frxCADJPY","frxCADCHF",
    "frxCHFJPY","frxNZDJPY","frxNZDCAD","frxNZDCHF"
]

ATIVOS_OTC = [
    "frxUSDTRY","frxUSDRUB","frxUSDZAR","frxUSDMXN",
    "frxUSDHKD","frxUSDKRW","frxUSDSEK","frxUSDNOK",
    "frxUSDDKK","frxUSDPLN","frxUSDHUF"
]

ATIVOS = ATIVOS_FOREX + ATIVOS_OTC

# ===============================
# LOG
# ===============================
def log_error(msg):
    with open(ERROR_LOG, "a") as f:
        f.write(f"{datetime.utcnow()} - {msg}\n")
    print(msg)

# ===============================
# TELEGRAM (INALTERADO)
# ===============================
def enviar_sinal(ativo, direcao, confianca, estrategia, entrada="Próxima vela", resultado=None):
    try:
        msg = (
            f"💥 <b>SENTINEL IA – SINAL ENCONTRADO</b>\n"
            f"📊 <b>Ativo:</b> {ativo}\n"
            f"🎯 <b>Direção:</b> {direcao}\n"
            f"🧠 <b>Estratégia:</b> {estrategia}\n"
            f"⏱️ <b>Entrada:</b> {entrada}\n"
            f"🧮 <b>Confiança:</b> {confianca}%\n"
        )
        if resultado:
            msg += f"✅ <b>Resultado:</b> {'🟢 Green' if resultado=='Green' else '🔴 Red'}"

        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except Exception as e:
        log_error(f"Telegram erro: {e}")

# ===============================
# FUNÇÕES DE ANÁLISE (INALTERADAS)
# ===============================
def direcao_candle(c): return "CALL" if c["close"] > c["open"] else "PUT"

def calcular_confianca(candles):
    if not candles: return 0
    call = sum(1 for c in candles if c["close"] > c["open"])
    put  = len(candles) - call
    return int(max(call, put) / len(candles) * 100)

def direcao_confirmada(candles, n=3):
    ult = candles[-n:]
    if all(c["close"] > c["open"] for c in ult): return "CALL"
    if all(c["close"] < c["open"] for c in ult): return "PUT"
    return None

def tendencia_medio_prazo(candles, p=20):
    return "CALL" if candles[-1]["close"] > candles[-p]["close"] else "PUT"

def candle_valido(c, min_pct=0.0003):
    return abs(c["close"] - c["open"]) / c["open"] >= min_pct

def probabilidade_real(candles, d):
    return int(sum(1 for c in candles if direcao_candle(c) == d) / len(candles) * 100)

def proxima_vela_horario():
    now = datetime.now(timezone.utc)
    nxt = now + timedelta(seconds=TIMEFRAME - now.timestamp() % TIMEFRAME)
    return nxt.strftime("%H:%M:%S UTC")

# ===============================
# KEEP ALIVE (RAILWAY)
# ===============================
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_http():
    HTTPServer(("0.0.0.0", int(os.getenv("PORT", 8080))), Health).serve_forever()

threading.Thread(target=start_http, daemon=True).start()

# ===============================
# WEBSOCKET CORRIGIDO
# ===============================
DERIV_WS = "wss://ws.deriv.com/websockets/v3?app_id=1089"
candles_cache = {}

def on_message(ws, msg):
    data = json.loads(msg)
    if "candles" in data:
        ativo = data["echo_req"]["ticks_history"]
        candles_cache[ativo] = data["candles"]

def on_open(ws):
    for ativo in ATIVOS:
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": 50,
            "adjust_start_time": 1
        }))

def start_ws():
    websocket.WebSocketApp(
        DERIV_WS,
        on_open=on_open,
        on_message=on_message
    ).run_forever(ping_interval=30, ping_timeout=10)

threading.Thread(target=start_ws, daemon=True).start()

# ===============================
# LOOP PRINCIPAL (INALTERADO)
# ===============================
def loop_ativos_final():
    enviar_sinal("N/A","N/A",0,"Iniciando Bot Sentinel IA – Produção")
    cooldowns = {a:0 for a in ATIVOS}
    ultimo = {}

    while True:
        for ativo, candles in candles_cache.items():
            if time.time() < cooldowns.get(ativo, 0): continue
            if len(candles) < 20: continue

            direcao = direcao_confirmada(candles)
            if not direcao or not candle_valido(candles[-1]): continue

            confianca = calcular_confianca(candles[-20:])
            if direcao != tendencia_medio_prazo(candles): continue

            min_conf = CONF_MIN + (15 if ativo in ATIVOS_OTC else 0)
            if confianca < min_conf: continue
            if probabilidade_real(candles, direcao) < PROB_MIN: continue
            if ultimo.get(ativo) == direcao: continue

            if sinal_em_analise.acquire(False):
                horario = proxima_vela_horario()
                enviar_sinal(
                    ativo, direcao, confianca,
                    "Price Action + Suportes/Resistências + Probabilidade Avançada",
                    entrada=f"Agora ({horario})"
                )

                threading.Timer(
                    TIMEFRAME + WAIT_BUFFER,
                    sinal_em_analise.release
                ).start()

                cooldowns[ativo] = time.time() + TIMEFRAME
                ultimo[ativo] = direcao

        time.sleep(0.5)

# ===============================
# START
# ===============================
while True:
    try:
        loop_ativos_final()
    except Exception as e:
        log_error(f"[FATAL] {e}")
        time.sleep(RECONNECT_DELAY)
