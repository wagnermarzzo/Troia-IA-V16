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

# Filtros de sinal (teste mais leve)
CONF_MIN = 40    # confiança mínima
PROB_MIN = 50    # probabilidade mínima

# Controle de tentativas
RECONNECT_DELAY = 5
SCAN_DELAY = 3

# Timezone Brasil
BR_TZ = timezone(timedelta(hours=-3))

# Flags
sinal_em_analise = threading.Event()
bot_iniciado = False

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
# FUNÇÃO PARA PROCESSAR DADOS DO WS
# ===============================
def process_data(data):
    try:
        # Simulando análise de sinal
        market_data = json.loads(data)
        # Para teste: pegar apenas se houver "tick" no JSON
        if "tick" in market_data:
            price = market_data["tick"]["quote"]
            timestamp = market_data["tick"]["epoch"]
            dt = datetime.fromtimestamp(timestamp, tz=BR_TZ)
            # Log de tentativa
            print(f"[{dt.strftime('%H:%M:%S')}] Tentativa de sinal: preço={price}")
            
            # Teste: gerar sinal aleatório se filtros forem atingidos
            import random
            confianca = random.randint(30, 70)
            prob = random.randint(30, 70)
            if confianca >= CONF_MIN and prob >= PROB_MIN:
                sinal = "CALL" if random.random() > 0.5 else "PUT"
                message = f"SINAL GERADO: {sinal} | Conf: {confianca}% | Prob: {prob}% | Preço: {price}"
                print(message)
                send_telegram(message)
            else:
                print(f"Descartado: Conf={confianca}% Prob={prob}%")
    except Exception as e:
        print(f"[Erro processamento] {e}")

# ===============================
# FUNÇÃO DO WEBSOCKET
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
                on_close=lambda ws, close_status_code, close_msg: print("[WS] Fechado, reconectando...")
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
    print("=== Troia-V16 TESTE ONLINE ===")
    t = threading.Thread(target=start_ws)
    t.start()
