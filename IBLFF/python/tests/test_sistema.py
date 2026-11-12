"""Testes automatizados dos módulos (rodam contra o banco de verdade).

Antes de rodar, defina o cliente de linha de comando do MySQL/MariaDB, que o teste
usa para recriar o banco limpo a cada caso:
    export MYSQL_CLI="mysql -u root -p'senha'"     # ou "mariadb"
    python -m unittest tests.test_sistema -v        (dentro da pasta do projeto)
"""
import csv
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import auditoria                      # noqa: E402
import autenticacao                   # noqa: E402
import cadastro_beneficiario as cb    # noqa: E402
import cadastro_modalidade as cm      # noqa: E402
import cadastro_secretario as cs      # noqa: E402
import cadastro_voluntario as cv      # noqa: E402
import chamada                        # noqa: E402
import consulta_cadastros as cc       # noqa: E402
import relatorios                     # noqa: E402
from db import consultar, consultar_um  # noqa: E402
from seguranca import gerar_hash, verificar_hash  # noqa: E402
import validacao as v                 # noqa: E402

PASTA_BANCO = os.path.join(os.path.dirname(__file__), "..", "banco")
SENHA = "Demo@2026"


def recarregar_banco():
    cli = shlex.split(os.getenv("MYSQL_CLI", "mysql"))
    for arquivo in ("01_schema_instituto_batista.sql", "02_dados_exemplo.sql"):
        with open(os.path.join(PASTA_BANCO, arquivo), "rb") as f:
            subprocess.run(cli, stdin=f, check=True, capture_output=True)


def entrar(email):
    r = autenticacao.autenticar(email, SENHA)
    assert r.ok, r.mensagem
    return r.dados["sessao"]


class Base(unittest.TestCase):
    def setUp(self):
        recarregar_banco()
        autenticacao.limpar_tentativas()
        self.admin = entrar("admin@demo.org")
        self.secretaria = entrar("secretaria@demo.org")
        self.maria = entrar("maria.silva@demo.org")      # professora do Balé (turma 1)
        self.carlos = entrar("carlos.santos@demo.org")   # professor de Judô (turma 2)


class TestValidacao(unittest.TestCase):
    def test_cpf(self):
        self.assertTrue(v.validar_cpf("529.982.247-25"))
        self.assertFalse(v.validar_cpf("111.111.111-11"))
        self.assertFalse(v.validar_cpf("123"))
        self.assertFalse(v.validar_cpf("529.982.247-26"))

    def test_mascara_e_formatos(self):
        self.assertEqual(v.mascarar_cpf("52998224725"), "***.982.247-**")
        self.assertEqual(v.formatar_telefone("19990000001"), "(19) 99000-0001")

    def test_datas(self):
        self.assertEqual(v.converter_data("05/11/2026"), date(2026, 11, 5))
        with self.assertRaises(Exception):
            v.converter_data("31/02/2026")
        with self.assertRaises(Exception):
            v.converter_data("01/01/2999")

    def test_senha_e_hash(self):
        with self.assertRaises(Exception):
            v.validar_senha("curta1")
        with self.assertRaises(Exception):
            v.validar_senha("somenteletras")
        h = gerar_hash("Segura123")
        self.assertTrue(verificar_hash("Segura123", h))
        self.assertFalse(verificar_hash("outra", h))
        self.assertNotIn("Segura123", h)


