"""Erros de negócio e o formato padrão de retorno das funções do sistema."""
from collections import namedtuple


class ErroNegocio(Exception):
    """Regra de negócio violada (a mensagem pode ser mostrada ao usuário)."""


class PermissaoNegada(ErroNegocio):
    """Perfil sem permissão para a operação (RF14)."""


# Toda função de negócio devolve um Resultado:
#   ok        -> True/False
#   mensagem  -> texto objetivo para mostrar ao usuário (RNF03)
#   dados     -> informação extra (ids, listas, relatório...) ou None
Resultado = namedtuple("Resultado", ["ok", "mensagem", "dados"], defaults=[None])


def sucesso(mensagem, dados=None):
    return Resultado(True, mensagem, dados)


def falha(mensagem):
    return Resultado(False, mensagem, None)
