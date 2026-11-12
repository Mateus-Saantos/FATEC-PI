"""MÓDULO DE RELATÓRIOS.

Requisitos: RF12/RN010 (consultar com filtros e exportar PDF, XLSX e CSV),
caso de uso 4.1 (criar modelo de relatório), 4.3 (imprimir) e RF13 (auditoria,
em auditoria.py). Acesso: Administrador e Professor (o professor só vê as
próprias turmas e com o CPF mascarado: LGPD, minimização).
"""
import csv
import os
from datetime import datetime

from auditoria import registrar_log
from config import PASTA_EXPORTACAO
from db import consultar, executar, protegido, transacao
from erros import ErroNegocio, sucesso
from interface import cabecalho, ler, mostrar, tabela
from seguranca import ADMIN, PROFESSOR, exigir_perfil
from validacao import converter_data, formatar_cpf, mascarar_cpf

CAMPOS_RELATORIO = {
    "beneficiario": "Beneficiário",
    "cpf": "CPF",
    "modalidade": "Modalidade",
    "turma": "Turma",
    "total_aulas": "Aulas",
    "presencas": "Presenças",
    "faltas": "Faltas",
    "frequencia": "Frequência (%)",
    "situacao": "Situação",
}
SITUACOES = ("ATIVO", "FALTAS RECORRENTES", "VAGA LIBERADA", "CANCELADA")


# --- Modelos de relatório (caso de uso 4.1) -----------------------------------
@protegido
def criar_modelo(sessao, nome, campos):
    """O administrador escolhe quais campos aparecem no relatório."""
    exigir_perfil(sessao, ADMIN)
    nome = (nome or "").strip()
    if not nome:
        raise ErroNegocio("Informe um nome para o modelo.")
    if not campos:
        raise ErroNegocio("Selecione ao menos um campo.")
    invalidos = [c for c in campos if c not in CAMPOS_RELATORIO]
    if invalidos:
        raise ErroNegocio("Campo inválido: " + ", ".join(invalidos))
    with transacao() as conn:
        modelo_id = executar("INSERT INTO modelo_relatorio (nome, criado_por) "
                             "VALUES (%s, %s)", (nome, sessao.usuario_id), conn)
        for ordem, campo in enumerate(dict.fromkeys(campos), start=1):
            executar("INSERT INTO modelo_relatorio_campo (modelo_id, campo, ordem) "
                     "VALUES (%s, %s, %s)", (modelo_id, campo, ordem), conn)
        registrar_log("MODELO_RELATORIO_CRIADO", sessao.usuario_id,
                      "modelo_relatorio", modelo_id, conn=conn)
    return sucesso("Relatório criado com sucesso!", {"modelo_id": modelo_id})


@protegido
def listar_modelos(sessao):
    exigir_perfil(sessao, ADMIN, PROFESSOR)
    modelos = consultar(
        "SELECT m.id, m.nome, GROUP_CONCAT(c.campo ORDER BY c.ordem) AS campos "
        "FROM modelo_relatorio m "
        "LEFT JOIN modelo_relatorio_campo c ON c.modelo_id = m.id "
        "GROUP BY m.id, m.nome ORDER BY m.nome")
    return sucesso(f"{len(modelos)} modelo(s) disponível(is).", modelos)


