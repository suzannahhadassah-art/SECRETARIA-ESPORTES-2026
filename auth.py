from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

import database

bp = Blueprint("auth", __name__)


def usuario_atual():
    uid = session.get("usuario_id")
    if not uid:
        return None
    return database.obter_usuario(uid)


def _proximo_url_seguro(candidato):
    """Só aceita caminhos internos (evita redirecionar para outro site)."""
    if candidato and candidato.startswith("/") and not candidato.startswith("//"):
        return candidato
    return url_for("index")


def _sessao_valida():
    """Usuário atual, revalidado no banco a cada request — pega contas desativadas
    ou trocadas de papel mesmo que a sessão antiga ainda esteja aberta no navegador."""
    uid = session.get("usuario_id")
    if not uid:
        return None
    usuario = database.obter_usuario(uid)
    if not usuario or not usuario["ativo"]:
        return None
    return usuario


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _sessao_valida():
            session.clear()
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        usuario = _sessao_valida()
        if not usuario:
            session.clear()
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if usuario["cargo"] != "admin":
            flash("Acesso restrito a administradores.", "danger")
            return redirect(url_for("turmas.home"))
        return f(*args, **kwargs)
    return decorated


def ficha_bordo_required(f):
    """Admin sempre acessa; professor só se a conta tiver acesso_ficha_bordo marcado."""
    @wraps(f)
    def decorated(*args, **kwargs):
        usuario = _sessao_valida()
        if not usuario:
            session.clear()
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if usuario["cargo"] != "admin" and not usuario["acesso_ficha_bordo"]:
            flash("Você não tem acesso à Ficha de Bordo. Peça ao administrador para liberar em Usuários.", "danger")
            return redirect(url_for("turmas.home"))
        return f(*args, **kwargs)
    return decorated


@bp.route("/login", methods=["GET", "POST"])
def login():
    if "usuario_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")
        usuario = database.obter_usuario_por_email(email)

        if usuario and usuario["ativo"] and check_password_hash(usuario["senha_hash"], senha):
            session.clear()
            session["usuario_id"] = usuario["id"]
            session["nome"] = usuario["nome"]
            session["cargo"] = usuario["cargo"]
            return redirect(_proximo_url_seguro(request.args.get("next")))
        flash("E-mail ou senha incorretos.", "danger")

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
