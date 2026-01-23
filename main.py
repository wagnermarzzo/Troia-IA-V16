import json
import time
import threading
import websocket
import requests
from datetime import datetime, timezone, timedelta

# ===============================
# CONFIGURAÇÃO
# ===============================
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

# Filtros leves para gerar sinais contínuos
CONF_MIN = 30    # confiança mínima
PROB_MIN = 30    # probabilidade mínima

RECONNECT_DELAY = 5
SCAN_DELAY = 3

# Timezone Brasil
BR_TZ = timezone(timedelta(hours=-3))

# Flags
sinal_em_analise = threading.Event()
bot_iniciado = False

# ===============================
# LISTA DE ATIVOS
# ===============================
ATIVOS_FOREX = [
    "frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD",
    "frxUSDCAD", "frxUSDCHF", "frxNZDUSD"
]

ATIVOS_OTC = [
    "OTC_US500", "OTC_US30", "OTC_DE30", "OTC_FRA40",
    "OTC_FTI100", "OTC_AUS200", "OTC_JPN225"
]

# ===============================
# FUNÇÃO DE TELEGRAM
# ===============================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"[Telegram ERRO] {e}")

# ===============================
# CHECAR HORÁRIO OTC
# ===============================
def otc_ativo():
    # Para teste, OTC sempre ativo. Pode ajustar conforme horário real se quiser.
    return True

# ===============================
# PROCESSAR DADOS DO WS
# ===============================
def process_data(data):
    try:
        market_data = json.loads(data)

        if "tick" in market_data:
            tick = market_data["tick"]
            ativo = tick.get("symbol", "Desconhecido")
            price = tick["quote"]
            timestamp = tick["epoch"]
            dt = datetime.fromtimestamp(timestamp, tz=BR_TZ)
            
            print(f"[{dt.strftime('%H:%M:%S')}] {ativo} | Tick: {price}")

            sinal_em_analise.set()
            last_price = getattr(process_data, f"last_price_{ativo}", None)

            if last_price:
                diff = price - last_price
                confianca = 50  # Simulação de confiança leve
                prob = 50       # Simulação de probabilidade leve

                # Checa se ativo é OTC e se está ativo
                if ativo in ATIVOS_OTC and not otc_ativo():
                    print(f"{ativo} OTC fechado, ignorando tick")
                else:
                    if confianca >= CONF_MIN and prob >= PROB_MIN:
                        sinal = "CALL" if diff > 0 else "PUT"
                        message = f"SINAL GERADO: {ativo} | {sinal} | Conf: {confianca}% | Prob: {prob}% | Preço: {price}"
                        print(message)
                        send_telegram(message)
                    else:
                        print(f"Descartado: Conf={confianca}% Prob={prob}%")
            
            setattr(process_data, f"last_price_{ativo}", price)
            sinal_em_analise.clear()

    except Exception as e:
        print(f"[Erro processamento] {e}")

# ===============================
# INICIAR WEBSOCKET
# ===============================
def start_ws():
    global bot_iniciado
    while True:
        try:
            ws = websocket.WebSocketApp(
                DERIV_WS_URL,
                on_open=lambda ws: print("[WS] Conectado com sucesso."),
                on_message=lambda ws, msg: process_data(msg),
                on_error=lambda ws, err: print(f"[WS ERRO] {err}"),
                on_close=lambda ws, code, msg: print("[WS] Fechado, reconectando...")
            )

            if not bot_iniciado:
                send_telegram("🤖 Troia-V16 iniciado ✅")
                bot_iniciado = True

            ws.run_forever()
        except Exception as e:
            print(f"[WS EXCEPTION] {e}")
        print(f"Reconectando em {RECONNECT_DELAY}s...")
        time.sleep(RECONNECT_DELAY)

# ===============================
# INICIALIZAÇÃO
# ===============================
if __name__ == "__main__":
    print("=== Troia-V16 ONLINE ===")
    t = threading.Thread(target=start_ws)
    t.start()
