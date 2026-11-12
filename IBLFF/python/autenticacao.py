"""MÓDULO DE AUTENTICAÇÃO: login, termo LGPD e recuperação de senha.

Requisitos: RF06 (login por e-mail ou telefone), RF07/RN009 (recuperar senha),
RF08/RN012 (termo LGPD no primeiro acesso), RNF07 (senha em hash).
"""
import hashlib
import secrets
import time

from auditoria import registrar_log
from config import (BLOQUEIO_MINUTOS, IP_LOCAL, MAX_TENTATIVAS_LOGIN, URL_BASE,
                    VALIDADE_TOKEN_MINUTOS, VERSAO_TERMO_LGPD)
from db import consultar_um, executar, protegido, transacao
from erros import ErroNegocio, falha, sucesso
from interface import cabecalho, confirmar, ler, ler_senha, mostrar
from seguranca import Sessao, gerar_hash, verificar_hash
from validacao import somente_digitos, validar_senha

MSG_RECUPERACAO = ("Se o cadastro existir, enviaremos um link de redefinição "
                   "para o e-mail cadastrado.")

TERMO_LGPD = f"""TERMO DE CONSENTIMENTO (LGPD, Lei nº 13.709/2018) - versão {VERSAO_TERMO_LGPD}

1. Dados coletados: nome, data de nascimento, CPF, telefone, e-mail e, para
   beneficiários, endereço e atividades em que participam, com o histórico de
   presença. Para menores, também os dados do responsável legal.
2. Finalidade: organizar turmas e vagas, registrar frequência, emitir relatórios
   internos e entrar em contato. Não vendemos dados nem os compartilhamos com
   terceiros para fins comerciais.
3. Quem acessa: apenas administradores, secretários e professores autorizados.
4. Seus direitos: acesso, correção, anonimização ou eliminação dos dados,
   observados os prazos legais, e revogação deste consentimento, mediante
   pedido ao encarregado de dados do Instituto."""

# Controle simples de tentativas de login (guardado em memória).
_tentativas = {}


def _chave(identificador):
    return identificador.strip().lower()


def _bloqueado(chave):
    registro = _tentativas.get(chave)
    if registro is None:
        return False
    quantidade, primeira = registro
    if time.time() - primeira > BLOQUEIO_MINUTOS * 60:
        _tentativas.pop(chave, None)
        return False
    return quantidade >= MAX_TENTATIVAS_LOGIN


def _registrar_falha(chave):
    quantidade, primeira = _tentativas.get(chave, (0, time.time()))
    _tentativas[chave] = (quantidade + 1, primeira)


def limpar_tentativas():
    """Zera o controle de tentativas (usado nos testes)."""
    _tentativas.clear()


def _buscar_usuario(identificador, conn):
    """Procura o usuário pelo e-mail ou pelo telefone informado (RF06)."""
    ident = identificador.strip()
    if "@" in ident:
        campo, valor = "p.email", ident.lower()
    else:
        campo, valor = "p.telefone", somente_digitos(ident)
    sql = ("SELECT u.id, u.pessoa_id, u.senha_hash, u.primeiro_acesso, u.ativo, "
           "p.nome, p.email, pf.nome AS perfil "
           "FROM usuario u "
           "JOIN pessoa p  ON p.id = u.pessoa_id "
           "JOIN perfil pf ON pf.id = u.perfil_id "
           f"WHERE {campo} = %s")
    return consultar_um(sql, (valor,), conn)


# --- Login --------------------------------------------------------------------
@protegido
def autenticar(identificador, senha):
    """Confere e-mail/telefone e senha.

    Devolve Resultado com dados = {"sessao": Sessao, "primeiro_acesso": bool}.
    Se for o primeiro acesso, o login só termina depois de aceitar o termo
    (chame aceitar_termo_lgpd ou recusar_termo_lgpd).
    """
    if not identificador.strip() or not senha:
        raise ErroNegocio("Preencha todos os campos.")
    chave = _chave(identificador)
    if _bloqueado(chave):
        raise ErroNegocio("Muitas tentativas. Aguarde alguns minutos e tente de novo.")
    with transacao() as conn:
        usuario = _buscar_usuario(identificador, conn)
        if (usuario is None or not usuario["ativo"]
                or not verificar_hash(senha, usuario["senha_hash"])):
            _registrar_falha(chave)
            registrar_log("LOGIN_FALHA", usuario["id"] if usuario else None,
                          detalhe=None if usuario else identificador.strip(),
                          conn=conn)
            return falha("Credenciais inválidas.")      # mensagem genérica
        _tentativas.pop(chave, None)
        sessao = Sessao(usuario["id"], usuario["pessoa_id"],
                        usuario["nome"], usuario["perfil"])
        if not usuario["primeiro_acesso"]:
            registrar_log("LOGIN_OK", usuario["id"], conn=conn)
    return sucesso("Login realizado com sucesso.",
                   {"sessao": sessao,
                    "primeiro_acesso": bool(usuario["primeiro_acesso"])})


