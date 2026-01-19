import os
import json
import time
import websocket
import requests
from datetime import datetime

# ================= CONFIG =================
DERIV_API_KEY = os.getenv("UEISANwBEI9sPVR")
TELEGRAM_TOKEN = os.getenv("8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU")
CHAT_ID = os.getenv("2055716345")

if not DERIV_API_KEY or not TELEGRAM_TOKEN or not CHAT_ID:
    raise Exception("Variáveis de ambiente não configuradas")

WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"
TIMEFRAME = 60

# ================= IA MEMÓRIA =================
pesos_ativos = {}
pesos_direcao = {"CALL": 1.0, "PUT": 1.0}
forca_minima = 0.65
conf_minima = 1.0

# ================= CONTROLE =================
sinal_ativo = False
ativo_atual = None
direcao_atual = None
preco_entrada = None
forca_ultima = None

# ================= ATIVOS =================
ATIVOS = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD",
    "R_10","R_25","R_50",
    "frxEURUSD_OTC","frxGBPUSD_OTC"
]

# ================= TELEGRAM =================
def send_telegram(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg},
        timeout=5
    )

# ================= IA =================
def analisar_vela(o, h, l, c):
    global forca_minima
    corpo = abs(c - o)
    total = h - l
    if total == 0:
        return None, None

    forca = corpo / total
    if forca < forca_minima:
        return None, None

    direcao = "CALL" if c > o else "PUT"
    return direcao, forca

def calcular_confianca(ativo, direcao, forca):
    peso_ativo = pesos_ativos.get(ativo, 1.0)
    peso_dir = pesos_direcao[direcao]
    return peso_ativo * peso_dir * forca

def reforcar(resultado):
    global forca_minima
    ajuste = 0.03 if resultado == "GREEN" else -0.05

    pesos_ativos[ativo_atual] = pesos_ativos.get(ativo_atual, 1.0) + ajuste
    pesos_direcao[direcao_atual] += ajuste

    forca_minima += -0.01 if resultado == "GREEN" else 0.02
    forca_minima = min(max(forca_minima, 0.55), 0.75)

# ================= WEBSOCKET =================
def on_open(ws):
    send_telegram("🟢 Troia IA conectada à Deriv")
    ws.send(json.dumps({"authorize": DERIV_API_KEY}))

def on_message(ws, message):
    global sinal_ativo, ativo_atual, direcao_atual, preco_entrada, forca_ultima

    data = json.loads(message)

    if "authorize" in data:
        send_telegram("🤖 IA ATIVA | Aprendizado ONLINE")
        for ativo in ATIVOS:
            ws.send(json.dumps({
                "ticks_history": ativo,
                "style": "candles",
                "granularity": TIMEFRAME,
                "count": 2
            }))
        return

    if "candles" in data and not sinal_ativo:
        vela = data["candles"][-2]
        o, h, l, c = map(float, [vela["open"], vela["high"], vela["low"], vela["close"]])

        direcao, forca = analisar_vela(o, h, l, c)
        if not direcao:
            return

        ativo = data["echo_req"]["ticks_history"]
        confianca = calcular_confianca(ativo, direcao, forca)

        if confianca < conf_minima:
            return

        sinal_ativo = True
        ativo_atual = ativo
        direcao_atual = direcao
        preco_entrada = c
        forca_ultima = forca

        send_telegram(
            f"🧠 SINAL IA\nAtivo: {ativo}\nDireção: {direcao}\n"
            f"Força: {forca:.2f}\nConfiança: {confianca:.2f}\n"
            f"Entrada: PRÓXIMA VELA (1M)"
        )

        ws.send(json.dumps({"ticks": ativo, "subscribe": 1}))

    if "tick" in data and sinal_ativo:
        preco = float(data["tick"]["quote"])
        resultado = "GREEN" if (
            (direcao_atual == "CALL" and preco > preco_entrada) or
            (direcao_atual == "PUT" and preco < preco_entrada)
        ) else "RED"

        send_telegram(f"📊 RESULTADO IA: {resultado}")
        reforcar(resultado)

        sinal_ativo = False

def on_error(ws, error):
    send_telegram(f"⚠️ Erro WS: {error}")

def on_close(ws, code, msg):
    send_telegram("🔄 Reconectando IA...")
    time.sleep(5)
    start_ws()

def start_ws():
    websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    ).run_forever(ping_interval=30, ping_timeout=10)

# ================= MAIN =================
if __name__ == "__main__":
    send_telegram("🚀 Troia IA iniciado")
    start_ws()
