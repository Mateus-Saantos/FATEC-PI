"""MÓDULO DE CADASTRO DE VOLUNTÁRIOS.

Requisitos: RF01/RN001/RN014 (cadastro com Termo de Voluntariado assinado),
RF05/RN003 (CPF válido e único), RNF07 (senha em hash).
O voluntário recebe acesso ao sistema com o perfil Professor.
"""
from auditoria import registrar_log
from db import executar, protegido, transacao
from erros import ErroNegocio, sucesso
from interface import cabecalho, confirmar, ler, ler_senha, mostrar
from seguranca import ADMIN, SECRETARIO, exigir_perfil, gerar_hash
from validacao import (somente_digitos, validar_cpf, validar_email,
                       validar_nascimento, validar_nome, validar_senha,
                       validar_telefone)

TERMO_VOLUNTARIADO = ("TERMO DE VOLUNTARIADO: declaro que presto serviço voluntário "
                      "ao Instituto Batista Lázaro Ferreira Filho, sem vínculo "
                      "empregatício e sem remuneração, e que concordo com as normas "
                      "e com o tratamento dos meus dados conforme a LGPD.")


@protegido
def cadastrar_voluntario(sessao, nome, data_nasc, cpf, telefone, email, senha,
                         materia_funcao, termo_aceito=False):
    """Cadastra o voluntário (pessoa + voluntário + usuário Professor)."""
    exigir_perfil(sessao, ADMIN, SECRETARIO)
    nome = validar_nome(nome)
    nasc = validar_nascimento(data_nasc)
    if not validar_cpf(cpf):
        raise ErroNegocio("CPF inválido.")
    if not validar_telefone(telefone):
        raise ErroNegocio("Telefone inválido. Informe DDD e número.")
    email = (email or "").strip().lower()
    if not validar_email(email):
        raise ErroNegocio("E-mail inválido.")
    validar_senha(senha)
    materia_funcao = (materia_funcao or "").strip()
    if not materia_funcao:
        raise ErroNegocio("Informe a matéria ou função do voluntário.")
    if not termo_aceito:
        raise ErroNegocio("É necessário aceitar o Termo de Voluntariado.")

    with transacao() as conn:
        pessoa_id = executar(
            "INSERT INTO pessoa (nome, data_nasc, cpf, telefone, email) "
            "VALUES (%s, %s, %s, %s, %s)",
            (nome, nasc, somente_digitos(cpf), somente_digitos(telefone), email), conn)
        voluntario_id = executar(
            "INSERT INTO voluntario (pessoa_id, materia_funcao, termo_assinado, "
            "data_assinatura) VALUES (%s, %s, TRUE, CURDATE())",
            (pessoa_id, materia_funcao), conn)
        executar(
            "INSERT INTO usuario (pessoa_id, perfil_id, senha_hash) "
            "VALUES (%s, (SELECT id FROM perfil WHERE nome = 'Professor'), %s)",
            (pessoa_id, gerar_hash(senha)), conn)
        registrar_log("CADASTRO_VOLUNTARIO", sessao.usuario_id, "voluntario",
                      voluntario_id, conn=conn)
    return sucesso("Voluntário cadastrado com sucesso!", {"voluntario_id": voluntario_id})


# --- Tela de terminal ---------------------------------------------------------
def tela_cadastrar_voluntario(sessao):
    cabecalho("Cadastro de voluntário")
    nome = ler("Nome completo")
    data_nasc = ler("Data de nascimento (DD/MM/AAAA)")
    cpf = ler("CPF")
    telefone = ler("Telefone com DDD")
    email = ler("E-mail")
    senha = ler_senha("Senha inicial (mín. 8, letras e números)")
    funcao = ler("Matéria ou função")
    print("\n" + TERMO_VOLUNTARIADO)
    aceito = confirmar("O voluntário aceita o Termo de Voluntariado")
    mostrar(cadastrar_voluntario(sessao, nome, data_nasc, cpf, telefone, email,
                                 senha, funcao, aceito))