class TestAutenticacao(Base):
    def test_login_por_email_e_por_telefone(self):
        self.assertEqual(self.admin.perfil, "Administrador")
        r = autenticacao.autenticar("(19) 99000-0002", SENHA)
        self.assertTrue(r.ok)
        self.assertEqual(r.dados["sessao"].perfil, "Secretário")

    def test_credenciais_invalidas_mensagem_generica_e_log(self):
        a = autenticacao.autenticar("admin@demo.org", "errada123")
        b = autenticacao.autenticar("naoexiste@demo.org", "qualquer1")
        self.assertFalse(a.ok)
        self.assertEqual(a.mensagem, b.mensagem)
        falhas = consultar("SELECT * FROM log_auditoria WHERE tipo_evento = 'LOGIN_FALHA'")
        self.assertEqual(len(falhas), 2)

    def test_campos_vazios(self):
        self.assertFalse(autenticacao.autenticar("", "").ok)

    def test_bloqueio_apos_varias_tentativas(self):
        for _ in range(5):
            autenticacao.autenticar("admin@demo.org", "errada123")
        r = autenticacao.autenticar("admin@demo.org", SENHA)   # mesmo com a senha certa
        self.assertFalse(r.ok)
        self.assertIn("Muitas tentativas", r.mensagem)

    def test_primeiro_acesso_exige_termo(self):
        r = autenticacao.autenticar("lucia.costa@demo.org", SENHA)
        self.assertTrue(r.dados["primeiro_acesso"])
        uid = r.dados["sessao"].usuario_id
        self.assertTrue(autenticacao.aceitar_termo_lgpd(uid).ok)
        aceite = consultar_um("SELECT * FROM aceite_lgpd WHERE usuario_id = %s", (uid,))
        self.assertEqual(aceite["versao_termo"], "v1.0")
        r2 = autenticacao.autenticar("lucia.costa@demo.org", SENHA)
        self.assertFalse(r2.dados["primeiro_acesso"])

    def test_recusar_termo_nao_libera(self):
        r = autenticacao.autenticar("lucia.costa@demo.org", SENHA)
        self.assertFalse(autenticacao.recusar_termo_lgpd(r.dados["sessao"].usuario_id).ok)
        u = consultar_um("SELECT primeiro_acesso FROM usuario WHERE id = %s",
                         (r.dados["sessao"].usuario_id,))
        self.assertTrue(u["primeiro_acesso"])

    def test_recuperacao_de_senha_completa(self):
        r = autenticacao.iniciar_recuperacao_senha("admin@demo.org")
        token = r.dados["simulacao_email"]["token"]
        # o banco guarda só o hash do token
        self.assertIsNone(consultar_um("SELECT 1 AS x FROM token_redefinicao_senha "
                                       "WHERE token_hash = %s", (token,)))
        self.assertFalse(autenticacao.redefinir_senha(token, "NovaSenha1", "Diferente1").ok)
        self.assertFalse(autenticacao.redefinir_senha(token, "curta", "curta").ok)
        self.assertTrue(autenticacao.redefinir_senha(token, "NovaSenha1", "NovaSenha1").ok)
        self.assertTrue(autenticacao.autenticar("admin@demo.org", "NovaSenha1").ok)
        self.assertFalse(autenticacao.autenticar("admin@demo.org", SENHA).ok)
        # uso único
        self.assertFalse(autenticacao.redefinir_senha(token, "OutraSenha2", "OutraSenha2").ok)

    def test_recuperacao_mesma_mensagem_exista_ou_nao(self):
        a = autenticacao.iniciar_recuperacao_senha("admin@demo.org")
        b = autenticacao.iniciar_recuperacao_senha("fantasma@demo.org")
        self.assertEqual(a.mensagem, b.mensagem)
        self.assertIsNone(b.dados["simulacao_email"])

    def test_token_expirado(self):
        r = autenticacao.iniciar_recuperacao_senha("admin@demo.org")
        from db import executar
        executar("UPDATE token_redefinicao_senha SET expira_em = NOW() - INTERVAL 1 MINUTE")
        res = autenticacao.redefinir_senha(r.dados["simulacao_email"]["token"],
                                           "NovaSenha1", "NovaSenha1")
        self.assertFalse(res.ok)
        self.assertIn("inválido ou expirado", res.mensagem)


