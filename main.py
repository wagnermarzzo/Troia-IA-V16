import websocket
import json
import time
import requests
import threading
from datetime import datetime, timezone, timedelta
import os

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

TIMEFRAME = 60  # M1
BR_TZ = timezone(timedelta(hours=-3))

# Ativos FOREX + OTC
ATIVOS_FOREX = [
    "frxEURUSD","frxGBPUSD","frxUSDJPY","frxAUDUSD","frxUSDCAD",
    "frxUSDCHF","frxEURJPY","frxGBPJPY","frxEURGBP","frxAUDJPY"
]

ATIVOS_OTC = [
    "frxEURUSD_otc","frxGBPUSD_otc","frxUSDJPY_otc",
    "frxAUDUSD_otc","frxUSDCAD_otc"
]

# ===============================
# ESTADO GLOBAL
# ===============================
ativo_index = 0
ativo_atual = None
sinal_aberto = False
direcao_sinal = None
ultimo_epoch = None
modo = "CONSERVADOR"
ws = None
cooldown_ativos = {}  # Epoch do último sinal por ativo
bot_iniciado = False
ultima_mensagem_heartbeat = 0

# ===============================
# TELEGRAM
# ===============================
def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=5
        )
    except:
        pass

def heartbeat():
    global ultima_mensagem_heartbeat
    while True:
        agora = time.time()
        if agora - ultima_mensagem_heartbeat > 1800:  # 30 min
            send_telegram("💓 Bot vivo | TROIA-IA M1")
            ultima_mensagem_heartbeat = agora
        time.sleep(60)

# ===============================
# MERCADO / ATIVOS
# ===============================
def mercado_atual():
    agora = datetime.now(BR_TZ)
    return "OTC" if agora.weekday() >= 5 else "FOREX"

def ativos_em_uso():
    return ATIVOS_OTC if mercado_atual() == "OTC" else ATIVOS_FOREX

def atualizar_ativo():
    global ativo_index, ativo_atual
    ativos = ativos_em_uso()
    ativo_index = (ativo_index + 1) % len(ativos)
    ativo_atual = ativos[ativo_index]

# ===============================
# INICIALIZAÇÃO
# ===============================
def iniciar_bot():
    global bot_iniciado
    atualizar_ativo()
    hora = datetime.now(BR_TZ).strftime("%d/%m %H:%M")
    if not bot_iniciado:
        send_telegram(
            f"🤖 <b>TROIA-IA M1 ONLINE</b>\n"
            f"⏱️ M1 | Mercado REAL\n"
            f"🧭 Mercado: {mercado_atual()}\n"
            f"📊 Ativos: {len(ativos_em_uso())}\n"
            f"🕒 {hora} (BR)"
        )
        send_telegram(
            "🧪 <b>SINAL TESTE</b>\nSistema operacional. Aguardando fechamento do candle M1."
        )
        bot_iniciado = True

# ===============================
# ESTRATÉGIA SIMPLES
# ===============================
def analisar(candle):
    corpo = abs(candle["close"] - candle["open"])
    if modo == "CONSERVADOR" and corpo < 0.00002:
        return None
    return "CALL" if candle["close"] > candle["open"] else "PUT"

# ===============================
# PROCESSAMENTO
# ===============================
def processar_candle(candle):
    global sinal_aberto, direcao_sinal, modo, cooldown_ativos

    # Cooldown ativo
    if ativo_atual in cooldown_ativos:
        if time.time() - cooldown_ativos[ativo_atual] < 60:  # 1 min
            atualizar_ativo()
            solicitar_candles()
            return

    # Resultado
    if sinal_aberto:
        green = (direcao_sinal == "CALL" and candle["close"] > candle["open"]) or \
                (direcao_sinal == "PUT" and candle["close"] < candle["open"])
        send_telegram(
            f"{'🟢' if green else '🔴'} <b>RESULTADO</b>\n"
            f"📌 {ativo_atual}\n"
            f"🎯 {direcao_sinal}\n"
            f"📊 <b>{'GREEN' if green else 'RED'}</b>"
        )
        modo = "AGRESSIVO" if green else "CONSERVADOR"
        sinal_aberto = False
        direcao_sinal = None
        cooldown_ativos[ativo_atual] = time.time()
        atualizar_ativo()
        solicitar_candles()
        return

    # Novo sinal
    direcao = analisar(candle)
    if direcao:
        sinal_aberto = True
        direcao_sinal = direcao
        hora = datetime.now(BR_TZ).strftime("%H:%M")
        send_telegram(
            f"📊 <b>SINAL M1</b>\n"
            f"📌 {ativo_atual}\n"
            f"🎯 <b>{direcao}</b>\n"
            f"🕒 {hora}\n"
            f"⚙️ Modo: {modo}"
        )
        return

    # Sem sinal → próximo ativo
    atualizar_ativo()
    solicitar_candles()

# ===============================
# WEBSOCKET
# ===============================
def solicitar_candles():
    ws.send(json.dumps({
        "ticks_history": ativo_atual,
        "style": "candles",
        "granularity": TIMEFRAME,
        "count": 2
    }))

def on_message(ws_, msg):
    global ultimo_epoch
    data = json.loads(msg)
    if "candles" not in data:
        return
    candle = data["candles"][-1]
    candle["open"] = float(candle["open"])
    candle["close"] = float(candle["close"])
    if candle["epoch"] == ultimo_epoch:
        return
    ultimo_epoch = candle["epoch"]
    processar_candle(candle)

def on_open(ws_):
    global ws
    ws = ws_
    iniciar_bot()
    solicitar_candles()

def on_error(ws_, err):
    print("WS ERRO:", err)

def on_close(ws_, *a):
    print("⚠️ WebSocket fechado. Reconectando em 5s...")
    time.sleep(5)

# ===============================
# THREAD WS
# ===============================
def ws_loop():
    while True:
        try:
            websocket.enableTrace(False)
            ws_app = websocket.WebSocketApp(
                DERIV_WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws_app.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as e:
            print("Erro WS:", e)
            time.sleep(5)

# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    threading.Thread(target=heartbeat, daemon=True).start()
    ws_loop()