@protegido
def aceitar_termo_lgpd(usuario_id):
    """Grava o aceite do termo (data, versão e IP) e libera o acesso (RF08)."""
    with transacao() as conn:
        executar("INSERT INTO aceite_lgpd (usuario_id, versao_termo, ip) "
                 "VALUES (%s, %s, %s)", (usuario_id, VERSAO_TERMO_LGPD, IP_LOCAL), conn)
        executar("UPDATE usuario SET primeiro_acesso = FALSE WHERE id = %s",
                 (usuario_id,), conn)
        registrar_log("ACEITE_LGPD", usuario_id, "usuario", usuario_id, conn=conn)
        registrar_log("LOGIN_OK", usuario_id, conn=conn)
    return sucesso("Termo aceito. Bem-vindo ao sistema!")


@protegido
def recusar_termo_lgpd(usuario_id):
    """Sem aceite não há acesso: a sessão é encerrada."""
    registrar_log("TERMO_LGPD_RECUSADO", usuario_id)
    return falha("É necessário aceitar o termo para usar o sistema.")


# --- Recuperação de senha -----------------------------------------------------
def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@protegido
def iniciar_recuperacao_senha(identificador):
    """Gera um token de uso único (validade de 1 hora) e 'envia' o link.

    A mensagem é SEMPRE a mesma, exista ou não o cadastro (RF07).
    ATENÇÃO: não há servidor de e-mail neste protótipo. O envio é SIMULADO e o
    link volta em dados["simulacao_email"] para ser mostrado no terminal. Em
    produção, envie por SMTP e NÃO devolva o link.
    """
    if not identificador.strip():
        raise ErroNegocio("Informe o e-mail ou telefone cadastrado.")
    simulacao = None
    with transacao() as conn:
        usuario = _buscar_usuario(identificador, conn)
        if usuario and usuario["ativo"] and usuario["email"]:
            token = secrets.token_urlsafe(32)
            executar("UPDATE token_redefinicao_senha SET usado_em = NOW() "
                     "WHERE usuario_id = %s AND usado_em IS NULL",
                     (usuario["id"],), conn)
            executar("INSERT INTO token_redefinicao_senha (usuario_id, token_hash, expira_em) "
                     "VALUES (%s, %s, NOW() + INTERVAL %s MINUTE)",
                     (usuario["id"], _hash_token(token), VALIDADE_TOKEN_MINUTOS), conn)
            registrar_log("RECUPERACAO_SOLICITADA", usuario["id"], conn=conn)
            simulacao = {"para": usuario["email"], "token": token,
                         "link": f"{URL_BASE}/redefinir-senha?token={token}"}
    return sucesso(MSG_RECUPERACAO, {"simulacao_email": simulacao})


@protegido
def redefinir_senha(token, nova_senha, confirmacao):
    """Troca a senha usando o token recebido (uso único, 1 hora)."""
    with transacao() as conn:
        registro = consultar_um(
            "SELECT id, usuario_id FROM token_redefinicao_senha "
            "WHERE token_hash = %s AND usado_em IS NULL AND expira_em > NOW()",
            (_hash_token((token or "").strip()),), conn)
        if registro is None:
            raise ErroNegocio("Token inválido ou expirado.")
        if nova_senha != confirmacao:
            raise ErroNegocio("As senhas não coincidem.")
        validar_senha(nova_senha)
        executar("UPDATE usuario SET senha_hash = %s WHERE id = %s",
                 (gerar_hash(nova_senha), registro["usuario_id"]), conn)
        executar("UPDATE token_redefinicao_senha SET usado_em = NOW() WHERE id = %s",
                 (registro["id"],), conn)
        registrar_log("SENHA_REDEFINIDA", registro["usuario_id"], conn=conn)
    return sucesso("Senha redefinida com sucesso.")


# --- Telas de terminal --------------------------------------------------------
def tela_login():
    """Pede os dados e devolve a Sessao (ou None se o login falhar)."""
    cabecalho("Instituto Batista Lázaro Ferreira Filho - Entrar")
    identificador = ler("E-mail ou telefone")
    senha = ler_senha()
    resultado = autenticar(identificador, senha)
    if not mostrar(resultado):
        return None
    sessao = resultado.dados["sessao"]
    if resultado.dados["primeiro_acesso"]:
        cabecalho("Termo de consentimento (primeiro acesso)")
        print(TERMO_LGPD)
        if confirmar("\nLi e concordo com o termo"):
            mostrar(aceitar_termo_lgpd(sessao.usuario_id))
        else:
            mostrar(recusar_termo_lgpd(sessao.usuario_id))
            return None
    return sessao


def tela_esqueci_senha():
    cabecalho("Recuperar senha")
    resultado = iniciar_recuperacao_senha(ler("E-mail ou telefone cadastrado"))
    mostrar(resultado)
    envio = resultado.dados and resultado.dados.get("simulacao_email")
    if envio:                                   # somente neste protótipo
        print("\n--- SIMULAÇÃO DE E-MAIL (sem servidor de e-mail) ---")
        print(f"Para: {envio['para']}\nLink: {envio['link']}")
        print("Cole o token abaixo na opção 'Redefinir senha':", envio["token"])


def tela_redefinir_senha():
    cabecalho("Redefinir senha")
    token = ler("Token recebido por e-mail")
    nova = ler_senha("Nova senha")
    confirmacao = ler_senha("Confirme a nova senha")
    mostrar(redefinir_senha(token, nova, confirmacao))
