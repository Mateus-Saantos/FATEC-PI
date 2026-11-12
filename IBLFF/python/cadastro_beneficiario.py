"""MÓDULO DE CADASTRO DE BENEFICIÁRIOS.

Requisitos: RF02/RN002 (cadastro), RF05/RN003 (CPF válido e único), RN004 (vagas)
e LGPD art. 14 (menor de 18 anos exige responsável legal e o consentimento dele).
Evolução do protótipo da disciplina: agora grava no banco de dados.
"""
from auditoria import registrar_log
from cadastro_modalidade import listar_turmas
from db import consultar_um, executar, protegido, transacao
from erros import ErroNegocio, sucesso
from interface import cabecalho, confirmar, ler, ler_inteiros, mostrar, tabela
from seguranca import ADMIN, SECRETARIO, exigir_perfil
from validacao import (calcular_idade, converter_data, somente_digitos,
                       validar_cpf, validar_email, validar_nascimento,
                       validar_nome, validar_telefone)


def _validar_responsavel(responsavel, menor):
    """Para menores: devolve (nome, cpf, telefone). Maiores não precisam."""
    if not menor:
        return (None, None, None)
    responsavel = responsavel or {}
    nome = (responsavel.get("nome") or "").strip()
    if not nome:
        raise ErroNegocio("Informe o nome do responsável legal (beneficiário menor de 18 anos).")
    if not validar_telefone(responsavel.get("telefone")):
        raise ErroNegocio("Telefone do responsável inválido. Informe DDD e número.")
    cpf = somente_digitos(responsavel.get("cpf"))
    if cpf and not validar_cpf(cpf):
        raise ErroNegocio("CPF do responsável inválido.")
    if not responsavel.get("consentimento"):
        raise ErroNegocio("É necessário o consentimento do responsável legal.")
    return (nome, cpf or None, somente_digitos(responsavel["telefone"]))


@protegido
def cadastrar_beneficiario(sessao, nome, data_nasc, cpf, telefone, turma_ids,
                           email="", endereco="", responsavel=None):
    """Cadastra o beneficiário e o matricula nas turmas escolhidas.

    responsavel = {"nome", "telefone", "cpf" (opcional), "consentimento": True}
    Tudo é gravado numa única transação: se algo falhar, nada é salvo.
    """
    exigir_perfil(sessao, ADMIN, SECRETARIO)
    nome = validar_nome(nome)
    nasc = validar_nascimento(data_nasc)
    if not validar_cpf(cpf):
        raise ErroNegocio("CPF inválido.")
    if not validar_telefone(telefone):
        raise ErroNegocio("Telefone inválido. Informe DDD e número.")
    email = (email or "").strip().lower()
    if email and not validar_email(email):
        raise ErroNegocio("E-mail inválido.")
    turma_ids = sorted(set(turma_ids or []))
    if not turma_ids:
        raise ErroNegocio("Selecione ao menos uma modalidade.")
    resp_nome, resp_cpf, resp_tel = _validar_responsavel(
        responsavel, calcular_idade(nasc) < 18)

    with transacao() as conn:
        for turma_id in turma_ids:
            turma = consultar_um("SELECT ativa FROM turma WHERE id = %s", (turma_id,), conn)
            if turma is None or not turma["ativa"]:
                raise ErroNegocio(f"Turma {turma_id} inválida ou inativa.")
        pessoa_id = executar(
            "INSERT INTO pessoa (nome, data_nasc, cpf, telefone, email, endereco) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (nome, nasc, somente_digitos(cpf), somente_digitos(telefone),
             email or None, (endereco or "").strip() or None), conn)
        beneficiario_id = executar(
            "INSERT INTO beneficiario (pessoa_id, responsavel_nome, responsavel_cpf, "
            "responsavel_telefone, consentimento_responsavel_em) "
            "VALUES (%s, %s, %s, %s, %s)",
            (pessoa_id, resp_nome, resp_cpf, resp_tel,
             None if resp_nome is None else _agora()), conn)
        for turma_id in turma_ids:          # o banco bloqueia se não houver vaga
            executar("INSERT INTO matricula (beneficiario_id, turma_id) VALUES (%s, %s)",
                     (beneficiario_id, turma_id), conn)
        registrar_log("CADASTRO_BENEFICIARIO", sessao.usuario_id, "beneficiario",
                      beneficiario_id, conn=conn)
    return sucesso(f"Beneficiário '{nome}' cadastrado com sucesso!",
                   {"beneficiario_id": beneficiario_id})


def _agora():
    from datetime import datetime
    return datetime.now().replace(microsecond=0)


# --- Tela de terminal ---------------------------------------------------------
def tela_cadastrar_beneficiario(sessao):
    cabecalho("Cadastro de beneficiário")
    nome = ler("Nome completo")
    data_nasc = ler("Data de nascimento (DD/MM/AAAA)")
    cpf = ler("CPF")
    telefone = ler("Telefone com DDD")
    email = ler("E-mail (opcional)", obrigatorio=False)
    endereco = ler("Endereço (opcional)", obrigatorio=False)

    responsavel = None
    try:
        menor = calcular_idade(converter_data(data_nasc)) < 18
    except ErroNegocio:
        menor = False              # a validação completa mostra o erro depois
    if menor:
        print("\nBeneficiário menor de 18 anos: dados do responsável legal.")
        responsavel = {"nome": ler("Nome do responsável"),
                       "telefone": ler("Telefone do responsável"),
                       "cpf": ler("CPF do responsável (opcional)", obrigatorio=False),
                       "consentimento": confirmar("O responsável consentiu com o "
                                                  "tratamento dos dados")}

    print("\nTurmas disponíveis:")
    turmas = listar_turmas()
    for t in turmas:
        t["vagas"] = f"{t['vagas_ocupadas']}/{t['vagas_maximas']}"
    tabela(turmas, [("turma_id", "ID", 4), ("turma", "Turma", 18), ("dias", "Dias", 10),
                    ("horario", "Horário", 11), ("vagas", "Vagas", 7)])
    turma_ids = ler_inteiros("IDs das turmas desejadas (ex.: 1,3)")
    mostrar(cadastrar_beneficiario(sessao, nome, data_nasc, cpf, telefone, turma_ids,
                                   email, endereco, responsavel))
