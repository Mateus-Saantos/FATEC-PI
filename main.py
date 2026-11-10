"""PROGRAMA PRINCIPAL: login e menus de cada perfil.

Como executar (dentro desta pasta):
    pip install -r requirements.txt
    python main.py
"""
from auditoria import consultar_auditoria
from autenticacao import (tela_esqueci_senha, tela_login, tela_redefinir_senha)
from cadastro_beneficiario import tela_cadastrar_beneficiario
from cadastro_modalidade import tela_cadastrar_modalidade, tela_listar_modalidades
from cadastro_secretario import tela_cadastrar_secretario
from cadastro_voluntario import tela_cadastrar_voluntario
from chamada import tela_consultar_chamadas, tela_registrar_chamada
from consulta_cadastros import tela_consultar_cadastros
from interface import cabecalho, ler, mostrar, tabela
from relatorios import tela_consultar_relatorio, tela_criar_modelo
from seguranca import ADMIN, PROFESSOR, SECRETARIO


def tela_auditoria(sessao):
    cabecalho("Auditoria de acessos")
    tipo = ler("Filtrar por tipo de evento (Enter = todos)", obrigatorio=False).upper()
    resultado = consultar_auditoria(sessao, tipo or None, 30)
    if mostrar(resultado):
        for linha in resultado.dados:
            linha["quando"] = f"{linha['criado_em']:%d/%m/%Y %H:%M}"
        tabela(resultado.dados, [("quando", "Quando", 16), ("tipo_evento", "Evento", 24),
                                 ("usuario", "Usuário", 18), ("detalhe", "Detalhe", 22)])


# Cada perfil só enxerga as opções permitidas (RF14).
MENUS = {
    ADMIN: [("Cadastrar beneficiário", tela_cadastrar_beneficiario),
            ("Cadastrar voluntário", tela_cadastrar_voluntario),
            ("Cadastrar secretário", tela_cadastrar_secretario),
            ("Nova modalidade", tela_cadastrar_modalidade),
            ("Consultar cadastros", tela_consultar_cadastros),
            ("Gestão de modalidades", lambda s: tela_listar_modalidades()),
            ("Consultar chamadas", tela_consultar_chamadas),
            ("Relatórios", tela_consultar_relatorio),
            ("Criar modelo de relatório", tela_criar_modelo),
            ("Auditoria de acessos", tela_auditoria)],
    SECRETARIO: [("Cadastrar beneficiário", tela_cadastrar_beneficiario),
                 ("Cadastrar voluntário", tela_cadastrar_voluntario),
                 ("Nova modalidade", tela_cadastrar_modalidade),
                 ("Consultar cadastros", tela_consultar_cadastros),
                 ("Gestão de modalidades", lambda s: tela_listar_modalidades()),
                 ("Consultar chamadas", tela_consultar_chamadas)],
    PROFESSOR: [("Registrar chamada", tela_registrar_chamada),
                ("Consultar chamadas", tela_consultar_chamadas),
                ("Relatórios", tela_consultar_relatorio)],
}


def menu_do_perfil(sessao):
    opcoes = MENUS[sessao.perfil]
    while True:
        cabecalho(f"Início - {sessao.nome} ({sessao.perfil})")
        for numero, (rotulo, _) in enumerate(opcoes, start=1):
            print(f"{numero:>2} - {rotulo}")
        print(" 0 - Sair")
        escolha = input("\nEscolha uma opção: ").strip()
        if escolha == "0":
            print("Sessão encerrada.")
            return
        if escolha.isdigit() and 1 <= int(escolha) <= len(opcoes):
            opcoes[int(escolha) - 1][1](sessao)
        else:
            print("Opção inválida!")


def main():
    while True:
        cabecalho("Instituto Batista Lázaro Ferreira Filho")
        print("1 - Entrar\n2 - Esqueci minha senha\n3 - Redefinir senha\n0 - Fechar")
        escolha = input("\nEscolha uma opção: ").strip()
        if escolha == "1":
            sessao = tela_login()
            if sessao:
                menu_do_perfil(sessao)
        elif escolha == "2":
            tela_esqueci_senha()
        elif escolha == "3":
            tela_redefinir_senha()
        elif escolha == "0":
            break
        else:
            print("Opção inválida!")


if __name__ == "__main__":
    main()
