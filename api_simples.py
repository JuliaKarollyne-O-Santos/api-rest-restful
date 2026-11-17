"""
1) API SIMPLES (estilo RPC / sem padrão)  ->  http://localhost:5001

Cada endpoint é uma "função remota" com nome de ação:
  /fazerPedido, /verPedidos, /mudarStatus, /cancelarPedido ...

Problemas de propósito:
  - Verbos na URL
  - GET e POST misturados sem critério (cancelar e mudar status via GET!)
  - Sempre status 200, mesmo com erro
  - Cada endpoint responde num formato diferente
"""
from flask import Flask, request, jsonify
from banco import Banco

app = Flask(__name__)
app.json.ensure_ascii = False
banco = Banco("simples.db")


@app.route("/verCardapio")
def ver_cardapio():
    # Formato 1: texto montado à mão
    return "\n".join(f"{l['id']} - {l['nome']} R${l['preco']}" for l in banco.listar_lanches())


@app.route("/verPedidos")
def ver_pedidos():
    # Formato 2: lista crua
    return jsonify(banco.listar_pedidos())


@app.route("/verPedido")
def ver_pedido():
    pedido = banco.obter_pedido(request.args.get("id", type=int))
    if pedido is None:
        return jsonify(sucesso=False, motivo="pedido nao existe")   # erro com 200
    # Formato 3: dados dentro de "dados"
    return jsonify(sucesso=True, dados=pedido)


@app.route("/fazerPedido", methods=["GET", "POST"])
def fazer_pedido():
    # Aceita os dados de qualquer jeito: JSON, formulário ou query string
    entrada = request.get_json(silent=True) or request.values
    try:
        pedido = banco.criar_pedido(entrada["cliente"], int(entrada["lanche"]), int(entrada.get("qtd", 1)))
    except Exception:
        return "deu erro no pedido"                                   # erro como texto, 200
    return jsonify(mensagem=f"Pedido {pedido['id']} feito!")


@app.route("/mudarStatus")
def mudar_status():
    # Altera dados usando GET e não valida nada (pula etapas, aceita qualquer texto)
    pedido_id = request.args.get("id", type=int)
    banco.alterar_pedido(pedido_id, status=request.args.get("status", "recebido"))
    return jsonify(ok=1)


@app.route("/cancelarPedido")
def cancelar_pedido():
    # Apaga dados usando GET
    apagou = banco.apagar_pedido(request.args.get("id", type=int))
    return jsonify(resultado="cancelado" if apagou else "nao tinha esse pedido")


if __name__ == "__main__":
    app.run(port=5001, debug=True)
