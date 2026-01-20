import websocket, json, time, requests

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
# TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode":"HTML"}, timeout=5
        )
    except:
        pass

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
# WS TESTE DEFINITIVO
# ===============================
def ws_teste():
    def on_open(ws):
        tg("🔄 WS aberto. Tentando autorização...")
        # Autorizar API Key
        ws.send(json.dumps({"authorize": DERIV_API_KEY}))

        # Timestamp UTC atual para o end
        end_timestamp = int(time.time())

        # Solicitar últimos 20 candles 1M
        ws.send(json.dumps({
            "ticks_history": ATIVO_TESTE,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": NUM_CANDLES_ANALISE,
            "end": end_timestamp
        }))

    def on_message(ws, msg):
        data = json.loads(msg)
        if "candles" in data:
            candles = data["candles"][-NUM_CANDLES_ANALISE:]
            direcao = direcao_candle(candles[-1])
            conf = calcular_confianca(candles)
            tg(f"✅ WS conectado corretamente!\nAtivo: {ATIVO_TESTE}\nÚltima direção: {direcao}\nConfiança últimos 20 candles: {conf}%\nTotal candles recebidos: {len(candles)}")
            ws.close()

    def on_error(ws, error):
        tg(f"❌ WS ERROR: {error}")

    def on_close(ws, *args):
        tg("🔄 WS fechado.")

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
tg("🤖 Teste WS definitivo com 'end' iniciado — frxEURUSD")
ws_teste()
