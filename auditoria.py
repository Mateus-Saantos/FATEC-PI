"""Auditoria de acessos e alterações (RF13, RN011)."""
from config import IP_LOCAL
from db import executar, consultar, protegido
from erros import sucesso
from seguranca import ADMIN, exigir_perfil

_SQL_LOG = ("INSERT INTO log_auditoria "
            "(usuario_id, tipo_evento, entidade, entidade_id, detalhe, ip) "
            "VALUES (%s, %s, %s, %s, %s, %s)")


def registrar_log(tipo_evento, usuario_id=None, entidade=None,
                  entidade_id=None, detalhe=None, conn=None):
    """Grava um evento. Passe 'conn' para entrar na mesma transação."""
    if detalhe is not None:
        detalhe = str(detalhe)[:255]
    executar(_SQL_LOG, (usuario_id, tipo_evento, entidade, entidade_id,
                        detalhe, IP_LOCAL), conn)


@protegido
def consultar_auditoria(sessao, tipo_evento=None, limite=50):
    """Lista os últimos eventos do log. Apenas o Administrador."""
    exigir_perfil(sessao, ADMIN)
    limite = max(1, min(int(limite), 500))
    sql = ("SELECT l.id, l.criado_em, l.tipo_evento, p.nome AS usuario, "
           "l.entidade, l.entidade_id, l.detalhe, l.ip "
           "FROM log_auditoria l "
           "LEFT JOIN usuario u ON u.id = l.usuario_id "
           "LEFT JOIN pessoa p ON p.id = u.pessoa_id ")
    params = []
    if tipo_evento:
        sql += "WHERE l.tipo_evento = %s "
        params.append(tipo_evento)
    sql += "ORDER BY l.id DESC LIMIT %s"
    params.append(limite)
    linhas = consultar(sql, params)
    return sucesso(f"{len(linhas)} evento(s) encontrado(s).", linhas)
