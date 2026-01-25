import websocket, json, time, requests, os, threading
from datetime import datetime, timezone, timedelta
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

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
NUM_CANDLES = 50   # agora usamos 50 candles para análise avançada
WAIT_BUFFER = 2
HEARTBEAT = 25
BR_TZ = timezone(timedelta(hours=-3))
HIST_FILE = "historico_sentinel.json"
SCORE_RESET_THRESHOLD = 10

# =====================================================
# ATIVOS FOREX
# =====================================================
FOREX = {
    "frxEURUSD": "EUR/USD",
    "frxGBPUSD": "GBP/USD",
    "frxUSDJPY": "USD/JPY",
    "frxAUDUSD": "AUD/USD",
    "frxEURGBP": "EUR/GBP",
    "frxUSDCAD": "USD/CAD",
    "frxUSDCHF": "USD/CHF",
    "frxNZDUSD": "NZD/USD",
    "frxEURJPY": "EUR/JPY",
    "frxGBPJPY": "GBP/JPY",
    "frxAUDJPY": "AUD/JPY",
    "frxEURAUD": "EUR/AUD"
}

# =====================================================
# KEEP ALIVE HTTP
# =====================================================
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Troia-IA V16 Online")

def start_http():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), KeepAlive)
    server.serve_forever()

# =====================================================
# TELEGRAM
# =====================================================
def tg_send(msg):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        ).json()
        return r["result"]["message_id"]
    except:
        return None

