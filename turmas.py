from datetime import datetime, timezone, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort

import database
from uploads import salvar_foto
from auth import login_required, admin_required

bp = Blueprint("turmas", __name__, url_prefix="/turmas")

AMT = timezone(timedelta(hours=-4))  # Cuiabá (UTC-4)


def _hoje():
    return datetime.now(AMT).strftime("%Y-%m-%d")


def _pode_acessar_turma(tid):
    if session.get("cargo") == "admin":
        return True
    return database.professor_tem_turma(session["usuario_id"], tid)


def _exigir_acesso_turma(tid):
    if not _pode_acessar_turma(tid):
        abort(403)


def _agrupar_por_modalidade(turmas_info):
    grupos = {}
    for info in turmas_info:
        chave = info.get("modalidade") or "Sem modalidade"
        grupos.setdefault(chave, []).append(info)
    return dict(sorted(grupos.items(), key=lambda kv: kv[0].lower()))


@bp.route("/")
@login_required
def home():
    hoje = _hoje()
    if session.get("cargo") == "admin":
        turmas_info = []
        for t in database.listar_turmas():
            info = dict(t)
            info["qtd_alunos"] = database.contar_alunos(t["id"])
            info["professores"] = database.professores_da_turma(t["id"])
            info["foto_hoje"] = database.foto_turma_do_dia(t["id"], hoje)
            turmas_info.append(info)
        todos_professores = database.listar_professores()
        return render_template("turmas_home.html", turmas=turmas_info, grupos=_agrupar_por_modalidade(turmas_info),
                                modo="admin", todos_professores=todos_professores, hoje=hoje)

    turmas_info = []
    for t in database.turmas_do_professor(session["usuario_id"]):
        info = dict(t)
        info["qtd_alunos"] = database.contar_alunos(t["id"])
        info["foto_hoje"] = database.foto_turma_do_dia(t["id"], hoje)
        turmas_info.append(info)
    return render_template("turmas_home.html", turmas=turmas_info, grupos=_agrupar_por_modalidade(turmas_info),
                            modo="professor", hoje=hoje)


@bp.route("/criar", methods=["POST"])
@admin_required
def criar():
    nome = request.form.get("nome", "").strip()
    modalidade = request.form.get("modalidade", "").strip() or None
    local = request.form.get("local", "").strip() or None
    dias = ",".join(request.form.getlist("dias_semana"))
    hora_inicio = request.form.get("hora_inicio") or None
    hora_fim = request.form.get("hora_fim") or None

    if not nome:
        flash("Informe o nome da turma.", "danger")
        return redirect(url_for("turmas.home"))

    database.criar_turma(nome, modalidade, local, dias, hora_inicio, hora_fim)
    flash(f'Turma "{nome}" criada.', "success")
    return redirect(url_for("turmas.home"))


@bp.route("/<int:tid>/editar", methods=["POST"])
@admin_required
def editar(tid):
    nome = request.form.get("nome", "").strip()
    modalidade = request.form.get("modalidade", "").strip() or None
    local = request.form.get("local", "").strip() or None
    dias = ",".join(request.form.getlist("dias_semana"))
    hora_inicio = request.form.get("hora_inicio") or None
    hora_fim = request.form.get("hora_fim") or None
    ativo = 1 if request.form.get("ativo") else 0

    if not nome:
        flash("Informe o nome da turma.", "danger")
        return redirect(url_for("turmas.home"))

    database.editar_turma(tid, nome, modalidade, local, dias, hora_inicio, hora_fim, ativo)
    flash("Turma atualizada.", "success")
    return redirect(url_for("turmas.home"))


@bp.route("/<int:tid>/excluir", methods=["POST"])
@admin_required
def excluir(tid):
    turma = database.obter_turma(tid)
    if not turma:
        abort(404)
    nome = turma["nome"]
    database.excluir_turma(tid)
    flash(f'Turma "{nome}" excluída.', "success")
    return redirect(url_for("turmas.home"))


@bp.route("/<int:tid>/professores", methods=["POST"])
@admin_required
def vincular_professores(tid):
    ids = [int(x) for x in request.form.getlist("professores")]
    database.vincular_professores_turma(tid, ids)
    flash("Vínculos atualizados.", "success")
    return redirect(url_for("turmas.home"))


