"""Acesso ao banco de dados MySQL/MariaDB (via PyMySQL).

- transacao(): abre conexão, faz commit no fim e rollback se der erro.
- consultar / consultar_um / executar: atalhos para SQL parametrizado
  (sempre com %s, nunca concatenando texto do usuário: evita SQL injection).
- protegido: decorador que converte erros de banco e de negócio em Resultado.
"""
import functools
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from config import DB_CONFIG
from erros import ErroNegocio, falha


def conectar():
    cfg = dict(DB_CONFIG)
    sock = cfg.pop("unix_socket", None)
    if sock:
        cfg["unix_socket"] = sock
        cfg.pop("host", None)
        cfg.pop("port", None)
    return pymysql.connect(cursorclass=DictCursor, autocommit=False, **cfg)


@contextmanager
def transacao():
    conn = conectar()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def consultar(sql, params=None, conn=None):
    """Executa um SELECT e devolve a lista de linhas (dicionários)."""
    if conn is None:
        with transacao() as nova:
            return consultar(sql, params, nova)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def consultar_um(sql, params=None, conn=None):
    linhas = consultar(sql, params, conn)
    return linhas[0] if linhas else None


def executar(sql, params=None, conn=None):
    """Executa INSERT/UPDATE e devolve o id gerado (quando houver)."""
    if conn is None:
        with transacao() as nova:
            return executar(sql, params, nova)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.lastrowid


# --- Tradução de erros do banco para mensagens objetivas ---------------------
_UNICOS = {
    "uq_pessoa_cpf": "CPF já cadastrado no sistema.",
    "uq_pessoa_email": "E-mail já cadastrado no sistema.",
    "uq_pessoa_telefone": "Telefone já cadastrado no sistema.",
    "uq_chamada_turma_data": "Já existe chamada registrada para esta turma nesta data.",
    "uq_matricula": "Beneficiário já matriculado nesta turma.",
    "uq_modalidade_nome": "Já existe uma modalidade com este nome.",
    "uq_turma_nome": "Já existe uma turma com este nome nesta modalidade.",
    "uq_modelo_nome": "Já existe um modelo de relatório com este nome.",
}

_GATILHOS = {
    "Modalidade sem vagas disponiveis": "Modalidade sem vagas disponíveis.",
    "Voluntario sem termo de voluntariado assinado":
        "Voluntário sem Termo de Voluntariado assinado.",
    "Menor de idade exige responsavel legal e consentimento":
        "Menor de 18 anos exige responsável legal e o consentimento dele.",
    "Data de nascimento obrigatoria para beneficiario":
        "Data de nascimento é obrigatória para o beneficiário.",
    "Historico de presenca nao pode ser excluido":
        "O histórico de presença não pode ser excluído.",
    "Chamada nao pode ser excluida": "A chamada não pode ser excluída.",
}


def traduzir_erro(exc):
    codigo = exc.args[0] if exc.args else 0
    texto = str(exc.args[1]) if len(exc.args) > 1 else str(exc)
    if codigo == 1062:
        for chave, mensagem in _UNICOS.items():
            if chave in texto:
                return mensagem
        return "Registro duplicado."
    if codigo == 1644:
        return _GATILHOS.get(texto, texto)
    if codigo in (4025, 3819):
        return "Algum campo está em formato inválido."
    if codigo in (1045, 1049, 2002, 2003, 2006, 2013):
        return "Não foi possível conectar ao banco de dados."
    return "Erro ao acessar o banco de dados."


def protegido(func):
    """Converte exceções esperadas em Resultado(ok=False, ...)."""
    @functools.wraps(func)
    def envoltorio(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ErroNegocio as erro:          # inclui PermissaoNegada
            return falha(str(erro))
        except pymysql.MySQLError as erro:
            return falha(traduzir_erro(erro))
    return envoltorio
