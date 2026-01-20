import websocket, json, time, requests
from datetime import datetime, timedelta, timezone

# ===============================
# CONFIGURAÇÃO FIXA
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"
CONF_MIN = 55
TIMEFRAME = 60  # 1 minuto
NUM_CANDLES_ANALISE = 20  # últimos 20 candles

# ===============================
# LISTA COMPLETA DE ATIVOS
# ===============================
ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxUSDCHF","frxAUDUSD",
    "frxNZDUSD","frxUSDCAD","frxEURJPY","frxGBPJPY","frxEURGBP",
    "frxEURAUD","frxEURCHF","frxAUDJPY","frxCADJPY","frxCHFJPY",
    "frxNZDJPY","R_10","R_25","R_50","R_75","R_100"
]

# ===============================
# ESTADO GLOBAL
# ===============================
estado = {"ativo": None, "direcao": None, "entrada": None, "aguardando_resultado": False}

# ===============================
# FUNÇÕES TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID,"text":msg,"parse_mode":"HTML"}, timeout=5)
    except: pass

# ===============================
# PAINEL PROFISSIONAL
# ===============================
def painel(ativo,direcao,hora,conf):
    return f"""
🚨 <b>SINAL ENCONTRADO</b>
📊 <b>Ativo:</b> {ativo}
📈 <b>Direção:</b> {direcao}
⏱ <b>Timeframe:</b> 1M
🧠 <b>Estratégia:</b> Price Action
⏰ <b>Entrada:</b> Próxima vela ({hora})
📊 <b>Confiança:</b> {conf}%
"""

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
    return max(CONF_MIN, int(maior/total*100))

# ===============================
# WS RESULTADO
# ===============================
def ws_resultado(ativo,direcao):
    while True:
        try:
            def on_open(ws):
                ws.send(json.dumps({"authorize":DERIV_API_KEY}))

            def on_message(ws,msg):
                data = json.loads(msg)
                if "candles" not in data: return
                c = data["candles"][-1]
                green = (direcao=="CALL" and c["close"]>c["open"]) or (direcao=="PUT" and c["close"]<c["open"])
                tg(f"{'💸 GREEN' if green else '🧨 RED'} — {ativo}")
                # Reset estado
                estado["ativo"]=None
                estado["direcao"]=None
                estado["entrada"]=None
                estado["aguardando_resultado"]=False
                ws.close()

            def on_close(ws,*args):
                time.sleep(5)

            def on_error(ws,error):
                time.sleep(3)

            ws = websocket.WebSocketApp(
                "wss://ws.derivws.com/websockets/v3?app_id=1089",
                on_open=on_open,
                on_message=on_message,
                on_close=on_close,
                on_error=on_error)
            ws.run_forever()
        except:
            time.sleep(5)

# ===============================
# WS ANALISE ATIVO
# ===============================
def ws_analise_ativo(ativo):
    while True:
        if estado["aguardando_resultado"]:
            time.sleep(1)
            continue
        try:
            def on_open(ws):
                ws.send(json.dumps({"authorize":DERIV_API_KEY}))
                ws.send(json.dumps({
                    "ticks_history":ativo,
                    "style":"candles",
                    "count":NUM_CANDLES_ANALISE,
                    "granularity":TIMEFRAME
                }))

            def on_message(ws,msg):
                data = json.loads(msg)
                if "candles" not in data or estado["aguardando_resultado"]: return
                candles = data["candles"][-NUM_CANDLES_ANALISE:]
                conf = calcular_confianca(candles)
                if conf<CONF_MIN:
                    ws.close()
                    return
                # Preencher estado e lock
                estado["ativo"]=ativo
                estado["direcao"]=direcao_candle(candles[-1])
                estado["aguardando_resultado"]=True
                agora=datetime.now(timezone.utc)
                entrada=(agora+timedelta(minutes=1)).replace(second=0,microsecond=0)
                estado["entrada"]=entrada
                # Enviar sinal 5 segundos antes da próxima vela
                envio=entrada-timedelta(seconds=5)
                while datetime.now(timezone.utc)<envio: time.sleep(0.2)
                tg(painel(ativo,estado["direcao"],entrada.strftime("%H:%M:%S"),conf))
                # Esperar fechamento da vela
                fechamento=entrada+timedelta(minutes=1)
                while datetime.now(timezone.utc)<fechamento: time.sleep(0.5)
                ws_resultado(ativo,estado["direcao"])
                ws.close()

            def on_close(ws,*args):
                time.sleep(5)

            def on_error(ws,error):
                time.sleep(3)

            ws=websocket.WebSocketApp(
                "wss://ws.derivws.com/websockets/v3?app_id=1089",
                on_open=on_open,
                on_message=on_message,
                on_close=on_close,
                on_error=on_error)
            ws.run_forever()
        except:
            time.sleep(5)

# ===============================
# START
# ===============================
tg("🤖 <b>Troia IA ONLINE</b>\n📡 Mercado REAL Deriv\n⏱ Timeframe 1M\n💡 Análise últimos 20 candles, CONF_MIN 55")

while True:
    for ativo in ATIVOS:
        ws_analise_ativo(ativo)  # ⚡ 1 ativo por vez → envia sinal e aguarda resultado antes de passar para o próximo
