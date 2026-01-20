# ===============================
# LOOP PRINCIPAL COM RESULTADO REAL
# ===============================
def loop_ativos():
    tg("🤖 Troia V19 PRO FINAL - Painel Profissional iniciado.\nAnalise 1 ativo por vez.")
    while True:
        for ativo in ATIVOS:
            res = analisar_ativo(ativo)
            if res.get("sinal_enviado"):
                # Espera 1 vela fechar antes de verificar resultado
                time.sleep(WAIT_AFTER_VELA)

                # Pegar candle real da entrada
                end_timestamp = int(time.time())
                # Conecta WS para pegar último candle
                try:
                    ws = websocket.create_connection("wss://ws.derivws.com/websockets/v3?app_id=1089")
                    ws.send(json.dumps({"authorize": DERIV_API_KEY}))
                    ws.send(json.dumps({
                        "ticks_history": ativo,
                        "style": "candles",
                        "granularity": TIMEFRAME,
                        "count": 1,
                        "end": end_timestamp
                    }))
                    data = json.loads(ws.recv())
                    candle = data["candles"][-1]
                    ws.close()

                    # Determinar resultado real
                    direcao_real = direcao_candle(candle)
                    if direcao_real == res['direcao']:
                        resultado = "💸 Green"
                    else:
                        resultado = "🧨 Red"

                    tg(f"🧾 <b>RESULTADO SINAL</b>\n"
                       f"📊 <b>Ativo:</b> {ativo}\n"
                       f"🎯 <b>Direção:</b> {res['direcao']}\n"
                       f"⏱️ <b>Entrada realizada:</b> {res['horario_entrada']}\n"
                       f"✅ <b>Resultado:</b> {resultado}")
                except:
                    tg(f"❌ Não foi possível obter candle real de {ativo}")
            else:
                # Nenhum sinal → passa para próximo ativo
                time.sleep(2)
