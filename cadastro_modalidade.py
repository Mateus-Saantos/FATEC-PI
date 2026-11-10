"""MÓDULO DE CADASTRO DE MODALIDADES E TURMAS.

Requisitos: RF03/RN006 (cadastrar modalidade), RN004 (limite de vagas),
RN005 (limite de faltas por modalidade).
Cada modalidade (ex.: Balé) tem turmas (professor, sala, horário e dias).
"""
from auditoria import registrar_log
from db import consultar, executar, protegido, transacao
from erros import ErroNegocio, sucesso
from interface import cabecalho, confirmar, ler, mostrar, tabela
from seguranca import ADMIN, SECRETARIO, exigir_perfil
from validacao import validar_hora

DIAS_VALIDOS = ("SEG", "TER", "QUA", "QUI", "SEX", "SAB")


def listar_voluntarios_ativos():
    """Voluntários que podem ser responsáveis (termo assinado)."""
    return consultar(
        "SELECT v.id, p.nome, v.materia_funcao FROM voluntario v "
        "JOIN pessoa p ON p.id = v.pessoa_id "
        "WHERE v.ativo = TRUE AND v.termo_assinado = TRUE ORDER BY p.nome")


def listar_turmas():
    """Turmas ativas com professor, sala, horário, dias e ocupação de vagas."""
    return consultar(
        "SELECT t.id AS turma_id, t.nome AS turma, md.nome AS modalidade, "
        "pp.nome AS professor, t.sala, "
        "CONCAT(LEFT(t.horario_inicio, 5), '-', LEFT(t.horario_fim, 5)) AS horario, "
        "(SELECT GROUP_CONCAT(td.dia_semana ORDER BY "
        "  FIELD(td.dia_semana,'SEG','TER','QUA','QUI','SEX','SAB')) "
        "  FROM turma_dia td WHERE td.turma_id = t.id) AS dias, "
        "vm.vagas_ocupadas, vm.vagas_maximas, vm.lotada "
        "FROM turma t "
        "JOIN modalidade md ON md.id = t.modalidade_id "
        "JOIN voluntario v ON v.id = t.voluntario_id "
        "JOIN pessoa pp ON pp.id = v.pessoa_id "
        "JOIN vw_vagas_modalidade vm ON vm.modalidade_id = md.id "
        "WHERE t.ativa = TRUE AND md.ativo = TRUE ORDER BY md.nome, t.nome")


def listar_modalidades():
    """Cards da tela de modalidades: ocupação de vagas e selo de lotação."""
    return consultar(
        "SELECT m.id, m.nome, m.descricao, m.periodicidade, m.limite_faltas, "
        "vm.vagas_ocupadas, vm.vagas_maximas, vm.vagas_disponiveis, vm.lotada "
        "FROM modalidade m JOIN vw_vagas_modalidade vm ON vm.modalidade_id = m.id "
        "ORDER BY m.nome")


