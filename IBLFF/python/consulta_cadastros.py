"""MÓDULO DE CONSULTA E EDIÇÃO DE CADASTROS.

Requisitos: RF14/RF15/RN013/RNF12. Consulta: Administrador e Secretário.
Edição de dados: somente o Administrador.
"""
from auditoria import registrar_log
from db import consultar, executar, protegido, transacao
from erros import ErroNegocio, sucesso
from interface import cabecalho, ler, mostrar, tabela
from seguranca import ADMIN, SECRETARIO, exigir_perfil
from validacao import (formatar_cpf, formatar_telefone, somente_digitos,
                       validar_email, validar_telefone)


@protegido
def buscar_beneficiarios(sessao, termo=""):
    """Busca por nome ou CPF. Sem termo, lista todos."""
    exigir_perfil(sessao, ADMIN, SECRETARIO)
    termo = (termo or "").strip()
    sql = ("SELECT b.id, p.nome, p.cpf, p.telefone, p.email, b.ativo "
           "FROM beneficiario b JOIN pessoa p ON p.id = b.pessoa_id ")
    params = []
    if termo:
        sql += "WHERE p.nome LIKE %s OR p.cpf = %s "
        params += [f"%{termo}%", somente_digitos(termo)]
    linhas = consultar(sql + "ORDER BY p.nome", params or None)
    for linha in linhas:
        linha["cpf"] = formatar_cpf(linha["cpf"])
        linha["telefone"] = formatar_telefone(linha["telefone"])
    return sucesso(f"{len(linhas)} beneficiário(s) encontrado(s).", linhas)


@protegido
def buscar_voluntarios(sessao, termo=""):
    exigir_perfil(sessao, ADMIN, SECRETARIO)
    termo = (termo or "").strip()
    sql = ("SELECT v.id, p.nome, p.cpf, p.telefone, p.email, v.materia_funcao, v.ativo "
           "FROM voluntario v JOIN pessoa p ON p.id = v.pessoa_id ")
    params = []
    if termo:
        sql += "WHERE p.nome LIKE %s OR p.cpf = %s "
        params += [f"%{termo}%", somente_digitos(termo)]
    linhas = consultar(sql + "ORDER BY p.nome", params or None)
    for linha in linhas:
        linha["cpf"] = formatar_cpf(linha["cpf"])
        linha["telefone"] = formatar_telefone(linha["telefone"])
    return sucesso(f"{len(linhas)} voluntário(s) encontrado(s).", linhas)


@protegido
def atualizar_contato(sessao, pessoa_id, telefone=None, email=None, endereco=None):
    """Corrige telefone, e-mail ou endereço (direito de correção, LGPD art. 18)."""
    exigir_perfil(sessao, ADMIN)
    campos, valores = [], []
    if telefone is not None:
        if not validar_telefone(telefone):
            raise ErroNegocio("Telefone inválido. Informe DDD e número.")
        campos.append("telefone = %s")
        valores.append(somente_digitos(telefone))
    if email is not None:
        email = email.strip().lower()
        if not validar_email(email):
            raise ErroNegocio("E-mail inválido.")
        campos.append("email = %s")
        valores.append(email)
    if endereco is not None:
        campos.append("endereco = %s")
        valores.append(endereco.strip() or None)
    if not campos:
        raise ErroNegocio("Nenhuma alteração informada.")
    with transacao() as conn:
        executar(f"UPDATE pessoa SET {', '.join(campos)} WHERE id = %s",
                 valores + [pessoa_id], conn)
        registrar_log("ALTERACAO_CADASTRO", sessao.usuario_id, "pessoa", pessoa_id,
                      detalhe="campos: " + ", ".join(c.split(" =")[0] for c in campos),
                      conn=conn)
    return sucesso("Cadastro atualizado com sucesso!")


# --- Telas de terminal --------------------------------------------------------
def tela_consultar_cadastros(sessao):
    cabecalho("Consulta de cadastros")
    tipo = ler("1 = Beneficiários, 2 = Voluntários", padrao="1")
    termo = ler("Buscar por nome ou CPF (Enter para todos)", obrigatorio=False)
    busca = (buscar_voluntarios if tipo == "2" else buscar_beneficiarios)(sessao, termo)
    if mostrar(busca):
        colunas = [("id", "ID", 4), ("nome", "Nome", 24), ("cpf", "CPF", 14),
                   ("telefone", "Telefone", 15), ("email", "E-mail", 24)]
        tabela(busca.dados, colunas)
