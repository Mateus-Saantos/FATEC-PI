
import os
import sys
import secrets
import hmac
from pathlib import Path
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)

# Permite importar os módulos que estão dentro de IBLFF/python
BASE_DIR = Path(__file__).resolve().parent
PYTHON_DIR = BASE_DIR / "python"
sys.path.insert(0, str(PYTHON_DIR))

from autenticacao import (
    autenticar,
    aceitar_termo_lgpd,
    recusar_termo_lgpd,
    TERMO_LGPD
)
from seguranca import Sessao
from config import VERSAO_TERMO_LGPD


from cadastro_beneficiario import cadastrar_beneficiario
from cadastro_voluntario import cadastrar_voluntario
from cadastro_modalidade import listar_turmas



app = Flask(
    __name__,
    template_folder="templates",
    static_folder="css",
    static_url_path="/css"
)

# A chave deve ser definida no ambiente, nunca fixa no código.
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "Defina a variável de ambiente FLASK_SECRET_KEY antes de iniciar."
    )

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_HTTPS", "0") == "1"
)


# -------------------------------------------------------------------
# Proteção CSRF simples para os formulários POST
# -------------------------------------------------------------------

@app.before_request
def preparar_csrf():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)


@app.context_processor
def disponibilizar_csrf():
    return {"csrf_token": session.get("_csrf_token", "")}


def validar_csrf():
    enviado = request.form.get("csrf_token", "")
    esperado = session.get("_csrf_token", "")

    if not esperado or not hmac.compare_digest(enviado, esperado):
        flash("Sua sessão expirou ou o formulário é inválido. Tente novamente.", "erro")
        return False

    return True


# -------------------------------------------------------------------
# Sessão e autenticação
# -------------------------------------------------------------------

def obter_sessao():
    if not session.get("usuario_id"):
        return None

    return Sessao(
        usuario_id=session["usuario_id"],
        pessoa_id=session["pessoa_id"],
        nome=session["nome"],
        perfil=session["perfil"]
    )