class TestCadastroBeneficiario(Base):
    ADULTO = dict(nome="Helena Rocha", data_nasc="10/05/1995", cpf="935.411.347-80",
                  telefone="(19) 98888-0001", turma_ids=[2])

    def cadastrar(self, sessao=None, **extra):
        dados = {**self.ADULTO, **extra}
        return cb.cadastrar_beneficiario(sessao or self.secretaria, **dados)

    def test_cadastro_adulto_ok_com_matricula(self):
        # CPF do exemplo já existe no seed -> usar CPF novo e válido
        r = self.cadastrar(cpf="077.164.836-76")
        self.assertTrue(r.ok, r.mensagem)
        mat = consultar("SELECT * FROM matricula WHERE beneficiario_id = %s",
                        (r.dados["beneficiario_id"],))
        self.assertEqual(len(mat), 1)
        self.assertEqual(mat[0]["status"], "ATIVA")

    def test_cpf_invalido_e_duplicado(self):
        self.assertIn("CPF inválido", self.cadastrar(cpf="123.456.789-00").mensagem)
        dup = self.cadastrar(cpf="543.231.948-97")           # CPF da Ana Souza (seed)
        self.assertFalse(dup.ok)
        self.assertIn("CPF já cadastrado", dup.mensagem)

    def test_menor_exige_responsavel_e_consentimento(self):
        base = dict(cpf="077.164.836-76", data_nasc="01/03/2015")
        self.assertIn("responsável", self.cadastrar(**base).mensagem)
        sem_ok = {"nome": "Rita Rocha", "telefone": "19988880002", "consentimento": False}
        self.assertIn("consentimento", self.cadastrar(responsavel=sem_ok, **base).mensagem)
        com_ok = {**sem_ok, "consentimento": True}
        r = self.cadastrar(responsavel=com_ok, **base)
        self.assertTrue(r.ok, r.mensagem)
        b = consultar_um("SELECT * FROM beneficiario WHERE id = %s",
                         (r.dados["beneficiario_id"],))
        self.assertEqual(b["responsavel_nome"], "Rita Rocha")
        self.assertIsNotNone(b["consentimento_responsavel_em"])

    def test_professor_nao_pode_cadastrar(self):
        r = self.cadastrar(sessao=self.maria, cpf="077.164.836-76")
        self.assertFalse(r.ok)
        self.assertIn("não autorizado", r.mensagem)
        negado = consultar("SELECT * FROM log_auditoria WHERE tipo_evento = 'ACESSO_NEGADO'")
        self.assertEqual(len(negado), 1)

    def test_falha_nao_deixa_registro_pela_metade(self):
        antes = consultar_um("SELECT COUNT(*) AS n FROM pessoa")["n"]
        r = self.cadastrar(cpf="077.164.836-76", turma_ids=[2, 999])
        self.assertFalse(r.ok)
        self.assertEqual(consultar_um("SELECT COUNT(*) AS n FROM pessoa")["n"], antes)

    def test_modalidade_lotada_bloqueia_e_desfaz_tudo(self):
        voluntarios = cm.listar_voluntarios_ativos()
        r = cm.cadastrar_modalidade(
            self.admin, "Oficina Mini", "Teste", voluntarios[0]["id"], 1,
            turma={"nome": "Mini A", "sala": "Sala D", "horario_inicio": "18:00",
                   "horario_fim": "19:00", "dias": ["SEG"]})
        turma = r.dados["turma_id"]
        self.assertTrue(self.cadastrar(cpf="077.164.836-76", turma_ids=[turma]).ok)
        antes = consultar_um("SELECT COUNT(*) AS n FROM pessoa")["n"]
        segundo = self.cadastrar(nome="Outra Pessoa", cpf="473.209.567-48",
                                 telefone="19988880009", turma_ids=[turma])
        self.assertFalse(segundo.ok)
        self.assertIn("sem vagas", segundo.mensagem)
        self.assertEqual(consultar_um("SELECT COUNT(*) AS n FROM pessoa")["n"], antes)