# --- Consulta (RF12) ------------------------------------------------------------
@protegido
def consultar_relatorio(sessao, modelo_id=None, modalidade_id=None, turma_id=None,
                        status=None, data_inicio=None, data_fim=None):
    """Frequência por beneficiário, com filtros de modalidade, turma, status e período.

    Devolve dados = {"colunas": [(chave, rótulo)], "linhas": [...], "resumo": {...}}.
    """
    exigir_perfil(sessao, ADMIN, PROFESSOR)
    inicio = converter_data(data_inicio, "Data inicial", True) if data_inicio else None
    fim = converter_data(data_fim, "Data final", True) if data_fim else None
    if inicio and fim and inicio > fim:
        raise ErroNegocio("Filtros inválidos: a data inicial é depois da final.")
    if status and status not in SITUACOES:
        raise ErroNegocio("Situação inválida. Use: " + ", ".join(SITUACOES) + ".")

    colunas = list(CAMPOS_RELATORIO)
    if modelo_id:
        campos = [c["campo"] for c in consultar(
            "SELECT campo FROM modelo_relatorio_campo WHERE modelo_id = %s "
            "ORDER BY ordem", (modelo_id,))]
        if not campos:
            raise ErroNegocio("Modelo de relatório não encontrado.")
        colunas = [c for c in campos if c in CAMPOS_RELATORIO]

    where, params = ["1 = 1"], [inicio or "1000-01-01", fim or "9999-12-31"]
    if modalidade_id:
        where.append("md.id = %s")
        params.append(modalidade_id)
    if turma_id:
        where.append("t.id = %s")
        params.append(turma_id)
    if sessao.perfil == PROFESSOR:               # só as próprias turmas
        where.append("t.voluntario_id IN (SELECT id FROM voluntario WHERE pessoa_id = %s)")
        params.append(sessao.pessoa_id)
    having = ""
    if status:
        having = "HAVING situacao = %s"
        params.append(status)

    linhas = consultar(
        "SELECT p.nome AS beneficiario, p.cpf, md.nome AS modalidade, t.nome AS turma, "
        "COUNT(pr.id) AS total_aulas, "
        "COALESCE(SUM(pr.status = 'PRESENTE'), 0) AS presencas, "
        "COALESCE(SUM(pr.status = 'AUSENTE'), 0) AS faltas, "
        "ROUND(100 * SUM(pr.status = 'PRESENTE') / NULLIF(COUNT(pr.id), 0), 1) AS frequencia, "
        "CASE WHEN mt.status = 'VAGA_LIBERADA' THEN 'VAGA LIBERADA' "
        "     WHEN mt.status = 'CANCELADA' THEN 'CANCELADA' "
        "     WHEN fn_faltas_consecutivas(mt.id) >= md.limite_faltas - 1 "
        "          THEN 'FALTAS RECORRENTES' ELSE 'ATIVO' END AS situacao "
        "FROM matricula mt "
        "JOIN beneficiario b ON b.id = mt.beneficiario_id "
        "JOIN pessoa p ON p.id = b.pessoa_id "
        "JOIN turma t ON t.id = mt.turma_id "
        "JOIN modalidade md ON md.id = t.modalidade_id "
        "LEFT JOIN chamada c ON c.turma_id = t.id AND c.data_aula BETWEEN %s AND %s "
        "LEFT JOIN presenca pr ON pr.chamada_id = c.id AND pr.matricula_id = mt.id "
        f"WHERE {' AND '.join(where)} "
        "GROUP BY mt.id, p.nome, p.cpf, md.nome, md.limite_faltas, t.nome, mt.status "
        f"{having} ORDER BY p.nome, md.nome", params)

    if not linhas:
        return sucesso("Nenhum dado encontrado para os filtros selecionados.",
                       {"colunas": [(c, CAMPOS_RELATORIO[c]) for c in colunas],
                        "linhas": [], "resumo": {}})
    for linha in linhas:                          # LGPD: CPF mascarado p/ professor
        linha["cpf"] = (formatar_cpf(linha["cpf"]) if sessao.perfil == ADMIN
                        else mascarar_cpf(linha["cpf"]))
        for chave in ("presencas", "faltas"):
            linha[chave] = int(linha[chave])
        if linha["frequencia"] is not None:
            linha["frequencia"] = float(linha["frequencia"])
    resumo = {}
    for linha in linhas:
        resumo[linha["situacao"]] = resumo.get(linha["situacao"], 0) + 1
    registrar_log("RELATORIO_CONSULTADO", sessao.usuario_id)
    return sucesso(f"{len(linhas)} resultado(s) encontrado(s).",
                   {"colunas": [(c, CAMPOS_RELATORIO[c]) for c in colunas],
                    "linhas": linhas, "resumo": resumo})


# --- Exportação (RF12) e impressão (caso de uso 4.3) -----------------------------
def _matriz(relatorio):
    cabecalho_ = [rotulo for _, rotulo in relatorio["colunas"]]
    linhas = [["" if l.get(c) is None else l.get(c) for c, _ in relatorio["colunas"]]
              for l in relatorio["linhas"]]
    return cabecalho_, linhas


@protegido
def exportar_relatorio(sessao, relatorio, formato, caminho=None):
    """Exporta para CSV, XLSX ou PDF. Devolve o caminho do arquivo gerado."""
    exigir_perfil(sessao, ADMIN, PROFESSOR)
    formato = (formato or "").lower().strip(".")
    if formato not in ("csv", "xlsx", "pdf"):
        raise ErroNegocio("Formato inválido. Use PDF, XLSX ou CSV.")
    if not relatorio or not relatorio["linhas"]:
        raise ErroNegocio("Não há dados para exportar.")
    if caminho is None:
        os.makedirs(PASTA_EXPORTACAO, exist_ok=True)
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho = os.path.join(PASTA_EXPORTACAO, f"relatorio_{carimbo}.{formato}")
    titulos, linhas = _matriz(relatorio)

    if formato == "csv":
        with open(caminho, "w", newline="", encoding="utf-8-sig") as arq:
            escritor = csv.writer(arq, delimiter=";")     # abre direto no Excel pt-BR
            escritor.writerow(titulos)
            escritor.writerows(linhas)
    elif formato == "xlsx":
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except ImportError:
            raise ErroNegocio("Para exportar XLSX instale: pip install openpyxl")
        pasta = Workbook()
        aba = pasta.active
        aba.title = "Frequência"
        aba.append(titulos)
        for celula in aba[1]:
            celula.font = Font(bold=True)
        for linha in linhas:
            aba.append(linha)
        for coluna in aba.columns:
            aba.column_dimensions[coluna[0].column_letter].width = max(
                12, max(len(str(c.value or "")) for c in coluna) + 2)
        pasta.save(caminho)
    else:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
        except ImportError:
            raise ErroNegocio("Para exportar PDF instale: pip install reportlab")
        estilos = getSampleStyleSheet()
        doc = SimpleDocTemplate(caminho, pagesize=landscape(A4), title="Relatório")
        tabela_pdf = Table([titulos] + [[str(v) for v in l] for l in linhas],
                           repeatRows=1)
        tabela_pdf.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#29ABE2")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        doc.build([Paragraph("Instituto Batista Lázaro Ferreira Filho - Relatório de "
                             f"frequência ({datetime.now():%d/%m/%Y})", estilos["Title"]),
                   tabela_pdf])
    registrar_log("RELATORIO_EXPORTADO", sessao.usuario_id, detalhe=formato.upper())
    return sucesso(f"Relatório exportado em {formato.upper()}.", {"arquivo": caminho})


