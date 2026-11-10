"""MÓDULO DE CADASTRO DE SECRETÁRIOS (RF04). Apenas o Administrador."""
from auditoria import registrar_log
from db import executar, protegido, transacao
from erros import sucesso
from interface import cabecalho, ler, ler_senha, mostrar
from seguranca import ADMIN, exigir_perfil, gerar_hash
from validacao import (somente_digitos, validar_email, validar_nome,
                       validar_senha, validar_telefone)
from erros import ErroNegocio


@protegido
def cadastrar_secretario(sessao, nome, email, senha, telefone=""):
    """Cadastra um secretário: só nome, e-mail e senha são obrigatórios."""
    exigir_perfil(sessao, ADMIN)
    nome = validar_nome(nome)
    email = (email or "").strip().lower()
    if not validar_email(email):
        raise ErroNegocio("E-mail inválido.")
    validar_senha(senha)
    if telefone and not validar_telefone(telefone):
        raise ErroNegocio("Telefone inválido. Informe DDD e número.")
    with transacao() as conn:
        pessoa_id = executar(
            "INSERT INTO pessoa (nome, email, telefone) VALUES (%s, %s, %s)",
            (nome, email, somente_digitos(telefone) or None), conn)
        usuario_id = executar(
            "INSERT INTO usuario (pessoa_id, perfil_id, senha_hash) "
            "VALUES (%s, (SELECT id FROM perfil WHERE nome = 'Secretário'), %s)",
            (pessoa_id, gerar_hash(senha)), conn)
        registrar_log("CADASTRO_SECRETARIO", sessao.usuario_id, "usuario",
                      usuario_id, conn=conn)
    return sucesso("Secretário cadastrado com sucesso!", {"usuario_id": usuario_id})


def tela_cadastrar_secretario(sessao):
    cabecalho("Cadastro de secretário")
    mostrar(cadastrar_secretario(sessao, ler("Nome completo"), ler("E-mail"),
                                 ler_senha("Senha inicial (mín. 8, letras e números)"),
                                 ler("Telefone (opcional)", obrigatorio=False)))