def tg_edit(msg_id, msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText",
            data={"chat_id": TELEGRAM_CHAT_ID, "message_id": msg_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except:
        pass

# =====================================================
# DERIV WS
# =====================================================
def conectar_ws():
    while True:
        try:
            ws = websocket.create_connection(
                "wss://ws.derivws.com/websockets/v3?app_id=1089",
                timeout=10
            )
            ws.send(json.dumps({"authorize": DERIV_API_KEY}))
            ws.recv()
            print("✅ Conectado ao WebSocket")
            return ws
        except:
            print("⚠️ Falha na conexão WS, tentando novamente em 5s...")
            time.sleep(5)

def heartbeat(ws):
    while True:
        try:
            ws.send(json.dumps({"ping": 1}))
            time.sleep(HEARTBEAT)
        except:
            return

# =====================================================
# MERCADO
# =====================================================
def pegar_candles(ws, ativo, count):
    try:
        ws.send(json.dumps({
            "ticks_history": ativo,
            "style": "candles",
            "granularity": TIMEFRAME,
            "count": count,
            "end": "latest"
        }))
        data = json.loads(ws.recv())
        return data.get("candles")
    except:
        return None

def direcao_majoritaria(candles):
    if not candles or len(candles) < 5:
        return None
    ultimas = candles[-5:]
    altas = sum(1 for c in ultimas if c["close"] > c["open"])
    baixas = sum(1 for c in ultimas if c["close"] < c["open"])
    if altas > baixas:
        return "CALL"
    elif baixas > altas:
        return "PUT"
    return None

def confianca(candles):
    if not candles:
        return 0
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
        elif h["resultado"] == "Red":
            reds += 1
            streak = streak - 1 if streak <= 0 else -1
    acc = (greens / total * 100) if total else 0
    score = round((acc * 0.6 + abs(streak) * 8) / 10, 1)
    if total >= SCORE_RESET_THRESHOLD and score < 6:
        score += 2
    return total, greens, reds, acc, streak, score

# =====================================================
# IA ULTRA-AVANÇADA
# =====================================================
def ia_ultra(candles):
    if not candles or len(candles) < 10:
        return direcao_majoritaria(candles)

    closes = [c["close"] for c in candles]
    # SMAs
    sma5 = sum(closes[-5:]) / 5
    sma10 = sum(closes[-10:]) / 10
    sma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else sma10
    # Candle majoritário
    major = direcao_majoritaria(candles[-10:])

    # Momentum e reversão
    ultimos5 = candles[-5:]
    altas = sum(1 for c in ultimos5 if c["close"] > c["open"])
    baixas = 5 - altas

    # Lógica avançada
    if closes[-1] > sma5 and closes[-1] > sma10 and closes[-1] > sma20 and altas >= 3:
        return "CALL"
    elif closes[-1] < sma5 and closes[-1] < sma10 and closes[-1] < sma20 and baixas >= 3:
        return "PUT"
    # Reversão: candle forte contra tendência
    if major == "CALL" and closes[-1] < sma5:
        return "PUT"
    if major == "PUT" and closes[-1] > sma5:
        return "CALL"
    return major

# =====================================================
# TEMPLATES
# =====================================================
def template_entrada(nome, mercado, dirc, preco, total, g, r, acc, streak, score):
    seta = "⬆️ CALL" if dirc == "CALL" else "⬇️ PUT"
    return f"""
━━━━━━━━━━━━━━━━━━
🏆 <b>SALA PREMIUM • SENTINEL IA</b>
━━━━━━━━━━━━━━━━━━

📊 <b>ENTRADA CONFIRMADA</b>
📌 Ativo: <b>{nome}</b>
🌍 Mercado: {mercado}
⏱ Expiração: 1 Min

🎯 Direção: <b>{seta}</b>
💰 Entrada: <b>IMEDIATA</b>
📍 Preço: <b>{preco}</b>

📈 <b>Estatísticas</b>
📌 Total: {total}
✅ Greens: {g}
❌ Reds: {r}
🎯 Assertividade: {acc:.1f}%
🔥 Sequência: {streak}
⭐ Score: {score}/10

━━━━━━━━━━━━━━━━━━
🕒 Aguarde o resultado…
""".strip()

def template_resultado(msg_base, resultado, g, r, streak):
    emoji = "🟢💰" if resultado == "Green" else "🔴⚠️" if resultado == "Red" else "⚪️"
    return msg_base + f"""

━━━━━━━━━━━━━━━━━━
<b>{emoji} RESULTADO: {resultado.upper()}</b>

📊 Placar Atual
✅ Greens: {g}
❌ Reds: {r}
🔥 Sequência: {streak}
━━━━━━━━━━━━━━━━━━
""".strip()

# =====================================================
# LOOP PRINCIPAL ULTRA
# =====================================================
def loop():
    while True:
        try:
            ws = conectar_ws()
            Thread(target=heartbeat, args=(ws,), daemon=True).start()
            tg_send("🏆 <b>SALA PREMIUM SENTINEL IA</b>\n🤖 Sistema online • Forex 24/7")

            while True:
                mercado = "Forex"
                CONF_MIN = 65

                for cod, nome in FOREX.items():
                    candles = pegar_candles(ws, cod, NUM_CANDLES)
                    if not candles or len(candles) < NUM_CANDLES:
                        print(f"⚠️ {nome}: Candles insuficientes ou falha ao receber dados.")
                        ws = conectar_ws()
                        continue

                    conf = confianca(candles)
                    if conf < CONF_MIN:
                        print(f"⚠️ {nome}: Confiança {conf}% abaixo do mínimo ({CONF_MIN}%).")
                        continue

                    dirc = ia_ultra(candles)
                    if not dirc:
                        print(f"⚠️ {nome}: Direção indefinida pela IA.")
                        continue

                    preco = candles[-1]["close"]
                    total, g, r, acc, streak, score = estatistica_ativo(nome)
                    msg_base = template_entrada(nome, mercado, dirc, preco, total, g, r, acc, streak, score)

                    msg_id = tg_send(msg_base)
                    time.sleep(TIMEFRAME + WAIT_BUFFER)

                    candle_res = pegar_candles(ws, cod, 1)
                    if candle_res:
                        c = candle_res[0]
                        if c["close"] > c["open"]:
                            resultado = "Green" if dirc == "CALL" else "Red"
                        else:
                            resultado = "Green" if dirc == "PUT" else "Red"
                    else:
                        print(f"⚠️ {nome}: Falha ao receber candle de resultado.")
                        resultado = "Indefinido"
                        ws = conectar_ws()

                    salvar_hist({
                        "ativo": nome,
                        "resultado": resultado,
                        "hora": datetime.now(BR_TZ).strftime("%Y-%m-%d %H:%M:%S")
                    })

                    total, g, r, acc, streak, score = estatistica_ativo(nome)
                    tg_edit(msg_id, template_resultado(msg_base, resultado, g, r, streak))

                    time.sleep(3)

                time.sleep(1)

        except Exception as e:
            print("⚠️ LOOP REINICIADO:", e)
            time.sleep(5)

# =====================================================
# START
# =====================================================
if __name__ == "__main__":
    threading.Thread(target=start_http, daemon=True).start()
    loop()