class TestCadastroVoluntarioSecretarioModalidade(Base):
    DADOS = dict(nome="Paulo Teixeira", data_nasc="02/02/1990", cpf="077.164.836-76",
                 telefone="19977770001", email="paulo@demo.org", senha="Prof12345",
                 materia_funcao="Teclado")

    def test_voluntario_exige_termo(self):
        r = cv.cadastrar_voluntario(self.admin, termo_aceito=False, **self.DADOS)
        self.assertFalse(r.ok)
        self.assertIn("Termo de Voluntariado", r.mensagem)

    def test_voluntario_ok_e_ja_consegue_entrar_como_professor(self):
        r = cv.cadastrar_voluntario(self.secretaria, termo_aceito=True, **self.DADOS)
        self.assertTrue(r.ok, r.mensagem)
        login = autenticacao.autenticar("paulo@demo.org", "Prof12345")
        self.assertEqual(login.dados["sessao"].perfil, "Professor")
        self.assertTrue(login.dados["primeiro_acesso"])
        u = consultar_um("SELECT senha_hash FROM usuario WHERE pessoa_id = "
                         "(SELECT id FROM pessoa WHERE email = 'paulo@demo.org')")
        self.assertTrue(u["senha_hash"].startswith("$2"))      # bcrypt

    def test_voluntario_cpf_duplicado(self):
        r = cv.cadastrar_voluntario(self.admin, termo_aceito=True,
                                    **{**self.DADOS, "cpf": "083.016.613-05"})
        self.assertIn("CPF já cadastrado", r.mensagem)

    def test_so_admin_cadastra_secretario(self):
        dados = dict(nome="Nova Secretária", email="nova@demo.org", senha="Secret123")
        self.assertFalse(cs.cadastrar_secretario(self.secretaria, **dados).ok)
        self.assertTrue(cs.cadastrar_secretario(self.admin, **dados).ok)
        self.assertEqual(autenticacao.autenticar("nova@demo.org", "Secret123")
                         .dados["sessao"].perfil, "Secretário")

    def test_modalidade_validacoes_e_turma_com_varios_dias(self):
        vol = cm.listar_voluntarios_ativos()[0]["id"]
        turma = {"nome": "Teclado B", "sala": "Sala C", "horario_inicio": "18:00",
                 "horario_fim": "19:30", "dias": ["ter", "qui"]}
        self.assertFalse(cm.cadastrar_modalidade(self.admin, "X", "", vol, 0,
                                                 turma=turma).ok)
        self.assertFalse(cm.cadastrar_modalidade(
            self.admin, "X", "", vol, 10,
            turma={**turma, "horario_fim": "17:00"}).ok)
        r = cm.cadastrar_modalidade(self.admin, "Percussão", "Ritmo", vol, 12, turma=turma)
        self.assertTrue(r.ok, r.mensagem)
        dias = consultar("SELECT dia_semana FROM turma_dia WHERE turma_id = %s",
                         (r.dados["turma_id"],))
        self.assertEqual({d["dia_semana"] for d in dias}, {"TER", "QUI"})
        m = [x for x in cm.listar_modalidades() if x["nome"] == "Percussão"][0]
        self.assertEqual(m["periodicidade"], "2x por semana")
        self.assertFalse(cm.cadastrar_modalidade(self.maria, "Y", "", vol, 5,
                                                 periodicidade="1x").ok)

    def test_consulta_e_edicao_de_cadastros(self):
        achados = cc.buscar_beneficiarios(self.secretaria, "Ana")
        self.assertTrue(achados.ok)
        self.assertIn("Ana Souza", [b["nome"] for b in achados.dados])
        self.assertFalse(cc.buscar_beneficiarios(self.maria).ok)       # professor não
        pessoa = consultar_um("SELECT id FROM pessoa WHERE nome = 'Ana Souza'")["id"]
        self.assertFalse(cc.atualizar_contato(self.secretaria, pessoa, telefone="19999990000").ok)
        self.assertTrue(cc.atualizar_contato(self.admin, pessoa, telefone="19999990000").ok)
        self.assertFalse(cc.atualizar_contato(self.admin, pessoa, email="invalido").ok)
        log = consultar("SELECT * FROM log_auditoria WHERE tipo_evento = 'ALTERACAO_CADASTRO'")
        self.assertEqual(len(log), 1)


