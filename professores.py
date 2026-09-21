from datetime import datetime, timezone, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, session

import database
from auth import login_required, admin_required

bp = Blueprint("professores", __name__, url_prefix="/professores")

AMT = timezone(timedelta(hours=-4))  # Cuiabá (UTC-4)


def _agora():
    n = datetime.now(AMT)
    return n.strftime("%Y-%m-%d"), n.strftime("%H:%M")


CARGOS_VALIDOS = ("admin", "professor")


@bp.route("/")
@admin_required
def lista():
    professores = database.listar_professores()
    return render_template("professores_lista.html", professores=professores)


# ─── Usuários ─────────────────────────────────────────────────────────────────

@bp.route("/usuarios")
@admin_required
def usuarios():
    todos = database.listar_usuarios()
    turmas = database.listar_turmas(apenas_ativas=True)
    turmas_por_usuario = {
        u["id"]: [t["id"] for t in database.turmas_do_professor(u["id"])]
        for u in todos if u["cargo"] == "professor"
    }
    return render_template("professores_usuarios.html", usuarios=todos, turmas=turmas,
                            turmas_por_usuario=turmas_por_usuario)


@bp.route("/usuarios/criar", methods=["POST"])
@admin_required
def usuario_criar():
    nome = request.form.get("nome", "").strip()
    email = request.form.get("email", "").strip()
    senha = request.form.get("senha", "")
    cargo = request.form.get("cargo", "professor")
    telefone = request.form.get("telefone", "").strip() or None
    cargo_titulo = request.form.get("cargo_titulo", "").strip() or None
    carga_horaria = request.form.get("carga_horaria", "").strip() or None
    acesso_ficha_bordo = 1 if request.form.get("acesso_ficha_bordo") else 0
    acesso_espacos = 1 if request.form.get("acesso_espacos") else 0
    turma_ids = [int(x) for x in request.form.getlist("turmas")]

    if cargo not in CARGOS_VALIDOS:
        cargo = "professor"

    if not nome or not email or len(senha) < 6:
        flash("Preencha nome, e-mail e uma senha com pelo menos 6 caracteres.", "danger")
        return redirect(url_for("professores.usuarios"))

    if database.email_em_uso(email):
        flash("Já existe uma conta com esse e-mail.", "danger")
        return redirect(url_for("professores.usuarios"))

    uid = database.criar_usuario(nome, email, senha, cargo, telefone, cargo_titulo, carga_horaria,
                                  acesso_ficha_bordo, acesso_espacos)
    if cargo == "professor":
        for tid in turma_ids:
            database.adicionar_vinculo_turma(uid, tid)

    flash(f'Conta de "{nome}" criada.', "success")
    return redirect(url_for("professores.usuarios"))


@bp.route("/usuarios/<int:uid>/editar", methods=["POST"])
@admin_required
def usuario_editar(uid):
    nome = request.form.get("nome", "").strip()
    email = request.form.get("email", "").strip()
    cargo = request.form.get("cargo", "professor")
    telefone = request.form.get("telefone", "").strip() or None
    cargo_titulo = request.form.get("cargo_titulo", "").strip() or None
    carga_horaria = request.form.get("carga_horaria", "").strip() or None
    acesso_ficha_bordo = 1 if request.form.get("acesso_ficha_bordo") else 0
    acesso_espacos = 1 if request.form.get("acesso_espacos") else 0
    ativo = 1 if request.form.get("ativo") else 0
    nova_senha = request.form.get("nova_senha", "").strip()
    turma_ids = [int(x) for x in request.form.getlist("turmas")]

    if cargo not in CARGOS_VALIDOS:
        cargo = "professor"

    if not nome or not email:
        flash("Nome e e-mail são obrigatórios.", "danger")
        return redirect(url_for("professores.usuarios"))

    if database.email_em_uso(email, excluir_uid=uid):
        flash("Já existe outra conta com esse e-mail.", "danger")
        return redirect(url_for("professores.usuarios"))

    if nova_senha and len(nova_senha) < 6:
        flash("A nova senha deve ter pelo menos 6 caracteres.", "danger")
        return redirect(url_for("professores.usuarios"))

    database.editar_usuario(uid, nome, email, cargo, telefone, ativo, nova_senha or None,
                             cargo_titulo, carga_horaria, acesso_ficha_bordo, acesso_espacos)

    if cargo == "professor":
        _atualizar_turmas_do_professor(uid, turma_ids)

    if session.get("usuario_id") == uid:
        session["nome"] = nome
        session["cargo"] = cargo

    flash("Conta atualizada.", "success")
    return redirect(url_for("professores.usuarios"))


def _atualizar_turmas_do_professor(uid, turma_ids_desejados):
    """Ajusta os vínculos deste professor sem mexer nos vínculos de outros professores."""
    atuais = {t["id"] for t in database.turmas_do_professor(uid)}
    desejados = set(turma_ids_desejados)
    for tid in desejados - atuais:
        database.adicionar_vinculo_turma(uid, tid)
    for tid in atuais - desejados:
        database.remover_vinculo_turma(uid, tid)


# ─── Ponto ────────────────────────────────────────────────────────────────────

@bp.route("/ponto")
@login_required
def ponto():
    uid = session["usuario_id"]
    hoje, _ = _agora()
    registro_hoje = database.ponto_do_dia(uid, hoje)
    historico = database.historico_ponto(uid)

    minhas_turmas = []
    if session.get("cargo") == "professor":
        for t in database.turmas_do_professor(uid):
            info = dict(t)
            info["foto_hoje"] = database.foto_turma_do_dia(t["id"], hoje)
            minhas_turmas.append(info)

    return render_template("professores_ponto.html", hoje=hoje, registro_hoje=registro_hoje,
                            historico=historico, minhas_turmas=minhas_turmas)


def _safe_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


@bp.route("/ponto/registrar", methods=["POST"])
@login_required
def ponto_registrar():
    uid = session["usuario_id"]
    tipo = request.form.get("tipo")
    if tipo not in ("entrada", "saida"):
        flash("Ação inválida.", "danger")
        return redirect(url_for("professores.ponto"))

    lat = _safe_float(request.form.get("latitude"))
    lng = _safe_float(request.form.get("longitude"))

    hoje, hora = _agora()
    database.registrar_ponto(uid, hoje, hora, tipo, lat=lat, lng=lng)
    label = "Entrada" if tipo == "entrada" else "Saída"
    aviso_local = "" if (lat and lng) else " (sem localização)"
    flash(f"{label} registrada às {hora}{aviso_local}.", "success")
    return redirect(url_for("professores.ponto"))


@bp.route("/ponto/relatorio")
@admin_required
def ponto_relatorio():
    usuario_id = request.args.get("usuario_id", type=int)
    data_inicio = request.args.get("data_inicio") or None
    data_fim = request.args.get("data_fim") or None
    registros = database.relatorio_ponto(usuario_id, data_inicio, data_fim)
    professores = database.listar_professores()
    return render_template("professores_ponto_relatorio.html", registros=registros,
                            professores=professores, usuario_id=usuario_id,
                            data_inicio=data_inicio, data_fim=data_fim)
