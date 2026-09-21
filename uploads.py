import os
import uuid

import config

EXTENSOES_PERMITIDAS = {"jpg", "jpeg", "png", "webp"}

# Fica dentro de DATA_ROOT (não de static/) para sobreviver a um novo deploy —
# no Railway, DATA_ROOT aponta para o volume persistente; o restante do
# código da aplicação (incluindo static/) é recriado do zero a cada deploy.
UPLOAD_DIR = os.path.join(config.DATA_ROOT, "uploads")


def _extensao_valida(nome_arquivo):
    return "." in nome_arquivo and nome_arquivo.rsplit(".", 1)[1].lower() in EXTENSOES_PERMITIDAS


def salvar_foto(arquivo):
    """Salva a foto enviada com um nome gerado (nunca confia no nome original) e retorna o nome salvo."""
    if not arquivo or not arquivo.filename:
        return None
    if not _extensao_valida(arquivo.filename):
        return None
    ext = arquivo.filename.rsplit(".", 1)[1].lower()
    nome_salvo = f"{uuid.uuid4().hex}.{ext}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    arquivo.save(os.path.join(UPLOAD_DIR, nome_salvo))
    return nome_salvo