class TestChamada(Base):
    def presencas(self, turma_id, ausentes=()):
        alunos = chamada.listar_alunos_da_chamada(self.maria, turma_id).dados
        return {a["matricula_id"]: ("AUSENTE" if a["aluno"] in ausentes else "PRESENTE")
                for a in alunos}

    def test_professor_ve_so_as_proprias_turmas(self):
        minhas = chamada.listar_turmas_do_usuario(self.maria).dados
        self.assertEqual([t["turma"] for t in minhas], ["Balé Turma A"])
        todas = chamada.listar_turmas_do_usuario(self.admin).dados
        self.assertEqual(len(todas), 6)

    def test_lista_mostra_alerta_de_quem_esta_perto_do_limite(self):
        alunos = {a["aluno"]: a for a in chamada.listar_alunos_da_chamada(self.maria, 1).dados}
        self.assertEqual(alunos["Clara Mendes"]["alerta"], "ATENCAO")      # 2/3
        self.assertEqual(alunos["Clara Mendes"]["faltas_consecutivas"], 2)
        self.assertEqual(alunos["Beatriz Ramos"]["alerta"], "OK")

    def test_so_professor_registra_chamada(self):
        pres = self.presencas(1)
        self.assertFalse(chamada.registrar_chamada(self.admin, 1, pres, "05/11/2026").ok)
        self.assertFalse(chamada.registrar_chamada(self.secretaria, 1, pres, "05/11/2026").ok)

    def test_professor_nao_registra_turma_de_outro(self):
        pres = self.presencas(1)
        r = chamada.registrar_chamada(self.carlos, 1, pres, "05/11/2026")
        self.assertFalse(r.ok)
        self.assertIn("permissão", r.mensagem)

    def test_registrar_chamada_e_nao_duplicar(self):
        r = chamada.registrar_chamada(self.maria, 1, self.presencas(1), "05/11/2026")
        self.assertTrue(r.ok, r.mensagem)
        self.assertEqual(r.dados["vagas_liberadas"], [])
        dup = chamada.registrar_chamada(self.maria, 1, self.presencas(1), "05/11/2026")
        self.assertIn("Já existe chamada", dup.mensagem)

    def test_chamada_incompleta_ou_data_futura_rejeitadas(self):
        pres = self.presencas(1)
        pres.popitem()
        self.assertFalse(chamada.registrar_chamada(self.maria, 1, pres, "05/11/2026").ok)
        self.assertFalse(chamada.registrar_chamada(self.maria, 1, self.presencas(1),
                                                   "01/01/2999").ok)

    def test_terceira_falta_seguida_libera_a_vaga(self):
        r = chamada.registrar_chamada(self.maria, 1,
                                      self.presencas(1, ausentes=["Clara Mendes"]),
                                      "05/11/2026")
        self.assertTrue(r.ok, r.mensagem)
        self.assertEqual(r.dados["vagas_liberadas"], ["Clara Mendes"])
        nomes = [a["aluno"] for a in chamada.listar_alunos_da_chamada(self.maria, 1).dados]
        self.assertNotIn("Clara Mendes", nomes)            # saiu da lista de chamada
        log = consultar("SELECT * FROM log_auditoria WHERE tipo_evento = 'VAGA_LIBERADA'")
        self.assertEqual(len(log), 1)

    def test_consultar_chamadas_e_detalhe(self):
        lista = chamada.consultar_chamadas(self.admin, 1)
        self.assertEqual(len(lista.dados), 3)
        self.assertEqual(lista.dados[0]["data_aula"], date(2026, 11, 3))
        detalhe = chamada.detalhar_chamada(self.admin, lista.dados[0]["id"])
        status = {l["aluno"]: l["status"] for l in detalhe.dados}
        self.assertEqual(status["Clara Mendes"], "AUSENTE")
        self.assertFalse(chamada.consultar_chamadas(self.carlos, 1).ok)

    def test_historico_do_beneficiario(self):
        b = consultar_um("SELECT b.id FROM beneficiario b JOIN pessoa p ON p.id = b.pessoa_id "
                         "WHERE p.nome = 'Clara Mendes'")["id"]
        h = chamada.historico_beneficiario(self.secretaria, b).dados[0]
        self.assertEqual((h["total_aulas"], h["presencas"], h["faltas"]), (3, 1, 2))
        self.assertEqual(h["situacao"], "FALTAS RECORRENTES")

    def test_historico_nao_pode_ser_apagado_nem_pelo_codigo(self):
        import pymysql
        from db import executar
        with self.assertRaises(pymysql.MySQLError):
            executar("DELETE FROM presenca")


