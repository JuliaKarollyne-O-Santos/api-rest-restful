"""
3) API RESTful (rigor total + HATEOAS)  ->  http://localhost:5003

Tudo da API REST, mais:
  - Status semânticos: 200, 201, 204, 304, 400, 404, 405, 409, 415
  - Cabeçalhos: Location (201), ETag (cache condicional -> 304),
    Cache-Control (cardápio pode ficar em cache, pedidos não), Allow (405)
  - Stateless: sem sessão nem cookie; cada requisição é independente
  - HATEOAS: cada resposta traz "_links". Os links de um pedido seguem
    a máquina de estados: só aparecem as ações possíveis NAQUELE momento.
    Ex.: um pedido "recebido" oferece "preparando" e "cancelar";
         um pedido "pronto" oferece só "entregue";
         um pedido "entregue" não oferece nenhuma ação.
"""
from flask import Flask, request, jsonify, url_for
from werkzeug.exceptions import HTTPException
from banco import Banco, TRANSICOES, PODE_CANCELAR

app = Flask(__name__)
app.json.ensure_ascii = False
app.json.sort_keys = False
banco = Banco("restful.db")


# ------------------------- HATEOAS -------------------------
def link(endpoint, metodo="GET", **params):
    return {"href": url_for(endpoint, _external=True, **params), "method": metodo}


def lanche_com_links(lanche):
    return {**lanche, "_links": {
        "self": link("obter_lanche", lanche_id=lanche["id"]),
        "pedir": {**link("criar_pedido", "POST"), "body": {"cliente": "string", "lanche_id": lanche["id"], "quantidade": 1}},
    }}


def pedido_com_links(pedido):
    links = {
        "self": link("obter_pedido", pedido_id=pedido["id"]),
        "lanche": link("obter_lanche", lanche_id=pedido["lanche_id"]),
        "todos": link("listar_pedidos"),
    }
    # Só oferece as próximas etapas permitidas pela máquina de estados
    for proximo in TRANSICOES[pedido["status"]]:
        links[proximo] = {**link("mudar_status", "PATCH", pedido_id=pedido["id"]), "body": {"status": proximo}}
    if pedido["status"] in PODE_CANCELAR:
        links["cancelar"] = link("cancelar_pedido", "DELETE", pedido_id=pedido["id"])
    return {**pedido, "_links": links}


# ------------------------- respostas -------------------------
def responder(corpo, status=200, cache="no-cache", **cabecalhos):
    resposta = jsonify(corpo)
    resposta.status_code = status
    resposta.headers.update(cabecalhos)
    if request.method == "GET" and status == 200:
        resposta.headers["Cache-Control"] = cache
        resposta.add_etag()                       # ETag calculado sobre o conteúdo
        resposta.make_conditional(request)        # vira 304 se o cliente já tem essa versão
    return resposta


def problema(status, detalhe, **cabecalhos):
    corpo = {"status": status, "erro": detalhe, "_links": {"inicio": link("raiz")}}
    return responder(corpo, status, **cabecalhos)


@app.errorhandler(HTTPException)
def erro_http(e):
    # Deixa 404 e 405 do Flask em JSON (o padrão seria HTML)
    mensagens = {404: "Recurso não encontrado", 405: "Método não permitido para este recurso"}
    extra = {"Allow": e.get_response().headers["Allow"]} if e.code == 405 else {}
    return problema(e.code, mensagens.get(e.code, e.description), **extra)


def corpo_json():
    """Exige Content-Type: application/json -> senão 415; JSON quebrado -> 400."""
    if not request.is_json:
        return None, problema(415, "Envie o corpo com Content-Type: application/json")
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return None, problema(400, "JSON inválido")
    return dados, None


# ------------------------- rotas -------------------------
@app.get("/")
def raiz():
    return responder({
        "nome": "Lanchonete API (RESTful)",
        "_links": {
            "cardapio": link("listar_lanches"),
            "pedidos": link("listar_pedidos"),
            "fazer_pedido": link("criar_pedido", "POST"),
        },
    })