def formatar_relatorio_texto(relatorio):
    """Relatório em texto alinhado, para mostrar ou imprimir no terminal."""
    titulos, linhas = _matriz(relatorio)
    larguras = [max(len(str(x)) for x in [t] + [l[i] for l in linhas])
                for i, t in enumerate(titulos)]
    def montar(valores):
        return " | ".join(f"{str(v):<{w}}" for v, w in zip(valores, larguras))
    return "\n".join([montar(titulos), "-" * (sum(larguras) + 3 * (len(larguras) - 1))]
                     + [montar(l) for l in linhas])


@protegido
def imprimir_relatorio(sessao, relatorio):
    """Prepara o relatório para impressão (caso de uso 4.3).

    Neste protótipo a 'impressão' é feita no terminal; em uma aplicação web
    seria a janela de impressão do navegador.
    """
    exigir_perfil(sessao, ADMIN, PROFESSOR)
    if not relatorio or not relatorio["linhas"]:
        raise ErroNegocio("Execute a consulta de relatório antes de imprimir.")
    registrar_log("RELATORIO_IMPRESSO", sessao.usuario_id)
    return sucesso("Impressão enviada com sucesso.",
                   {"texto": formatar_relatorio_texto(relatorio)})


# --- Telas de terminal --------------------------------------------------------
def tela_consultar_relatorio(sessao):
    cabecalho("Relatórios")
    modelos = listar_modelos(sessao)
    if modelos.ok and modelos.dados:
        tabela(modelos.dados, [("id", "ID", 4), ("nome", "Modelo", 26)])
    modelo = ler("ID do modelo (Enter = todas as colunas)", obrigatorio=False)
    modalidade = ler("ID da modalidade (Enter = todas)", obrigatorio=False)
    turma = ler("ID da turma (Enter = todas)", obrigatorio=False)
    status = ler("Situação: " + " / ".join(SITUACOES) + " (Enter = todas)",
                 obrigatorio=False).upper()
    inicio = ler("Data inicial DD/MM/AAAA (Enter = sem filtro)", obrigatorio=False)
    fim = ler("Data final DD/MM/AAAA (Enter = sem filtro)", obrigatorio=False)
    resultado = consultar_relatorio(
        sessao, int(modelo) if modelo.isdigit() else None,
        int(modalidade) if modalidade.isdigit() else None,
        int(turma) if turma.isdigit() else None,
        status or None, inicio or None, fim or None)
    if not mostrar(resultado) or not resultado.dados["linhas"]:
        return
    relatorio = resultado.dados
    print()
    print(formatar_relatorio_texto(relatorio))
    print("\nResumo:", ", ".join(f"{n} {s.lower()}" for s, n in relatorio["resumo"].items()))
    acao = ler("Exportar (PDF/XLSX/CSV), I = imprimir, Enter = voltar",
               obrigatorio=False).upper()
    if acao == "I":
        impressao = imprimir_relatorio(sessao, relatorio)
        if mostrar(impressao):
            print(impressao.dados["texto"])
    elif acao:
        saida = exportar_relatorio(sessao, relatorio, acao)
        if mostrar(saida):
            print("Arquivo:", saida.dados["arquivo"])


def tela_criar_modelo(sessao):
    cabecalho("Criar modelo de relatório")
    for chave, rotulo in CAMPOS_RELATORIO.items():
        print(f"  {chave:<13} {rotulo}")
    nome = ler("Nome do modelo")
    campos = [c.strip() for c in ler("Campos (separados por vírgula)").split(",")]
    mostrar(criar_modelo(sessao, nome, campos))
