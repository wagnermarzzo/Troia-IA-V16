import websocket, json, time, requests
from datetime import datetime, timezone

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

ATIVOS = [
    "frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD",
    "frxUSDCAD", "frxUSDCHF", "frxNZDUSD", "frxEURGBP"
]  # Lista de ativos reais

NUM_CANDLES_ANALISE = 20
TIMEFRAME = 60  # 1M
CONF_MIN = 55  # confiança mínima para enviar sinal
WAIT_AFTER_VELA = 65  # espera 1m05s para ler resultado

# ===============================
# TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode":"HTML"}, timeout=5
        )
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
# ANALISA 1 ATIVO
# ===============================
def analisar_ativo(ativo):
    resultado_final = {"ativo": ativo, "sinal_enviado": False}

    def on_open(ws):
        ws.send(json.dumps({"authorize": DERIV_API_KEY}))
        end_timestamp = int(time.time())
        ws.send(json.dumps({
            "ticks_history": ativo,
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

            # Sinal apenas se confiança ≥ CONF_MIN
            if conf >= CONF_MIN:
                tg(f"💥 SINAL ENCONTRADO!\n"
                   f"Ativo: {ativo}\n"
                   f"Direção: {direcao}\n"
                   f"Confiança: {conf}%\n"
                   f"Timeframe: 1M\n"
                   f"Entrada: próxima vela")
                resultado_final["sinal_enviado"] = True
                resultado_final["direcao"] = direcao

            ws.close()

    def on_error(ws, error):
        tg(f"❌ WS ERROR: {error}")
        resultado_final["sinal_enviado"] = False

    def on_close(ws, *args):
        pass

    ws = websocket.WebSocketApp(
        "wss://ws.derivws.com/websockets/v3?app_id=1089",
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error
    )
    ws.run_forever()
    return resultado_final

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop_ativos():
    tg("🤖 Troia V19 PRO FINAL iniciado. Analise 1 ativo por vez.")
    while True:
        for ativo in ATIVOS:
            res = analisar_ativo(ativo)
            if res.get("sinal_enviado"):
                # Espera 1 vela fechar antes de passar para o próximo ativo
                time.sleep(WAIT_AFTER_VELA)
                # Confirmação resultado 💸 / 🧨
                tg(f"🧾 RESULTADO SINAL {res['ativo']}: {res['direcao']} (verificar candle real)")
            else:
                # Nenhum sinal → passa para próximo ativo
                time.sleep(2)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    loop_ativos()