class TestRelatorios(Base):
    def test_relatorio_completo_admin_com_cpf_inteiro(self):
        r = relatorios.consultar_relatorio(self.admin)
        self.assertTrue(r.ok)
        self.assertEqual(len(r.dados["linhas"]), 8)
        ana = [l for l in r.dados["linhas"] if l["beneficiario"] == "Ana Souza"][0]
        self.assertEqual(ana["cpf"], "543.231.948-97")
        self.assertEqual((ana["total_aulas"], ana["presencas"], ana["faltas"]), (3, 2, 1))

    def test_professor_so_as_proprias_turmas_e_cpf_mascarado(self):
        r = relatorios.consultar_relatorio(self.maria)
        self.assertTrue(r.ok)
        self.assertEqual(len(r.dados["linhas"]), 6)              # só o Balé
        self.assertTrue(all(l["cpf"].startswith("***.") for l in r.dados["linhas"]))
        self.assertTrue(relatorios.consultar_relatorio(self.carlos).ok)
        self.assertFalse(relatorios.consultar_relatorio(self.secretaria).ok)

    def test_filtros_status_modalidade_e_periodo(self):
        rec = relatorios.consultar_relatorio(self.admin, status="FALTAS RECORRENTES")
        self.assertEqual([l["beneficiario"] for l in rec.dados["linhas"]], ["Clara Mendes"])
        balé = relatorios.consultar_relatorio(self.admin, modalidade_id=1)
        self.assertEqual(len(balé.dados["linhas"]), 6)
        periodo = relatorios.consultar_relatorio(self.admin, turma_id=1,
                                                 data_inicio="29/10/2026",
                                                 data_fim="03/11/2026")
        self.assertEqual({l["total_aulas"] for l in periodo.dados["linhas"]}, {2})
        vazio = relatorios.consultar_relatorio(self.admin, status="VAGA LIBERADA")
        self.assertTrue(vazio.ok)
        self.assertEqual(vazio.dados["linhas"], [])
        self.assertIn("Nenhum dado", vazio.mensagem)

    def test_filtros_invalidos(self):
        self.assertFalse(relatorios.consultar_relatorio(
            self.admin, data_inicio="10/11/2026", data_fim="01/11/2026").ok)
        self.assertFalse(relatorios.consultar_relatorio(self.admin, status="XYZ").ok)

    def test_modelo_de_relatorio(self):
        self.assertFalse(relatorios.criar_modelo(self.maria, "Meu", ["faltas"]).ok)
        self.assertFalse(relatorios.criar_modelo(self.admin, "Vazio", []).ok)
        self.assertFalse(relatorios.criar_modelo(self.admin, "Ruim", ["senha_hash"]).ok)
        r = relatorios.criar_modelo(self.admin, "Só faltas", ["beneficiario", "faltas"])
        self.assertTrue(r.ok, r.mensagem)
        rel = relatorios.consultar_relatorio(self.admin, modelo_id=r.dados["modelo_id"])
        self.assertEqual([c for c, _ in rel.dados["colunas"]], ["beneficiario", "faltas"])

    def test_exportar_csv_xlsx_pdf(self):
        rel = relatorios.consultar_relatorio(self.admin).dados
        with tempfile.TemporaryDirectory() as pasta:
            for formato in ("csv", "xlsx", "pdf"):
                r = relatorios.exportar_relatorio(self.admin, rel, formato,
                                                  os.path.join(pasta, f"r.{formato}"))
                self.assertTrue(r.ok, r.mensagem)
                self.assertGreater(os.path.getsize(r.dados["arquivo"]), 100)
            with open(os.path.join(pasta, "r.csv"), encoding="utf-8-sig") as f:
                linhas = list(csv.reader(f, delimiter=";"))
            self.assertEqual(len(linhas), 9)                  # cabeçalho + 8
            self.assertEqual(linhas[0][0], "Beneficiário")
        self.assertFalse(relatorios.exportar_relatorio(self.admin, rel, "doc").ok)

    def test_imprimir_exige_relatorio_em_tela(self):
        self.assertFalse(relatorios.imprimir_relatorio(self.admin, None).ok)
        rel = relatorios.consultar_relatorio(self.admin).dados
        r = relatorios.imprimir_relatorio(self.admin, rel)
        self.assertTrue(r.ok)
        self.assertIn("Clara Mendes", r.dados["texto"])

    def test_auditoria_so_para_admin(self):
        self.assertFalse(auditoria.consultar_auditoria(self.maria).ok)
        r = auditoria.consultar_auditoria(self.admin, "LOGIN_OK")
        self.assertTrue(r.ok)
        self.assertGreaterEqual(len(r.dados), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
