import websocket
import json

DERIV_API_KEY = "UEISANwBEI9sPVR"

def listar_simbolos():
    try:
        ws = websocket.create_connection(
            "wss://ws.derivws.com/websockets/v3?app_id=1089",
            timeout=10
        )
        # Autorizar
        ws.send(json.dumps({"authorize": DERIV_API_KEY}))
        # Solicitar símbolos ativos completos
        ws.send(json.dumps({"active_symbols": "full"}))

        # Receber resposta
        resposta = ws.recv()
        data = json.loads(resposta)

        if "active_symbols" in data:
            simbolos = data["active_symbols"]
            for s in simbolos:
                # Imprime código do símbolo e se está aberto ou não
                print(f"{s['symbol']} - {s.get('market_status', 'desconhecido')}")
        else:
            print("❌ Não foi possível obter símbolos da API.")

        ws.close()

    except Exception as e:
        print(f"❌ Erro ao listar símbolos: {e}")

if __name__ == "__main__":
    listar_simbolos()
