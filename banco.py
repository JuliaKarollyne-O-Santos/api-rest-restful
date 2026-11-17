"""
Camada de dados compartilhada pelas três APIs.
Usa SQLite (já vem com o Python), então os pedidos não somem
quando o servidor é reiniciado. Cada API usa seu próprio arquivo .db.
"""
import sqlite3

CARDAPIO_INICIAL = [
    ("X-Burguer", 18.50),
    ("X-Salada", 21.00),
    ("Batata Frita", 12.00),
    ("Refrigerante Lata", 6.50),
    ("Milkshake", 15.00),
]

# Máquina de estados do pedido: de cada etapa, para onde ele pode ir
TRANSICOES = {
    "recebido":   ["preparando"],
    "preparando": ["pronto"],
    "pronto":     ["entregue"],
    "entregue":   [],
}
# Só dá para cancelar (apagar) um pedido que a cozinha ainda não começou
PODE_CANCELAR = {"recebido"}


class Banco:
    def __init__(self, arquivo):
        self.arquivo = arquivo
        with self._conectar() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS lanches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    preco REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente TEXT NOT NULL,
                    lanche_id INTEGER NOT NULL REFERENCES lanches(id),
                    quantidade INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'recebido'
                );
            """)
            if con.execute("SELECT COUNT(*) FROM lanches").fetchone()[0] == 0:
                con.executemany("INSERT INTO lanches (nome, preco) VALUES (?, ?)", CARDAPIO_INICIAL)

    def _conectar(self):
        con = sqlite3.connect(self.arquivo)
        con.row_factory = sqlite3.Row
        return con

    # ---------- cardápio ----------
    def listar_lanches(self):
        with self._conectar() as con:
            return [dict(l) for l in con.execute("SELECT * FROM lanches ORDER BY id")]

    def obter_lanche(self, lanche_id):
        with self._conectar() as con:
            linha = con.execute("SELECT * FROM lanches WHERE id = ?", (lanche_id,)).fetchone()
            return dict(linha) if linha else None

    # ---------- pedidos ----------
    def listar_pedidos(self, status=None):
        sql = """SELECT p.*, l.nome AS lanche, ROUND(l.preco * p.quantidade, 2) AS total
                 FROM pedidos p JOIN lanches l ON l.id = p.lanche_id"""
        parametros = ()
        if status:
            sql += " WHERE p.status = ?"
            parametros = (status,)
        with self._conectar() as con:
            return [dict(p) for p in con.execute(sql + " ORDER BY p.id", parametros)]

    def obter_pedido(self, pedido_id):
        with self._conectar() as con:
            linha = con.execute(
                """SELECT p.*, l.nome AS lanche, ROUND(l.preco * p.quantidade, 2) AS total
                   FROM pedidos p JOIN lanches l ON l.id = p.lanche_id WHERE p.id = ?""",
                (pedido_id,),
            ).fetchone()
            return dict(linha) if linha else None

    def criar_pedido(self, cliente, lanche_id, quantidade):
        with self._conectar() as con:
            cursor = con.execute(
                "INSERT INTO pedidos (cliente, lanche_id, quantidade) VALUES (?, ?, ?)",
                (cliente, lanche_id, quantidade),
            )
            novo_id = cursor.lastrowid
        return self.obter_pedido(novo_id)

    def alterar_pedido(self, pedido_id, **campos):
        if not campos:
            return self.obter_pedido(pedido_id)
        colunas = ", ".join(f"{nome} = ?" for nome in campos)
        with self._conectar() as con:
            con.execute(f"UPDATE pedidos SET {colunas} WHERE id = ?", (*campos.values(), pedido_id))
        return self.obter_pedido(pedido_id)

    def apagar_pedido(self, pedido_id):
        with self._conectar() as con:
            return con.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,)).rowcount > 0