@app.get("/lanches")
def listar_lanches():
    itens = [lanche_com_links(l) for l in banco.listar_lanches()]
    # Cardápio muda pouco: o cliente pode guardar em cache por 1 hora
    return responder({"itens": itens, "_links": {"self": link("listar_lanches"), "inicio": link("raiz")}},
                     cache="public, max-age=3600")


@app.get("/lanches/<int:lanche_id>")
def obter_lanche(lanche_id):
    lanche = banco.obter_lanche(lanche_id)
    if lanche is None:
        return problema(404, f"Lanche {lanche_id} não existe")
    return responder(lanche_com_links(lanche), cache="public, max-age=3600")


@app.get("/pedidos")
def listar_pedidos():
    status = request.args.get("status")
    if status and status not in TRANSICOES:
        return problema(400, f"Status inválido. Use um destes: {', '.join(TRANSICOES)}")
    filtros = {s: link("listar_pedidos", status=s) for s in TRANSICOES}
    return responder({
        "total": len(pedidos := banco.listar_pedidos(status)),
        "itens": [pedido_com_links(p) for p in pedidos],
        "_links": {"self": link("listar_pedidos"), "criar": link("criar_pedido", "POST"), "filtrar_por_status": filtros},
    })


@app.post("/pedidos")
def criar_pedido():
    dados, erro = corpo_json()
    if erro:
        return erro
    quantidade = dados.get("quantidade", 1)
    if not isinstance(dados.get("cliente"), str) or not dados["cliente"].strip():
        return problema(400, "Campo 'cliente' é obrigatório")
    if not isinstance(quantidade, int) or quantidade < 1:
        return problema(400, "'quantidade' deve ser um inteiro maior que zero")
    if banco.obter_lanche(dados.get("lanche_id")) is None:
        return problema(400, "'lanche_id' não existe no cardápio")

    pedido = banco.criar_pedido(dados["cliente"].strip(), dados["lanche_id"], quantidade)
    return responder(pedido_com_links(pedido), 201,
                     Location=url_for("obter_pedido", pedido_id=pedido["id"], _external=True))


@app.get("/pedidos/<int:pedido_id>")
def obter_pedido(pedido_id):
    pedido = banco.obter_pedido(pedido_id)
    if pedido is None:
        return problema(404, f"Pedido {pedido_id} não encontrado")
    return responder(pedido_com_links(pedido))


@app.patch("/pedidos/<int:pedido_id>")
def mudar_status(pedido_id):
    pedido = banco.obter_pedido(pedido_id)
    if pedido is None:
        return problema(404, f"Pedido {pedido_id} não encontrado")
    dados, erro = corpo_json()
    if erro:
        return erro
    novo = dados.get("status")
    if novo not in TRANSICOES:
        return problema(400, "Informe um 'status' válido")
    if novo not in TRANSICOES[pedido["status"]]:
        # 409 Conflict: o pedido existe, mas o estado atual não permite isso
        return problema(409, f"Um pedido '{pedido['status']}' não pode ir para '{novo}'")
    return responder(pedido_com_links(banco.alterar_pedido(pedido_id, status=novo)))


@app.delete("/pedidos/<int:pedido_id>")
def cancelar_pedido(pedido_id):
    pedido = banco.obter_pedido(pedido_id)
    if pedido is None:
        return problema(404, f"Pedido {pedido_id} não encontrado")
    if pedido["status"] not in PODE_CANCELAR:
        return problema(409, f"Pedido já está '{pedido['status']}' e não pode mais ser cancelado")
    banco.apagar_pedido(pedido_id)
    return "", 204                                  # 204 No Content: deu certo, sem corpo


if __name__ == "__main__":
    app.run(port=5003, debug=True)
