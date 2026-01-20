import websocket, json, time, requests
from datetime import datetime, timedelta, timezone

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"
ATIVO_TESTE = "frxEURUSD"  # Teste 1 ativo
NUM_CANDLES_ANALISE = 20
TIMEFRAME = 60  # 1M

# ===============================
# FUNÇÃO TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID,"text":msg,"parse_mode":"HTML"}, timeout=5)
    except: pass

# ===============================
# DIREÇÃO E CONFIANÇA
# ===============================
def direcao_candle(candle):
    return "CALL" if candle["close"] > candle["open"] else "PUT"

def calcular_confianca(candles):
    call = sum(1 for c in candles if c["close"] > c["open"])
    put = sum(1 for c in candles if c["close"] < c["open"])
    total = len(candles)
    maior = max(call, put)
    return int(maior/total*100)

# ===============================
# WS TESTE
# ===============================
def ws_teste():
    def on_open(ws):
        ws.send(json.dumps({"authorize": DERIV_API_KEY}))
        ws.send(json.dumps({
            "ticks_history": ATIVO_TESTE,
            "style": "candles",
            "count": NUM_CANDLES_ANALISE,
            "granularity": TIMEFRAME
        }))

    def on_message(ws, msg):
        data = json.loads(msg)
        if "candles" in data:
            candles = data["candles"][-NUM_CANDLES_ANALISE:]
            direcao = direcao_candle(candles[-1])
            conf = calcular_confianca(candles)
            agora = datetime.now(timezone.utc)
            tg(f"✅ WS conectado!\nAtivo: {ATIVO_TESTE}\nÚltima direção: {direcao}\nConfiança últimos 20 candles: {conf}%\nHora UTC: {agora.strftime('%H:%M:%S')}")
            ws.close()

    def on_error(ws, error):
        tg(f"❌ WS ERROR: {error}")
        time.sleep(5)

    def on_close(ws, *args):
        tg("🔄 WS fechado ou finalizado.")

    ws = websocket.WebSocketApp(
        "wss://ws.derivws.com/websockets/v3?app_id=1089",
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error
    )
    ws.run_forever()

# ===============================
# START
# ===============================
tg("🤖 Teste WS iniciado — frxEURUSD")
ws_teste()
