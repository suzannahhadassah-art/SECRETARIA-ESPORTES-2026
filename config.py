import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Em nuvem, DATA_ROOT pode apontar para um volume persistente; localmente usa a pasta do projeto.
_data_root_env = os.environ.get("DATA_ROOT", BASE_DIR)
DATA_ROOT = _data_root_env if os.path.isdir(_data_root_env) else BASE_DIR

DB_PATH = os.path.join(DATA_ROOT, "smesp.db")

PORT = int(os.environ.get("PORT", 5000))
HOST = "0.0.0.0"

ADMIN_EMAIL_PADRAO = os.environ.get("ADMIN_EMAIL_PADRAO", "ebutakka@gmail.com")
ADMIN_SENHA_PADRAO = os.environ.get("ADMIN_SENHA_PADRAO", "esportes2026")

DIAS_SEMANA = [
    ("seg", "Segunda"),
    ("ter", "Terça"),
    ("qua", "Quarta"),
    ("qui", "Quinta"),
    ("sex", "Sexta"),
    ("sab", "Sábado"),
    ("dom", "Domingo"),
]
DIA_LABEL = dict(DIAS_SEMANA)

MODALIDADES_SUGERIDAS = [
    "Futebol", "Futsal", "Vôlei", "Basquete", "Natação", "Judô",
    "Karatê", "Atletismo", "Ginástica", "Dança", "Handebol", "Tênis de Mesa",
]
