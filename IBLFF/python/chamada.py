"""MÓDULO DE CHAMADA (CONTROLE DE PRESENÇA).

Requisitos: RF09/RN007 (só o Professor registra, nas próprias turmas),
RF10/RN005 (libera a vaga ao atingir o limite de faltas consecutivas: o gatilho
do banco faz isso ao gravar a falta), RF11/RN008 (histórico, nunca excluído).
"""
from datetime import date

from auditoria import registrar_log
from db import consultar, consultar_um, executar, protegido, transacao
from erros import ErroNegocio, sucesso
from interface import cabecalho, confirmar, ler, mostrar, tabela
from seguranca import ADMIN, PROFESSOR, SECRETARIO, exigir_perfil
from validacao import converter_data

STATUS_VALIDOS = ("PRESENTE", "AUSENTE")


def _turma_permitida(sessao, turma_id, conn):
    """Professor só enxerga as próprias turmas; Admin e Secretário veem todas."""
    if sessao.perfil == PROFESSOR:
        turma = consultar_um(
            "SELECT t.id, t.nome FROM turma t "
            "JOIN voluntario v ON v.id = t.voluntario_id "
            "WHERE t.id = %s AND v.pessoa_id = %s AND t.ativa = TRUE",
            (turma_id, sessao.pessoa_id), conn)
    else:
        turma = consultar_um("SELECT id, nome FROM turma WHERE id = %s AND ativa = TRUE",
                             (turma_id,), conn)
    if turma is None:
        raise ErroNegocio("Turma não encontrada ou sem permissão de acesso.")
    return turma


@protegido
def listar_turmas_do_usuario(sessao):
    exigir_perfil(sessao, ADMIN, SECRETARIO, PROFESSOR)
    sql = ("SELECT t.id, t.nome AS turma, md.nome AS modalidade, t.sala, "
           "CONCAT(LEFT(t.horario_inicio, 5), '-', LEFT(t.horario_fim, 5)) AS horario "
           "FROM turma t JOIN modalidade md ON md.id = t.modalidade_id ")
    params = None
    if sessao.perfil == PROFESSOR:
        sql += ("JOIN voluntario v ON v.id = t.voluntario_id "
                "WHERE v.pessoa_id = %s AND t.ativa = TRUE ")
        params = (sessao.pessoa_id,)
    else:
        sql += "WHERE t.ativa = TRUE "
    linhas = consultar(sql + "ORDER BY md.nome, t.nome", params)
    if not linhas:
        return sucesso("Nenhuma turma disponível.", [])
    return sucesso(f"{len(linhas)} turma(s) disponível(is).", linhas)


@protegido
def listar_alunos_da_chamada(sessao, turma_id):
    """Alunos com matrícula ativa, contador de faltas e alerta visual."""
    exigir_perfil(sessao, ADMIN, SECRETARIO, PROFESSOR)
    with transacao() as conn:
        _turma_permitida(sessao, turma_id, conn)
        alunos = consultar(
            "SELECT matricula_id, aluno, faltas_consecutivas, limite_faltas, alerta "
            "FROM vw_lista_chamada WHERE turma_id = %s ORDER BY aluno",
            (turma_id,), conn)
    return sucesso(f"{len(alunos)} aluno(s) na turma.", alunos)


