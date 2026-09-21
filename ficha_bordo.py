from datetime import datetime, timezone, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort

import database
from uploads import salvar_foto
from auth import ficha_bordo_required

bp = Blueprint("ficha_bordo", __name__, url_prefix="/ficha-bordo")

AMT = timezone(timedelta(hours=-4))  # Cuiabá (UTC-4)


def _agora():
    n = datetime.now(AMT)
    return n.strftime("%Y-%m-%d"), n.strftime("%H:%M")


@bp.route("/")
@ficha_bordo_required
def home():
    em_andamento = database.listar_fichas_bordo(apenas_em_andamento=True)
    historico = database.listar_fichas_bordo()
    veiculos_recentes = database.veiculos_usados_recentemente()
    hoje, hora = _agora()
    return render_template("ficha_bordo_home.html", em_andamento=em_andamento, historico=historico,
                            veiculos_recentes=veiculos_recentes, hoje=hoje, hora=hora)


@bp.route("/registrar-saida", methods=["POST"])
@ficha_bordo_required
def registrar_saida():
    veiculo = request.form.get("veiculo", "").strip()
    motorista = request.form.get("motorista", "").strip()
    destino = request.form.get("destino", "").strip() or None
    km_inicial = request.form.get("km_inicial", "").strip()
    observacao = request.form.get("observacao_missao", "").strip() or None

    if not veiculo or not motorista or not km_inicial:
        flash("Informe o veículo, o motorista e o KM inicial.", "danger")
        return redirect(url_for("ficha_bordo.home"))

    try:
        km_inicial = int(km_inicial)
    except ValueError:
        flash("O KM inicial deve ser um número.", "danger")
        return redirect(url_for("ficha_bordo.home"))

    foto = salvar_foto(request.files.get("foto_km_inicial"))
    if not foto:
        flash("Envie uma foto do KM inicial (jpg, png ou webp).", "danger")
        return redirect(url_for("ficha_bordo.home"))

    data, hora = _agora()
    database.registrar_saida_veiculo(veiculo, motorista, destino, data, hora,
                                      km_inicial, foto, observacao, session["usuario_id"])
    flash(f'Saída do veículo "{veiculo}" registrada às {hora}.', "success")
    return redirect(url_for("ficha_bordo.home"))


@bp.route("/<int:fid>/registrar-chegada", methods=["POST"])
@ficha_bordo_required
def registrar_chegada(fid):
    ficha = database.obter_ficha_bordo(fid)
    if not ficha:
        abort(404)
    if ficha["km_final"] is not None:
        flash("Esta ficha já foi encerrada.", "warning")
        return redirect(url_for("ficha_bordo.home"))

    km_final = request.form.get("km_final", "").strip()
    observacao = request.form.get("observacao_missao", "").strip() or ficha["observacao_missao"]

    if not km_final:
        flash("Informe o KM final.", "danger")
        return redirect(url_for("ficha_bordo.home"))

    try:
        km_final = int(km_final)
    except ValueError:
        flash("O KM final deve ser um número.", "danger")
        return redirect(url_for("ficha_bordo.home"))

    if km_final < ficha["km_inicial"]:
        flash("O KM final não pode ser menor que o KM inicial.", "danger")
        return redirect(url_for("ficha_bordo.home"))

    foto = salvar_foto(request.files.get("foto_km_final"))
    if not foto:
        flash("Envie uma foto do KM final (jpg, png ou webp).", "danger")
        return redirect(url_for("ficha_bordo.home"))

    data, hora = _agora()
    database.registrar_chegada_veiculo(fid, data, hora, km_final, foto, observacao)
    flash(f'Chegada registrada às {hora}. Percurso: {km_final - ficha["km_inicial"]} km.', "success")
    return redirect(url_for("ficha_bordo.home"))