@protegido
def cadastrar_modalidade(sessao, nome, descricao, voluntario_id, vagas_maximas,
                         limite_faltas=3, periodicidade=None, turma=None):
    """Cadastra a modalidade e, se informada, a primeira turma.

    turma = {"nome", "sala", "horario_inicio", "horario_fim", "dias": ["TER","QUI"]}
    'periodicidade' é opcional: se faltar, usa "<N>x por semana" pelos dias da turma.
    """
    exigir_perfil(sessao, ADMIN, SECRETARIO)
    nome = (nome or "").strip()
    if not nome:
        raise ErroNegocio("Informe o nome da modalidade.")
    try:
        vagas_maximas, limite_faltas = int(vagas_maximas), int(limite_faltas)
    except (TypeError, ValueError):
        raise ErroNegocio("Vagas e limite de faltas devem ser números inteiros.")
    if vagas_maximas <= 0:
        raise ErroNegocio("O número de vagas deve ser maior que zero.")
    if limite_faltas <= 0:
        raise ErroNegocio("O limite de faltas deve ser maior que zero.")

    dias = []
    if turma:
        dias = [d.upper() for d in turma.get("dias", [])]
        if not dias or any(d not in DIAS_VALIDOS for d in dias):
            raise ErroNegocio("Informe os dias da turma (SEG, TER, QUA, QUI, SEX, SAB).")
        inicio = validar_hora(turma.get("horario_inicio"), "Horário de início")
        fim = validar_hora(turma.get("horario_fim"), "Horário de término")
        if fim <= inicio:
            raise ErroNegocio("O horário de término deve ser depois do início.")
    if not periodicidade:
        if not dias:
            raise ErroNegocio("Informe a periodicidade da modalidade.")
        periodicidade = f"{len(set(dias))}x por semana"

    with transacao() as conn:
        modalidade_id = executar(
            "INSERT INTO modalidade (nome, descricao, voluntario_id, periodicidade, "
            "vagas_maximas, limite_faltas) VALUES (%s, %s, %s, %s, %s, %s)",
            (nome, (descricao or "").strip() or None, voluntario_id, periodicidade,
             vagas_maximas, limite_faltas), conn)
        turma_id = None
        if turma:
            turma_id = executar(
                "INSERT INTO turma (modalidade_id, voluntario_id, nome, sala, "
                "horario_inicio, horario_fim) VALUES (%s, %s, %s, %s, %s, %s)",
                (modalidade_id, voluntario_id,
                 (turma.get("nome") or f"{nome} Turma A").strip(),
                 (turma.get("sala") or "").strip() or None, inicio, fim), conn)
            for dia in sorted(set(dias)):
                executar("INSERT INTO turma_dia (turma_id, dia_semana) VALUES (%s, %s)",
                         (turma_id, dia), conn)
        registrar_log("CADASTRO_MODALIDADE", sessao.usuario_id, "modalidade",
                      modalidade_id, conn=conn)
    return sucesso("Modalidade salva!", {"modalidade_id": modalidade_id,
                                         "turma_id": turma_id})


# --- Telas de terminal --------------------------------------------------------
def tela_listar_modalidades():
    cabecalho("Gestão de modalidades")
    cartoes = listar_modalidades()
    for c in cartoes:
        c["ocupacao"] = f"{c['vagas_ocupadas']}/{c['vagas_maximas']}"
        c["selo"] = "TURMA LOTADA" if c["lotada"] else ""
    tabela(cartoes, [("nome", "Modalidade", 14), ("periodicidade", "Frequência", 15),
                     ("ocupacao", "Vagas", 7), ("limite_faltas", "Lim.faltas", 10),
                     ("selo", "Selo", 12)])
    print("\nTurmas:")
    tabela(listar_turmas(), [("turma", "Turma", 18), ("professor", "Professor", 16),
                             ("dias", "Dias", 12), ("horario", "Horário", 12),
                             ("sala", "Sala", 8)])


def tela_cadastrar_modalidade(sessao):
    cabecalho("Nova modalidade")
    voluntarios = listar_voluntarios_ativos()
    if not voluntarios:
        print("Cadastre antes um voluntário com o termo assinado.")
        return
    tabela(voluntarios, [("id", "ID", 4), ("nome", "Voluntário", 22),
                         ("materia_funcao", "Função", 14)])
    nome = ler("Nome da modalidade")
    descricao = ler("Descrição", obrigatorio=False)
    voluntario_id = ler("ID do voluntário responsável (professor)")
    vagas = ler("Vagas máximas")
    limite = ler("Limite de faltas consecutivas", padrao="3")
    turma = None
    if confirmar("Cadastrar a primeira turma agora"):
        turma = {"nome": ler("Nome da turma", padrao=f"{nome} Turma A"),
                 "sala": ler("Sala", obrigatorio=False),
                 "horario_inicio": ler("Horário de início (HH:MM)"),
                 "horario_fim": ler("Horário de término (HH:MM)"),
                 "dias": [d.strip() for d in
                          ler("Dias (ex.: TER,QUI)").replace(";", ",").split(",")]}
    mostrar(cadastrar_modalidade(sessao, nome, descricao, voluntario_id, vagas,
                                 limite, turma=turma))