@protegido
def registrar_chamada(sessao, turma_id, presencas, data_aula=None):
    """Registra a chamada do dia.

    presencas = {matricula_id: "PRESENTE" | "AUSENTE"} para TODOS os alunos ativos.
    Se algum aluno chegar ao limite de faltas, o banco libera a vaga sozinho; esta
    função só informa quais vagas foram liberadas (para avisar a secretaria).
    """
    exigir_perfil(sessao, PROFESSOR)
    data = converter_data(data_aula or date.today(), "Data da chamada")
    for status in presencas.values():
        if status not in STATUS_VALIDOS:
            raise ErroNegocio("Presença deve ser PRESENTE ou AUSENTE.")

    with transacao() as conn:
        _turma_permitida(sessao, turma_id, conn)
        ativos = {l["id"]: l["nome"] for l in consultar(
            "SELECT mt.id, p.nome FROM matricula mt "
            "JOIN beneficiario b ON b.id = mt.beneficiario_id "
            "JOIN pessoa p ON p.id = b.pessoa_id "
            "WHERE mt.turma_id = %s AND mt.status = 'ATIVA'", (turma_id,), conn)}
        if not ativos:
            raise ErroNegocio("A turma não tem alunos ativos.")
        if set(presencas) != set(ativos):
            raise ErroNegocio("Marque a presença de todos os alunos da lista.")

        chamada_id = executar(
            "INSERT INTO chamada (turma_id, data_aula, registrada_por) VALUES (%s, %s, %s)",
            (turma_id, data, sessao.usuario_id), conn)
        for matricula_id, status in presencas.items():
            executar("INSERT INTO presenca (chamada_id, matricula_id, status) "
                     "VALUES (%s, %s, %s)", (chamada_id, matricula_id, status), conn)

        marcadores = ", ".join(["%s"] * len(ativos))
        liberadas = [l["nome"] for l in consultar(
            "SELECT p.nome FROM matricula mt "
            "JOIN beneficiario b ON b.id = mt.beneficiario_id "
            "JOIN pessoa p ON p.id = b.pessoa_id "
            f"WHERE mt.id IN ({marcadores}) AND mt.status = 'VAGA_LIBERADA'",
            list(ativos), conn)]
        em_atencao = [l["aluno"] for l in consultar(
            "SELECT aluno FROM vw_lista_chamada "
            "WHERE turma_id = %s AND alerta <> 'OK'", (turma_id,), conn)]
        registrar_log("CHAMADA_REGISTRADA", sessao.usuario_id, "chamada",
                      chamada_id, conn=conn)
    return sucesso("Chamada salva!", {"chamada_id": chamada_id,
                                      "vagas_liberadas": liberadas,
                                      "em_atencao": em_atencao})


@protegido
def consultar_chamadas(sessao, turma_id):
    """Lista as chamadas já registradas de uma turma (mais recentes primeiro)."""
    exigir_perfil(sessao, ADMIN, SECRETARIO, PROFESSOR)
    with transacao() as conn:
        _turma_permitida(sessao, turma_id, conn)
        linhas = consultar(
            "SELECT c.id, c.data_aula, "
            "SUM(pr.status = 'PRESENTE') AS presentes, "
            "SUM(pr.status = 'AUSENTE') AS ausentes "
            "FROM chamada c LEFT JOIN presenca pr ON pr.chamada_id = c.id "
            "WHERE c.turma_id = %s GROUP BY c.id, c.data_aula "
            "ORDER BY c.data_aula DESC", (turma_id,), conn)
    if not linhas:
        return sucesso("Nenhuma chamada registrada para esta turma.", [])
    return sucesso(f"{len(linhas)} chamada(s) encontrada(s).", linhas)


@protegido
def detalhar_chamada(sessao, chamada_id):
    exigir_perfil(sessao, ADMIN, SECRETARIO, PROFESSOR)
    with transacao() as conn:
        chamada = consultar_um("SELECT turma_id, data_aula FROM chamada WHERE id = %s",
                               (chamada_id,), conn)
        if chamada is None:
            raise ErroNegocio("Chamada não encontrada.")
        _turma_permitida(sessao, chamada["turma_id"], conn)
        linhas = consultar(
            "SELECT p.nome AS aluno, pr.status FROM presenca pr "
            "JOIN matricula mt ON mt.id = pr.matricula_id "
            "JOIN beneficiario b ON b.id = mt.beneficiario_id "
            "JOIN pessoa p ON p.id = b.pessoa_id "
            "WHERE pr.chamada_id = %s ORDER BY p.nome", (chamada_id,), conn)
    return sucesso(f"Chamada de {chamada['data_aula']:%d/%m/%Y}.", linhas)