@bp.route("/<int:tid>/foto", methods=["POST"])
@login_required
def registrar_foto(tid):
    _exigir_acesso_turma(tid)
    if not database.obter_turma(tid):
        abort(404)

    foto = salvar_foto(request.files.get("foto"))
    if not foto:
        flash("Envie uma foto da turma (jpg, png ou webp).", "danger")
        return redirect(url_for("turmas.home"))

    database.registrar_foto_turma(tid, _hoje(), foto, session["usuario_id"])
    flash("Foto do dia registrada.", "success")
    return redirect(url_for("turmas.home"))


# ─── Alunos ───────────────────────────────────────────────────────────────────

@bp.route("/<int:tid>/alunos")
@login_required
def alunos(tid):
    _exigir_acesso_turma(tid)
    turma = database.obter_turma(tid)
    if not turma:
        abort(404)
    lista = database.listar_alunos(tid)
    return render_template("turmas_alunos.html", turma=turma, alunos=lista)


@bp.route("/<int:tid>/alunos/criar", methods=["POST"])
@login_required
def aluno_criar(tid):
    _exigir_acesso_turma(tid)
    nome = request.form.get("nome", "").strip()
    telefone = request.form.get("telefone", "").strip() or None
    responsavel_nome = request.form.get("responsavel_nome", "").strip() or None
    responsavel_telefone = request.form.get("responsavel_telefone", "").strip() or None
    data_nasc = request.form.get("data_nasc") or None

    if not nome:
        flash("Informe o nome do aluno.", "danger")
        return redirect(url_for("turmas.alunos", tid=tid))

    database.criar_aluno(nome, tid, telefone, responsavel_nome, responsavel_telefone, data_nasc)
    flash(f'Aluno "{nome}" cadastrado.', "success")
    return redirect(url_for("turmas.alunos", tid=tid))


@bp.route("/alunos/<int:aid>/editar", methods=["POST"])
@login_required
def aluno_editar(aid):
    aluno = database.obter_aluno(aid)
    if not aluno:
        abort(404)
    _exigir_acesso_turma(aluno["turma_id"])

    nome = request.form.get("nome", "").strip()
    telefone = request.form.get("telefone", "").strip() or None
    responsavel_nome = request.form.get("responsavel_nome", "").strip() or None
    responsavel_telefone = request.form.get("responsavel_telefone", "").strip() or None
    data_nasc = request.form.get("data_nasc") or None
    ativo = 1 if request.form.get("ativo") else 0

    if not nome:
        flash("Informe o nome do aluno.", "danger")
        return redirect(url_for("turmas.alunos", tid=aluno["turma_id"]))

    database.editar_aluno(aid, nome, telefone, responsavel_nome, responsavel_telefone, data_nasc, ativo)
    flash("Aluno atualizado.", "success")
    return redirect(url_for("turmas.alunos", tid=aluno["turma_id"]))


# ─── Chamada ──────────────────────────────────────────────────────────────────

@bp.route("/<int:tid>/chamada", methods=["GET", "POST"])
@login_required
def chamada(tid):
    _exigir_acesso_turma(tid)
    turma = database.obter_turma(tid)
    if not turma:
        abort(404)

    if request.method == "POST":
        data = request.form.get("data") or _hoje()
        registros = []
        for chave, valor in request.form.items():
            if chave.startswith("status_"):
                aluno_id = int(chave.replace("status_", ""))
                registros.append({"aluno_id": aluno_id, "status": valor})
        if registros:
            database.salvar_chamada(tid, data, registros, session["usuario_id"])
            flash(f"Chamada de {data} salva com sucesso.", "success")
        return redirect(url_for("turmas.chamada", tid=tid, data=data))

    data = request.args.get("data") or _hoje()
    lista = database.chamada_do_dia(tid, data)
    ja_feita = database.chamada_ja_feita(tid, data)
    return render_template("turmas_chamada.html", turma=turma, alunos=lista, data=data, ja_feita=ja_feita)


@bp.route("/chamadas-realizadas")
@admin_required
def chamadas_realizadas():
    tid = request.args.get("turma_id", type=int)
    data_inicio = request.args.get("data_inicio") or None
    data_fim = request.args.get("data_fim") or None
    resumo = database.listar_chamadas_resumo(tid, data_inicio, data_fim)
    turmas_todas = database.listar_turmas()
    return render_template("turmas_chamadas_realizadas.html", resumo=resumo, turmas=turmas_todas,
                            turma_id=tid, data_inicio=data_inicio, data_fim=data_fim)
