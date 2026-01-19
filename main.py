import websocket
import json
import time
import threading
import requests
from datetime import datetime

# ===============================
# CONFIGURAÇÃO FIXA (NÃO MUDA)
# ===============================
DERIV_API_KEY = "UEISANwBEI9sPVR"

TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
CHAT_ID = "2055716345"

TIMEFRAME = 60  # 1 minuto
ANALISE_INTERVALO = 15  # segundos

# ===============================
# LISTA COMPLETA DE ATIVOS DERIV
# ===============================
ATIVOS = [
    # Forex
    "frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD",
    "frxUSDCAD", "frxUSDCHF", "frxEURGBP", "frxEURJPY",

    # OTC
    "OTC_EURUSD", "OTC_GBPUSD", "OTC_USDJPY",
    "OTC_AUDUSD", "OTC_USDCAD", "OTC_USDCHF",
]

# ===============================
# CONTROLE GLOBAL
# ===============================
sinal_ativo = False
resultado_pendente = None
historico = []

# ===============================
# TELEGRAM
# ===============================
def enviar_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, json=payload)

# ===============================
# GERAR SINAL (SIMPLIFICADO)
# ===============================
def gerar_sinal():
    global sinal_ativo, resultado_pendente

    if sinal_ativo:
        return

    ativo = ATIVOS[int(time.time()) % len(ATIVOS)]
    direcao = "CALL" if int(time.time()) % 2 == 0 else "PUT"

    sinal_ativo = True
    resultado_pendente = {
        "ativo": ativo,
        "direcao": direcao,
        "hora": datetime.now()
    }

    msg = (
        f"📊 SINAL GERADO\n\n"
        f"Ativo: {ativo}\n"
        f"Direção: {direcao}\n"
        f"⏱ Timeframe: 1M\n"
        f"🕒 Entrada para a PRÓXIMA vela"
    )

    enviar_telegram(msg)

# ===============================
# SIMULA RESULTADO (WIN / LOSS)
# ===============================
def verificar_resultado():
    global sinal_ativo, resultado_pendente

    if not sinal_ativo:
        return

    time.sleep(TIMEFRAME)

    resultado = "GREEN" if int(time.time()) % 2 == 0 else "RED"

    historico.append(resultado)

    enviar_telegram(
        f"📌 RESULTADO\n"
        f"Ativo: {resultado_pendente['ativo']}\n"
        f"Resultado: {resultado}"
    )

    sinal_ativo = False
    resultado_pendente = None

# ===============================
# LOOP PRINCIPAL
# ===============================
def loop_principal():
    enviar_telegram("🤖 Troia IA Deriv ONLINE\nAguardando análise...")

    while True:
        gerar_sinal()

        if sinal_ativo:
            verificar_resultado()

        time.sleep(ANALISE_INTERVALO)

# ===============================
# START
# ===============================
if __name__ == "__main__":
    loop_principal()
