"""Senhas em hash, sessão do usuário e controle de permissões (RF14)."""
from dataclasses import dataclass

import bcrypt

from erros import PermissaoNegada

ADMIN = "Administrador"
SECRETARIO = "Secretário"
PROFESSOR = "Professor"


@dataclass(frozen=True)
class Sessao:
    """Quem está usando o sistema neste momento."""
    usuario_id: int
    pessoa_id: int
    nome: str
    perfil: str


def gerar_hash(senha):
    """bcrypt com custo 10 (RNF07). A senha nunca é guardada em texto."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("ascii")


def verificar_hash(senha, senha_hash):
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("ascii"))
    except ValueError:
        return False


def exigir_perfil(sessao, *perfis):
    """Interrompe a operação se o perfil não estiver autorizado.

    Também registra a tentativa no log de auditoria (RF13).
    """
    if sessao is not None and sessao.perfil in perfis:
        return
    from auditoria import registrar_log          # import local evita ciclo
    try:
        registrar_log("ACESSO_NEGADO",
                      sessao.usuario_id if sessao else None,
                      detalhe="perfil exigido: " + ", ".join(perfis))
    except Exception:
        pass                                      # negar o acesso vem primeiro
    raise PermissaoNegada("Acesso não autorizado.")