@protegido
def historico_beneficiario(sessao, beneficiario_id):
    """Total de aulas, presenças, faltas e % de frequência (RF11)."""
    exigir_perfil(sessao, ADMIN, SECRETARIO, PROFESSOR)
    linhas = consultar(
        "SELECT v.modalidade, v.turma, v.total_aulas, v.presencas, v.faltas, "
        "v.percentual_frequencia, v.situacao "
        "FROM vw_frequencia v JOIN matricula mt ON mt.id = v.matricula_id "
        "WHERE mt.beneficiario_id = %s", (beneficiario_id,))
    if not linhas:
        return sucesso("Nenhum registro de participação encontrado.", [])
    return sucesso("Histórico de participação.", linhas)


# --- Telas de terminal --------------------------------------------------------
ICONE = {"OK": "", "ATENCAO": "(!) perto do limite", "LIMITE": "(X) limite atingido"}


def _escolher_turma(sessao):
    turmas = listar_turmas_do_usuario(sessao)
    if not mostrar(turmas) or not turmas.dados:
        return None
    tabela(turmas.dados, [("id", "ID", 4), ("turma", "Turma", 20),
                          ("modalidade", "Modalidade", 12), ("horario", "Horário", 12)])
    try:
        return int(ler("ID da turma"))
    except ValueError:
        print("[ERRO] Digite o número da turma.")
        return None


def tela_registrar_chamada(sessao):
    cabecalho("Controle de presença")
    turma_id = _escolher_turma(sessao)
    if turma_id is None:
        return
    alunos = listar_alunos_da_chamada(sessao, turma_id)
    if not mostrar(alunos) or not alunos.dados:
        return
    print("\nAluno | Faltas | Marque P (presente) ou A (ausente). Enter = presente.")
    presencas = {}
    for aluno in alunos.dados:
        faltas = f"{aluno['faltas_consecutivas']}/{aluno['limite_faltas']}"
        aviso = ICONE.get(aluno["alerta"], "")
        resposta = input(f"{aluno['aluno']:<24} {faltas:<5} {aviso}  [P/A]: ").strip().upper()
        presencas[aluno["matricula_id"]] = "AUSENTE" if resposta == "A" else "PRESENTE"
    ausentes = sum(1 for s in presencas.values() if s == "AUSENTE")
    print(f"\nPresentes: {len(presencas) - ausentes} | Ausentes: {ausentes}")
    if not confirmar("Salvar a chamada"):
        print("Chamada não salva.")
        return
    data = ler("Data da chamada (DD/MM/AAAA)", padrao=date.today().strftime("%d/%m/%Y"))
    resultado = registrar_chamada(sessao, turma_id, presencas, data)
    if mostrar(resultado):
        for nome in resultado.dados["vagas_liberadas"]:
            print(f"  >> Vaga liberada: {nome} atingiu o limite de faltas. "
                  "A secretaria deve ser avisada.")
        for nome in resultado.dados["em_atencao"]:
            print(f"  (!) Atenção: {nome} está perto do limite de faltas.")


def tela_consultar_chamadas(sessao):
    cabecalho("Consultar chamadas")
    turma_id = _escolher_turma(sessao)
    if turma_id is None:
        return
    lista = consultar_chamadas(sessao, turma_id)
    if not mostrar(lista) or not lista.dados:
        return
    for linha in lista.dados:
        linha["data"] = f"{linha['data_aula']:%d/%m/%Y}"
    tabela(lista.dados, [("id", "ID", 5), ("data", "Data", 12),
                         ("presentes", "Presentes", 9), ("ausentes", "Ausentes", 9)])
    escolha = ler("ID da chamada para ver os detalhes (Enter para voltar)",
                  obrigatorio=False)
    if escolha.isdigit():
        detalhe = detalhar_chamada(sessao, int(escolha))
        if mostrar(detalhe):
            tabela(detalhe.dados, [("aluno", "Aluno", 28), ("status", "Presença", 10)])
