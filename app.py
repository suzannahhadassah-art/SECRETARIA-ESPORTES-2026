import os

from flask import Flask, redirect, url_for, session, send_from_directory, abort

import config
import database
import uploads
import auth
import professores
import turmas
import ficha_bordo

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smesp-secretaria-esportes-cuiaba-2026-kf83")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB — limite de upload (fotos da Ficha de Bordo)

database.init_db()

app.register_blueprint(auth.bp)
app.register_blueprint(professores.bp)
app.register_blueprint(turmas.bp)
app.register_blueprint(ficha_bordo.bp)

app.jinja_env.globals["usuario_atual"] = auth.usuario_atual
app.jinja_env.globals["DIA_LABEL"] = config.DIA_LABEL
app.jinja_env.globals["DIAS_SEMANA"] = config.DIAS_SEMANA
app.jinja_env.globals["MODALIDADES_SUGERIDAS"] = config.MODALIDADES_SUGERIDAS


@app.route("/")
def index():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))
    if session.get("cargo") == "admin":
        return redirect(url_for("professores.lista"))
    return redirect(url_for("turmas.home"))


@app.route("/arquivos/<path:filename>")
def arquivos(filename):
    """Serve fotos enviadas (ponto, ficha de bordo) — vivem em DATA_ROOT, fora de static/,
    para sobreviver a um novo deploy quando DATA_ROOT aponta para um volume persistente."""
    if "usuario_id" not in session:
        abort(403)
    return send_from_directory(uploads.UPLOAD_DIR, filename)


if __name__ == "__main__":
    print(f"\n Secretaria de Esportes e Lazer — acessível em http://localhost:{config.PORT}\n")
    app.run(host=config.HOST, port=config.PORT, debug=False)