def login_obrigatorio(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if obter_sessao() is None:
            flash("Faça login para acessar o sistema.", "erro")
            return redirect(url_for("index"))

        return func(*args, **kwargs)

    return wrapper


def registrar_sessao(dados):
    sessao_usuario = dados["sessao"]

    session.clear()
    session["usuario_id"] = sessao_usuario.usuario_id
    session["pessoa_id"] = sessao_usuario.pessoa_id
    session["nome"] = sessao_usuario.nome
    session["perfil"] = sessao_usuario.perfil


# -------------------------------------------------------------------
# Login
# -------------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    if obter_sessao():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not validar_csrf():
            return redirect(url_for("index"))

        identificador = request.form.get("identity", "").strip()
        senha = request.form.get("password", "")

        resultado = autenticar(identificador, senha)

        if not resultado.ok:
            flash(resultado.mensagem, "erro")
            return redirect(url_for("index"))

        if resultado.dados["primeiro_acesso"]:
            # Ainda não libera o sistema. Aguarda o aceite LGPD.
            session.clear()
            session["usuario_pendente_lgpd"] = (
                resultado.dados["sessao"].usuario_id
            )
            session["nome_pendente_lgpd"] = (
                resultado.dados["sessao"].nome
            )
            session["_csrf_token"] = secrets.token_urlsafe(32)

            return redirect(url_for("termo_lgpd"))

        registrar_sessao(resultado.dados)
        session["_csrf_token"] = secrets.token_urlsafe(32)
        flash("Login realizado com sucesso.", "sucesso")
        return redirect(url_for("dashboard"))

    return render_template("index.html")


# -------------------------------------------------------------------
# Termo LGPD no primeiro acesso
# -------------------------------------------------------------------

@app.route("/termo-lgpd", methods=["GET", "POST"])
def termo_lgpd():
    usuario_id = session.get("usuario_pendente_lgpd")

    if not usuario_id:
        return redirect(url_for("index"))

    if request.method == "POST":
        if not validar_csrf():
            return redirect(url_for("termo_lgpd"))

        acao = request.form.get("acao")

        if acao == "aceitar":

            if request.form.get("consentimento") != "sim":
                flash("É necessário marcar o aceite do termo.", "erro")
                return redirect(url_for("termo_lgpd"))

            resultado = aceitar_termo_lgpd(usuario_id)

            if resultado.ok:
                nome = session.get("nome_pendente_lgpd", "")
                session.clear()
                session["usuario_id"] = usuario_id

                # Recupera os dados completos da sessão após o aceite.
                # A autenticação será refeita no próximo login.
                # Nesta etapa, buscamos os dados da pessoa e do perfil.
                from db import consultar_um

                usuario = consultar_um(
                    "SELECT u.pessoa_id, p.nome, pf.nome AS perfil "
                    "FROM usuario u "
                    "JOIN pessoa p ON p.id = u.pessoa_id "
                    "JOIN perfil pf ON pf.id = u.perfil_id "
                    "WHERE u.id = %s AND u.ativo = TRUE",
                    (usuario_id,)
                )

                if usuario is None:
                    session.clear()
                    flash("Não foi possível iniciar sua sessão. Faça login novamente.", "erro")
                    return redirect(url_for("index"))

                session["pessoa_id"] = usuario["pessoa_id"]
                session["nome"] = usuario["nome"]
                session["perfil"] = usuario["perfil"]
                session["_csrf_token"] = secrets.token_urlsafe(32)

                flash(resultado.mensagem, "sucesso")
                return redirect(url_for("dashboard"))

            flash(resultado.mensagem, "erro")

        elif acao == "recusar":
            resultado = recusar_termo_lgpd(usuario_id)
            session.clear()
            flash(resultado.mensagem, "erro")
            return redirect(url_for("index"))

    return render_template(
        "termo_lgpd.html",
        termo=TERMO_LGPD,
        versao=VERSAO_TERMO_LGPD,
        nome=session.get("nome_pendente_lgpd", "")
    )


# -------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------

@app.route("/dashboard")
@login_obrigatorio
def dashboard():
    return render_template(
        "dashboard.html",
        nome=session.get("nome"),
        perfil=session.get("perfil")
    )


# -------------------------------------------------------------------
# Logout
# -------------------------------------------------------------------

@app.route("/sair", methods=["POST"])
@login_obrigatorio
def sair():
    if not validar_csrf():
        return redirect(url_for("dashboard"))

    session.clear()
    flash("Você saiu do sistema.", "sucesso")
    return redirect(url_for("index"))

@app.route("/cadastro")
@login_obrigatorio
def cadastro():
    turmas = listar_turmas()

    return render_template(
        "cadastro.html",
        turmas=turmas
    )
    
@app.route("/chamada")
@login_obrigatorio
def chamada():
    return render_template("chamada.html")


@app.route("/relatorios")
@login_obrigatorio
def relatorios():
    return render_template("relatorios.html")


@app.route("/modalidades")
@login_obrigatorio
def modalidades():
    return render_template("modalidades.html")

@app.route("/form-voluntario")
@login_obrigatorio
def form_voluntario():
    return render_template("forms/form-voluntario.html")


@app.route("/form-beneficiario")
@login_obrigatorio
def form_beneficiario():
    return render_template(
        "forms/form-beneficiario.html",
        turmas=listar_turmas()
    )

@app.route("/cadastrar-beneficiario", methods=["POST"])
@login_obrigatorio
def cadastrar_beneficiario_web():

    if not validar_csrf():
        return redirect(url_for("cadastro"))

    try:
        turma_ids = [
            int(turma_id)
            for turma_id in request.form.getlist("turma_ids")
        ]
    except ValueError:
        flash("Seleção de turma inválida.", "erro")
        return redirect(url_for("cadastro"))

    data_nasc = request.form.get("data_nasc", "").strip()

    if data_nasc:
        try:
            data_nasc = (
                f"{data_nasc[8:10]}/"
                f"{data_nasc[5:7]}/"
                f"{data_nasc[0:4]}"
            )
        except (IndexError, ValueError):
            flash("Data de nascimento inválida.", "erro")
            return redirect(url_for("cadastro"))

    responsavel_nome = request.form.get("responsavel_nome", "").strip()
    responsavel_telefone = request.form.get(
        "responsavel_telefone", ""
    ).strip()
    responsavel_cpf = request.form.get(
        "responsavel_cpf", ""
    ).strip()

    responsavel = None

    if responsavel_nome or responsavel_telefone or responsavel_cpf:
        responsavel = {
            "nome": responsavel_nome,
            "telefone": responsavel_telefone,
            "cpf": responsavel_cpf or None,
            "consentimento": (
                request.form.get("consentimento_responsavel") == "on"
            )
        }

    resultado = cadastrar_beneficiario(
        obter_sessao(),
        nome=request.form.get("nome", "").strip(),
        data_nasc=data_nasc,
        cpf=request.form.get("cpf", "").strip(),
        telefone=request.form.get("telefone", "").strip(),
        turma_ids=turma_ids,
        email=request.form.get("email", "").strip(),
        endereco=request.form.get("endereco", "").strip(),
        responsavel=responsavel
    )

    if resultado.ok:
        flash(resultado.mensagem, "sucesso")
    else:
        flash(resultado.mensagem, "erro")

    return redirect(url_for("cadastro"))

@app.route("/cadastrar-voluntario", methods=["POST"])
@login_obrigatorio
def cadastrar_voluntario_web():

    if not validar_csrf():
        return redirect(url_for("cadastro"))

    data_nasc = request.form.get("data_nasc", "").strip()

    if data_nasc:
        data_nasc = (
            f"{data_nasc[8:10]}/"
            f"{data_nasc[5:7]}/"
            f"{data_nasc[0:4]}"
        )

    resultado = cadastrar_voluntario(
        obter_sessao(),
        nome=request.form.get("nome", "").strip(),
        data_nasc=data_nasc,
        cpf=request.form.get("cpf", "").strip(),
        telefone=request.form.get("telefone", "").strip(),
        email=request.form.get("email", "").strip(),
        senha=request.form.get("senha", ""),
        materia_funcao=request.form.get("materia_funcao", "").strip(),
        termo_aceito=request.form.get("termo_assinado") == "on"
    )

    if resultado.ok:
        flash(resultado.mensagem, "sucesso")
    else:
        flash(resultado.mensagem, "erro")

    return redirect(url_for("cadastro"))

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
