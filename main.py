import websocket, json, time, requests

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"
ATIVO_TESTE = "frxEURUSD"  # Teste 1 ativo

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
# WS TESTE CONEXÃO
# ===============================
def ws_teste():
    def on_open(ws):
        tg("🔄 WS aberto. Tentando autorização...")
        # Autorizar API Key
        ws.send(json.dumps({"authorize": DERIV_API_KEY}))
        # Pedir ticks_history para 1 candle apenas (teste)
        ws.send(json.dumps({
            "ticks_history": ATIVO_TESTE,
            "style": "candles",
            "count": 1,
            "granularity": 60
        }))

    def on_message(ws, msg):
        tg(f"✅ WS respondeu:\n{msg}")
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
tg("🤖 Teste WS definitivo iniciado — frxEURUSD")
ws_teste()
