import websocket
import json
import time
import threading
import requests
from datetime import datetime, timedelta, timezone

# ===============================
# CONFIGURAÇÃO FIXA
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

CONF_MIN = 60
TIMEFRAME = 60  # 1 minuto

# ===============================
# LISTA DE ATIVOS (Deriv + OTC)
# ===============================
ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxUSDCHF",
    "frxAUDUSD","frxNZDUSD","frxUSDCAD","frxEURJPY",
    "frxGBPJPY","frxEURGBP","frxEURAUD","frxEURCHF",
    "frxAUDJPY","frxCADJPY","frxCHFJPY","frxNZDJPY",
    "R_10","R_25","R_50","R_75","R_100"
]

# ===============================
# ESTADO GLOBAL
# ===============================
estado = {
    "ativo": None,
    "direcao": None,
    "entrada": None,
    "aguardando_resultado": False
}

ULTIMO_STATUS = 0

# ===============================
# TELEGRAM
# ===============================
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except:
        pass

def tg_log(msg):
    tg(f"🖥 <b>LOG:</b> {msg}")
    print(msg)

# ===============================
# PAINEL PROFISSIONAL
# ===============================
def painel(ativo, direcao, hora, conf):
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
# FUNÇÕES DE CANDLE
# ===============================
def direcao_candle(c):
    return "CALL" if c["close"] > c["open"] else "PUT"

def calcular_confianca(c):
    return min(85, max(55, int(abs(c["close"] - c["open"]) * 10000)))

# ===============================
# WS RESULTADO
# ===============================
def ws_resultado():
    while True:
        try:
            def on_open(ws):
                tg_log("WS Resultado conectado")
                ws.send(json.dumps({"authorize": DERIV_API_KEY}))

            def on_message(ws, msg):
                data = json.loads(msg)
                if "candles" not in data:
                    return

                c = data["candles"][-1]
                ativo = estado["ativo"]
                direcao = estado["direcao"]

                green = (
                    (direcao == "CALL" and c["close"] > c["open"]) or
                    (direcao == "PUT" and c["close"] < c["open"])
                )

                tg(f"{'💸 GREEN' if green else '🧨 RED'} — {ativo}")

                estado["ativo"] = None
                estado["direcao"] = None
                estado["entrada"] = None
                estado["aguardando_resultado"] = False

                ws.close()

            def on_close(ws, close_status_code=None, close_msg=None):
                tg_log("WS Resultado caiu, reconectando em 5s...")
                time.sleep(5)

            def on_error(ws, error):
                tg_log(f"WS Resultado erro: {error}")

            ws = websocket.WebSocketApp(
                "wss://ws.derivws.com/websockets/v3?app_id=1089",
                on_open=on_open,
                on_message=on_message,
                on_close=on_close,
                on_error=on_error
            )
            ws.run_forever()
        except Exception as e:
            tg_log(f"Erro WS Resultado, reconectando: {e}")
            time.sleep(5)

# ===============================
# WS ANALISE
# ===============================
def ws_analise():
    global ULTIMO_STATUS
    while True:
        try:
            def on_open(ws):
                tg_log("WS Análise conectado")
                ws.send(json.dumps({"authorize": DERIV_API_KEY}))
                for a in ATIVOS:
                    ws.send(json.dumps({
                        "ticks_history": a,
                        "style": "candles",
                        "count": 10,
                        "granularity": TIMEFRAME
                    }))

            def on_message(ws, msg):
                global ULTIMO_STATUS
                data = json.loads(msg)
                if "candles" not in data or estado["aguardando_resultado"]:
                    return

                ativo = data["echo_req"]["ticks_history"]
                candle = data["candles"][-1]

                conf = calcular_confianca(candle)
                if conf < CONF_MIN:
                    agora = time.time()
                    if agora - ULTIMO_STATUS > 300:
                        tg("🔍 <b>Analisando mercado, aguarde...</b>")
                        ULTIMO_STATUS = agora
                    return

                estado["ativo"] = ativo
                estado["direcao"] = direcao_candle(candle)
                estado["aguardando_resultado"] = True

                agora = datetime.now(timezone.utc)
                entrada = (agora + timedelta(minutes=1)).replace(second=0, microsecond=0)
                estado["entrada"] = entrada

                envio = entrada - timedelta(seconds=5)
                while datetime.now(timezone.utc) < envio:
                    time.sleep(0.2)

                tg(painel(ativo, estado["direcao"], entrada.strftime("%H:%M:%S"), conf))

                fechamento = entrada + timedelta(minutes=1)
                while datetime.now(timezone.utc) < fechamento:
                    time.sleep(0.5)

                threading.Thread(target=ws_resultado).start()

            def on_close(ws, close_status_code=None, close_msg=None):
                tg_log("WS Análise caiu, reconectando em 5s...")
                time.sleep(5)

            def on_error(ws, error):
                tg_log(f"WS Análise erro: {error}")

            ws = websocket.WebSocketApp(
                "wss://ws.derivws.com/websockets/v3?app_id=1089",
                on_open=on_open,
                on_message=on_message,
                on_close=on_close,
                on_error=on_error
            )
            ws.run_forever()
        except Exception as e:
            tg_log(f"Erro WS Análise, reconectando: {e}")
            time.sleep(5)

# ===============================
# START
# ===============================
tg("🤖 <b>Troia IA ONLINE</b>\n📡 Mercado REAL Deriv\n⏱ Timeframe 1M")
threading.Thread(target=ws_analise).start()
