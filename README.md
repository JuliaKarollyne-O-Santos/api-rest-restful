# Lanchonete API: Simples (RPC) × REST × RESTful

Sistema de pedidos de uma lanchonete implementado em três níveis de maturidade, em **Python + Flask**, com os dados salvos em **SQLite**.

Cada pedido passa por etapas: **recebido → preparando → pronto → entregue**. Ele só pode ser cancelado enquanto ainda está "recebido".

| Arquivo | Estilo | Porta |
|---|---|---|
| `api_simples.py` | RPC / sem padrão | 5001 |
| `api_rest.py` | REST | 5002 |
| `api_restful.py` | RESTful + HATEOAS | 5003 |
| `banco.py` | camada de dados (SQLite) compartilhada | — |

## Como rodar

```bash
pip install -r requirements.txt
python api_simples.py
python api_rest.py
python api_restful.py
```

Rode cada uma num terminal. Cada API cria seu próprio arquivo `.db` na primeira execução, com o cardápio já preenchido.

## O que muda em cada uma

### 1) API Simples (RPC)
URLs com nome de ação, métodos usados sem critério e respostas sem padrão.

```bash
curl http://localhost:5001/verCardapio                                  # devolve texto, não JSON
curl -X POST http://localhost:5001/fazerPedido -H "Content-Type: application/json" -d '{"cliente":"Ana","lanche":1,"qtd":2}'
curl "http://localhost:5001/verPedido?id=99"                            # erro... com status 200
curl "http://localhost:5001/mudarStatus?id=1&status=qualquercoisa"      # altera via GET, sem validar
curl "http://localhost:5001/cancelarPedido?id=1"                        # apaga via GET
```

### 2) API REST
Recursos no plural, ação definida pelo método HTTP e JSON consistente. Os status ainda são genéricos (200 / 400).

```bash
curl http://localhost:5002/lanches
curl -X POST   http://localhost:5002/pedidos   -H "Content-Type: application/json" -d '{"cliente":"Bia","lanche_id":2}'
curl -X PUT    http://localhost:5002/pedidos/1 -H "Content-Type: application/json" -d '{"status":"pronto"}'
curl -X DELETE http://localhost:5002/pedidos/1
```

### 3) API RESTful
Status semânticos, cabeçalhos HTTP, nenhuma sessão (stateless) e **HATEOAS guiado pela máquina de estados**: cada pedido só mostra os links das ações permitidas naquele momento.

```bash
curl -i http://localhost:5003/                       # ponto de entrada: só links
curl -i -X POST http://localhost:5003/pedidos -H "Content-Type: application/json" \
     -d '{"cliente":"Caio","lanche_id":1,"quantidade":2}'                        # 201 + Location
curl -i -X PATCH http://localhost:5003/pedidos/1 -H "Content-Type: application/json" \
     -d '{"status":"entregue"}'                                                  # 409: pulou etapas
curl -i -X PATCH http://localhost:5003/pedidos/1 -H "Content-Type: application/json" \
     -d '{"status":"preparando"}'                                                # 200, links mudam
curl -i -X DELETE http://localhost:5003/pedidos/1    # 409: já está em preparo
curl -i http://localhost:5003/lanches/1              # Cache-Control: max-age=3600 + ETag
curl -i "http://localhost:5003/pedidos?status=pronto"   # filtro por status
```

Cache condicional: copie o `ETag` de uma resposta e envie de volta. Se o recurso não mudou, a resposta é `304`.
```bash
curl -i http://localhost:5003/pedidos/1 -H 'If-None-Match: "COLE_O_ETAG_AQUI"'
```

| Status | Quando acontece |
|---|---|
| 200 OK | leitura ou alteração bem-sucedida |
| 201 Created | pedido criado (com cabeçalho `Location`) |
| 204 No Content | pedido cancelado |
| 304 Not Modified | cliente já tem a versão atual (ETag) |
| 400 Bad Request | dados inválidos |
| 404 Not Found | pedido ou lanche inexistente |
| 405 Method Not Allowed | método não aceito (com cabeçalho `Allow`) |
| 409 Conflict | transição de etapa proibida, ou cancelar pedido já em preparo |
| 415 Unsupported Media Type | corpo enviado sem `Content-Type: application/json` |

## Comparação

| | Simples (RPC) | REST | RESTful |
|---|---|---|---|
| URL | ação (`/fazerPedido`) | recurso (`/pedidos`) | recurso (`/pedidos`) |
| Ação definida por | nome da URL | método HTTP | método HTTP |
| Regras de negócio | nenhuma (aceita qualquer status) | nenhuma | máquina de estados validada |
| Status | sempre 200 | 200 / 400 | 200, 201, 204, 304, 400, 404, 405, 409, 415 |
| Formato | muda a cada rota | JSON consistente | JSON consistente + `_links` |
| Cache | não | não | `ETag` + `Cache-Control` |
| HATEOAS | não | não | sim, os links dependem da etapa do pedido |
