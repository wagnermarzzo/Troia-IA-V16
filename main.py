import websocket, json, time, requests, os
from datetime import datetime, timezone, timedelta
from threading import Thread

# =====================================================
# CREDENCIAIS
# =====================================================
DERIV_API_KEY = "UEISANwBEI9sPVR"
TELEGRAM_TOKEN = "8536239572:AAEkewewiT25GzzwSWNVQL2ZRQ2ITRHTdVU"
TELEGRAM_CHAT_ID = "-1003656750711"

# =====================================================
# CONFIGURAÇÃO GERAL
# =====================================================
TIMEFRAME = 60
NUM_CANDLES = 20
WAIT_BUFFER = 2
HEARTBEAT = 25
MAX_SINAIS_HORA = 5
BR_TZ = timezone(timedelta(hours=-3))
HIST_FILE = "historico_sentinel.json"

# =====================================================
# ATIVOS
# =====================================================
FOREX = {
    "frxEURUSD": "EUR/USD",
    "frxGBPUSD": "GBP/USD",
    "frxUSDJPY": "USD/JPY",
    "frxAUDUSD": "AUD/USD",
    "frxEURGBP": "EUR/GBP"
}

OTC = {
    "OTC_DJI": "US30",
    "OTC_SPC": "US500",
    "OTC_NDX": "NAS100",
    "OTC_FTSE": "UK100",
    "OTC_N225": "JP225"
}

# =====================================================
# TELEGRAM
# =====================================================
def tg_send(msg):
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    ).json()
    return r["result"]["message_id"]

def tg_edit(msg_id, msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
        data={"chat_id": TELEGRAM_CHAT_ID, "message_id": msg_id, "text": msg, "parse_mode": "HTML"}
    )

# =====================================================
# DERIV WS
# =====================================================
def conectar_ws():
    ws = websocket.create_connection(
        "wss://ws.derivws.com/websockets/v3?app_id=1089"
    )
    ws.send(json.dumps({"authorize": DERIV_API_KEY}))
    ws.recv()
    return ws

def heartbeat(ws):
    while True:
        ws.send(json.dumps({"ping": 1}))
        time.sleep(HEARTBEAT)

# =====================================================
# MERCADO
# =====================================================
def pegar_candles(ws, ativo, count):
    ws.send(json.dumps({
        "ticks_history": ativo,
        "style": "candles",
        "granularity": TIMEFRAME,
        "count": count,
        "end": "latest"
    }))
    return json.loads(ws.recv()).get("candles")

def direcao_majoritaria(candles):
    ultimas = candles[-5:]
    return "CALL" if sum(1 for c in ultimas if c["close"] > c["open"]) >= 3 else "PUT"

def confianca(candles):
    call = sum(1 for c in candles if c["close"] > c["open"])
    put = len(candles) - call
    return int(max(call, put) / len(candles) * 100)

# =====================================================
# HISTÓRICO + SCORE
# =====================================================
def carregar_hist():
    if os.path.exists(HIST_FILE):
        return json.load(open(HIST_FILE))
    return []

def salvar_hist(d):
    hist = carregar_hist()
    hist.append(d)
    json.dump(hist, open(HIST_FILE, "w"), indent=2)

def estatistica_ativo(ativo):
    hist = carregar_hist()
    total = greens = reds = streak = 0

    for h in reversed(hist):
        if h["ativo"] != ativo:
            continue
        total += 1
        if h["resultado"] == "Green":
            greens += 1
            streak = streak + 1 if streak >= 0 else 1
        else:
            reds += 1
            streak = streak - 1 if streak <= 0 else -1

    acc = (greens / total * 100) if total else 0
    score = round((acc * 0.6 + abs(streak) * 8) / 10, 1)
    return total, greens, reds, acc, streak, score

# =====================================================
# LOOP PRINCIPAL
# =====================================================
def loop():
    ws = conectar_ws()
    Thread(target=heartbeat, args=(ws,), daemon=True).start()

    tg_send("🤖 <b>IA Sentinel BALANCEADA</b>\nAnálise 24/7 • Entrada imediata")

    sinais_hora = 0
    hora_ref = datetime.now(BR_TZ).hour

    while True:
        agora = datetime.now(BR_TZ)
        if agora.hour != hora_ref:
            sinais_hora = 0
            hora_ref = agora.hour

        if sinais_hora >= MAX_SINAIS_HORA:
            time.sleep(5)
            continue

        for mercado, ativos in [("Forex", FOREX), ("OTC", OTC)]:
            CONF_MIN = 55 if mercado == "Forex" else 50

            for cod, nome in ativos.items():
                candles = pegar_candles(ws, cod, NUM_CANDLES)
                if not candles:
                    continue

                conf = confianca(candles)
                if conf < CONF_MIN:
                    continue

                dirc = direcao_majoritaria(candles)
                preco = candles[-1]["close"]

                total, g, r, acc, streak, score = estatistica_ativo(nome)
                if total >= 10 and score < 6:
                    continue

                msg = (
                    f"📊 <b>SINAL GERADO</b>\n"
                    f"Ativo: {nome}\n"
                    f"Mercado: {mercado}\n"
                    f"Expiração: 1 Min\n"
                    f"Entrada: {'⬆️ CALL' if dirc=='CALL' else '⬇️ PUT'}\n"
                    f"Preço de referência: {preco}\n"
                    f"Modo: Entrada imediata\n\n"
                    f"📈 Estatísticas ({nome})\n"
                    f"📌 Total: {total}\n"
                    f"✅ Greens: {g}\n"
                    f"❌ Reds: {r}\n"
                    f"🎯 Assertividade: {acc:.1f}%\n"
                    f"🔥 Sequência: {streak}\n"
                    f"⭐ Score: {score}/10"
                )

                msg_id = tg_send(msg)
                sinais_hora += 1

                time.sleep(TIMEFRAME + WAIT_BUFFER)

                candle_res = pegar_candles(ws, cod, 1)
                resultado = "Green" if direcao_majoritaria(candle_res) == dirc else "Red"

                tg_edit(msg_id, msg + f"\n\n<b>Resultado:</b> {resultado}")

                salvar_hist({
                    "ativo": nome,
                    "resultado": resultado,
                    "hora": agora.strftime("%Y-%m-%d %H:%M:%S")
                })

                time.sleep(3)

        time.sleep(1)

# =====================================================
# START
# =====================================================
if __name__ == "__main__":
    loop()
