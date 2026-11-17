"""
2) API REST (princípios básicos)  ->  http://localhost:5002

  - URLs são recursos (substantivos no plural): /lanches, /pedidos, /pedidos/<id>
  - O método HTTP diz a ação: GET lê, POST cria, PUT altera, DELETE remove
  - Entrada e saída sempre em JSON, com formato consistente
  - Status codes ainda genéricos: 200 para sucesso, 400 para qualquer erro
"""
from flask import Flask, request, jsonify
from banco import Banco

app = Flask(__name__)
app.json.ensure_ascii = False
banco = Banco("rest.db")


@app.get("/lanches")
def listar_lanches():
    return jsonify(banco.listar_lanches())


@app.get("/pedidos")
def listar_pedidos():
    return jsonify(banco.listar_pedidos())


@app.get("/pedidos/<int:pedido_id>")
def obter_pedido(pedido_id):
    pedido = banco.obter_pedido(pedido_id)
    if pedido is None:
        return jsonify(erro="Pedido não encontrado"), 400
    return jsonify(pedido)


@app.post("/pedidos")
def criar_pedido():
    dados = request.get_json(silent=True) or {}
    if not dados.get("cliente") or not banco.obter_lanche(dados.get("lanche_id")):
        return jsonify(erro="Informe 'cliente' e um 'lanche_id' válido"), 400
    pedido = banco.criar_pedido(dados["cliente"], dados["lanche_id"], int(dados.get("quantidade", 1)))
    return jsonify(pedido), 200


@app.put("/pedidos/<int:pedido_id>")
def alterar_pedido(pedido_id):
    if banco.obter_pedido(pedido_id) is None:
        return jsonify(erro="Pedido não encontrado"), 400
    dados = request.get_json(silent=True) or {}
    permitidos = {k: v for k, v in dados.items() if k in ("cliente", "quantidade", "status")}
    return jsonify(banco.alterar_pedido(pedido_id, **permitidos))


@app.delete("/pedidos/<int:pedido_id>")
def remover_pedido(pedido_id):
    if not banco.apagar_pedido(pedido_id):
        return jsonify(erro="Pedido não encontrado"), 400
    return jsonify(mensagem="Pedido removido")


if __name__ == "__main__":
    app.run(port=5002, debug=True)
