import sqlite3

from werkzeug.security import generate_password_hash

import config


def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            nome                TEXT NOT NULL,
            email               TEXT NOT NULL,
            senha_hash          TEXT NOT NULL,
            cargo               TEXT NOT NULL DEFAULT 'professor',
            cargo_titulo        TEXT,
            carga_horaria       TEXT,
            telefone            TEXT,
            acesso_ficha_bordo  INTEGER NOT NULL DEFAULT 0,
            acesso_espacos      INTEGER NOT NULL DEFAULT 0,
            ativo               INTEGER NOT NULL DEFAULT 1,
            criado_em           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(email COLLATE NOCASE)
        );

        CREATE TABLE IF NOT EXISTS turmas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            nome         TEXT NOT NULL,
            modalidade   TEXT,
            local        TEXT,
            dias_semana  TEXT,
            hora_inicio  TEXT,
            hora_fim     TEXT,
            ativo        INTEGER NOT NULL DEFAULT 1,
            criado_em    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS professor_turma (
            usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
            turma_id    INTEGER NOT NULL REFERENCES turmas(id),
            PRIMARY KEY (usuario_id, turma_id)
        );

        CREATE TABLE IF NOT EXISTS alunos (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            nome                  TEXT NOT NULL,
            turma_id              INTEGER NOT NULL REFERENCES turmas(id),
            telefone              TEXT,
            responsavel_nome      TEXT,
            responsavel_telefone  TEXT,
            data_nasc             TEXT,
            ativo                 INTEGER NOT NULL DEFAULT 1,
            criado_em             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_alunos_turma ON alunos(turma_id);

        CREATE TABLE IF NOT EXISTS ponto (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id    INTEGER NOT NULL REFERENCES usuarios(id),
            data          TEXT NOT NULL,
            hora_entrada  TEXT,
            hora_saida    TEXT,
            lat_entrada   REAL,
            lng_entrada   REAL,
            lat_saida     REAL,
            lng_saida     REAL,
            criado_em     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(usuario_id, data)
        );

        CREATE TABLE IF NOT EXISTS fotos_turma (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            turma_id        INTEGER NOT NULL REFERENCES turmas(id),
            data            TEXT NOT NULL,
            foto            TEXT NOT NULL,
            registrado_por  INTEGER REFERENCES usuarios(id),
            criado_em       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(turma_id, data)
        );

        CREATE TABLE IF NOT EXISTS chamada (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id        INTEGER NOT NULL REFERENCES alunos(id),
            turma_id        INTEGER NOT NULL REFERENCES turmas(id),
            data            TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'ausente',
            registrado_por  INTEGER REFERENCES usuarios(id),
            criado_em       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(aluno_id, turma_id, data)
        );
        CREATE INDEX IF NOT EXISTS idx_chamada_turma_data ON chamada(turma_id, data);

        CREATE TABLE IF NOT EXISTS fichas_bordo (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            veiculo            TEXT NOT NULL,
            motorista          TEXT NOT NULL,
            destino            TEXT,
            data_saida         TEXT NOT NULL,
            hora_saida         TEXT NOT NULL,
            km_inicial         INTEGER NOT NULL,
            foto_km_inicial    TEXT,
            data_volta         TEXT,
            hora_volta         TEXT,
            km_final           INTEGER,
            foto_km_final      TEXT,
            observacao_missao  TEXT,
            registrado_por     INTEGER NOT NULL REFERENCES usuarios(id),
            criado_em          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_fichas_bordo_data ON fichas_bordo(data_saida);
    """)
    conn.commit()

    # ── Migrações: colunas novas em bancos já existentes ────────────────────
    # CREATE TABLE IF NOT EXISTS só cria a tabela na primeira vez; um banco criado
    # antes de uma coluna existir precisa dela adicionada aqui.
    novas_colunas = [
        ("ponto", "lat_entrada", "REAL"),
        ("ponto", "lng_entrada", "REAL"),
        ("ponto", "lat_saida",   "REAL"),
        ("ponto", "lng_saida",   "REAL"),
        ("usuarios", "cargo_titulo",  "TEXT"),
        ("usuarios", "carga_horaria", "TEXT"),
        ("usuarios", "acesso_ficha_bordo", "INTEGER NOT NULL DEFAULT 0"),
        ("usuarios", "acesso_espacos", "INTEGER NOT NULL DEFAULT 0"),
    ]
    for tabela, coluna, tipo in novas_colunas:
        try:
            conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # coluna já existe

    existe = conn.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone()
    if not existe:
        # INSERT OR IGNORE: com múltiplos workers (gunicorn) subindo ao mesmo tempo,
        # mais de um processo pode passar por este "if" antes de qualquer um commitar.
        # A restrição UNIQUE(email) faz o segundo silenciosamente não fazer nada,
        # em vez de derrubar aquele worker com um erro de integridade.
        cur = conn.execute(
            "INSERT OR IGNORE INTO usuarios (nome, email, senha_hash, cargo) VALUES (?,?,?,?)",
            ("Administrador", config.ADMIN_EMAIL_PADRAO,
             generate_password_hash(config.ADMIN_SENHA_PADRAO), "admin"),
        )
        conn.commit()
        if cur.rowcount:
            print("=" * 64)
            print(" Conta de administrador criada automaticamente:")
            print(f"   E-mail: {config.ADMIN_EMAIL_PADRAO}")
            print(f"   Senha:  {config.ADMIN_SENHA_PADRAO}")
            print(" Troque a senha assim que entrar (Usuários > editar).")
            print("=" * 64)

    conn.close()


# ─── Usuários ─────────────────────────────────────────────────────────────────

def obter_usuario(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    conn.close()
    return row


def obter_usuario_por_email(email):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE email=? COLLATE NOCASE", (email,)
    ).fetchone()
    conn.close()
    return row


def listar_usuarios():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM usuarios ORDER BY cargo, nome COLLATE NOCASE"
    ).fetchall()
    conn.close()
    return rows


def listar_professores():
    """Contas com cargo=professor, já com contagem de turmas vinculadas e último ponto batido."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.*,
               (SELECT COUNT(*) FROM professor_turma pt WHERE pt.usuario_id = u.id) AS qtd_turmas,
               (SELECT MAX(data) FROM ponto p WHERE p.usuario_id = u.id) AS ultimo_ponto_data
        FROM usuarios u
        WHERE u.cargo = 'professor'
        ORDER BY u.nome COLLATE NOCASE
    """).fetchall()
    conn.close()
    return rows


def email_em_uso(email, excluir_uid=None):
    conn = get_conn()
    if excluir_uid:
        row = conn.execute(
            "SELECT 1 FROM usuarios WHERE email=? COLLATE NOCASE AND id != ?",
            (email, excluir_uid),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM usuarios WHERE email=? COLLATE NOCASE", (email,)
        ).fetchone()
    conn.close()
    return row is not None


def criar_usuario(nome, email, senha, cargo, telefone=None, cargo_titulo=None, carga_horaria=None,
                   acesso_ficha_bordo=0, acesso_espacos=0):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO usuarios (nome, email, senha_hash, cargo, telefone, cargo_titulo, carga_horaria,
           acesso_ficha_bordo, acesso_espacos) VALUES (?,?,?,?,?,?,?,?,?)""",
        (nome, email, generate_password_hash(senha), cargo, telefone, cargo_titulo, carga_horaria,
         acesso_ficha_bordo, acesso_espacos),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def editar_usuario(uid, nome, email, cargo, telefone, ativo, nova_senha=None,
                    cargo_titulo=None, carga_horaria=None, acesso_ficha_bordo=0, acesso_espacos=0):
    conn = get_conn()
    if nova_senha:
        conn.execute(
            """UPDATE usuarios SET nome=?, email=?, cargo=?, telefone=?, ativo=?, senha_hash=?,
               cargo_titulo=?, carga_horaria=?, acesso_ficha_bordo=?, acesso_espacos=? WHERE id=?""",
            (nome, email, cargo, telefone, ativo, generate_password_hash(nova_senha),
             cargo_titulo, carga_horaria, acesso_ficha_bordo, acesso_espacos, uid),
        )
    else:
        conn.execute(
            """UPDATE usuarios SET nome=?, email=?, cargo=?, telefone=?, ativo=?,
               cargo_titulo=?, carga_horaria=?, acesso_ficha_bordo=?, acesso_espacos=? WHERE id=?""",
            (nome, email, cargo, telefone, ativo, cargo_titulo, carga_horaria,
             acesso_ficha_bordo, acesso_espacos, uid),
        )
    conn.commit()
    conn.close()


# ─── Turmas ───────────────────────────────────────────────────────────────────

def listar_turmas(apenas_ativas=False):
    conn = get_conn()
    sql = "SELECT * FROM turmas"
    if apenas_ativas:
        sql += " WHERE ativo=1"
    sql += " ORDER BY nome COLLATE NOCASE"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows


def obter_turma(tid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM turmas WHERE id=?", (tid,)).fetchone()
    conn.close()
    return row


def excluir_turma(tid):
    """Apaga a turma e tudo que depende dela (vínculos, alunos, chamadas, fotos do dia)."""
    conn = get_conn()
    conn.execute("DELETE FROM chamada WHERE turma_id=?", (tid,))
    conn.execute("DELETE FROM fotos_turma WHERE turma_id=?", (tid,))
    conn.execute("DELETE FROM alunos WHERE turma_id=?", (tid,))
    conn.execute("DELETE FROM professor_turma WHERE turma_id=?", (tid,))
    conn.execute("DELETE FROM turmas WHERE id=?", (tid,))
    conn.commit()
    conn.close()


def criar_turma(nome, modalidade, local, dias_semana, hora_inicio, hora_fim):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO turmas (nome, modalidade, local, dias_semana, hora_inicio, hora_fim)
           VALUES (?,?,?,?,?,?)""",
        (nome, modalidade, local, dias_semana, hora_inicio, hora_fim),
    )
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return tid


def editar_turma(tid, nome, modalidade, local, dias_semana, hora_inicio, hora_fim, ativo):
    conn = get_conn()
    conn.execute(
        """UPDATE turmas SET nome=?, modalidade=?, local=?, dias_semana=?, hora_inicio=?,
           hora_fim=?, ativo=? WHERE id=?""",
        (nome, modalidade, local, dias_semana, hora_inicio, hora_fim, ativo, tid),
    )
    conn.commit()
    conn.close()


def turmas_do_professor(uid):
    conn = get_conn()
    rows = conn.execute("""
        SELECT t.* FROM turmas t
        JOIN professor_turma pt ON pt.turma_id = t.id
        WHERE pt.usuario_id = ? AND t.ativo = 1
        ORDER BY t.nome COLLATE NOCASE
    """, (uid,)).fetchall()
    conn.close()
    return rows


def professores_da_turma(tid):
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.* FROM usuarios u
        JOIN professor_turma pt ON pt.usuario_id = u.id
        WHERE pt.turma_id = ?
        ORDER BY u.nome COLLATE NOCASE
    """, (tid,)).fetchall()
    conn.close()
    return rows


def vincular_professores_turma(tid, usuario_ids):
    conn = get_conn()
    conn.execute("DELETE FROM professor_turma WHERE turma_id=?", (tid,))
    for uid in usuario_ids:
        conn.execute(
            "INSERT OR IGNORE INTO professor_turma (usuario_id, turma_id) VALUES (?,?)",
            (uid, tid),
        )
    conn.commit()
    conn.close()


def adicionar_vinculo_turma(uid, tid):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO professor_turma (usuario_id, turma_id) VALUES (?,?)", (uid, tid)
    )
    conn.commit()
    conn.close()


def remover_vinculo_turma(uid, tid):
    conn = get_conn()
    conn.execute(
        "DELETE FROM professor_turma WHERE usuario_id=? AND turma_id=?", (uid, tid)
    )
    conn.commit()
    conn.close()


def professor_tem_turma(uid, tid):
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM professor_turma WHERE usuario_id=? AND turma_id=?", (uid, tid)
    ).fetchone()
    conn.close()
    return row is not None


# ─── Alunos ───────────────────────────────────────────────────────────────────

def listar_alunos(turma_id, apenas_ativos=True):
    conn = get_conn()
    sql = "SELECT * FROM alunos WHERE turma_id=?"
    if apenas_ativos:
        sql += " AND ativo=1"
    sql += " ORDER BY nome COLLATE NOCASE"
    rows = conn.execute(sql, (turma_id,)).fetchall()
    conn.close()
    return rows


def obter_aluno(aid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM alunos WHERE id=?", (aid,)).fetchone()
    conn.close()
    return row


def contar_alunos(turma_id):
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM alunos WHERE turma_id=? AND ativo=1", (turma_id,)
    ).fetchone()[0]
    conn.close()
    return n


def criar_aluno(nome, turma_id, telefone, responsavel_nome, responsavel_telefone, data_nasc):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO alunos (nome, turma_id, telefone, responsavel_nome, responsavel_telefone, data_nasc)
           VALUES (?,?,?,?,?,?)""",
        (nome, turma_id, telefone, responsavel_nome, responsavel_telefone, data_nasc),
    )
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid


def editar_aluno(aid, nome, telefone, responsavel_nome, responsavel_telefone, data_nasc, ativo):
    conn = get_conn()
    conn.execute(
        """UPDATE alunos SET nome=?, telefone=?, responsavel_nome=?, responsavel_telefone=?,
           data_nasc=?, ativo=? WHERE id=?""",
        (nome, telefone, responsavel_nome, responsavel_telefone, data_nasc, ativo, aid),
    )
    conn.commit()
    conn.close()


# ─── Ponto ────────────────────────────────────────────────────────────────────

def ponto_do_dia(usuario_id, data):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM ponto WHERE usuario_id=? AND data=?", (usuario_id, data)
    ).fetchone()
    conn.close()
    return row


def registrar_ponto(usuario_id, data, hora, tipo, lat=None, lng=None):
    """tipo: 'entrada' ou 'saida'."""
    conn = get_conn()
    existente = conn.execute(
        "SELECT id FROM ponto WHERE usuario_id=? AND data=?", (usuario_id, data)
    ).fetchone()

    if tipo == "entrada":
        campos, valores = ["hora_entrada", "lat_entrada", "lng_entrada"], [hora, lat, lng]
    else:
        campos, valores = ["hora_saida", "lat_saida", "lng_saida"], [hora, lat, lng]

    if existente:
        set_clause = ", ".join(f"{c}=?" for c in campos)
        conn.execute(f"UPDATE ponto SET {set_clause} WHERE id=?", (*valores, existente["id"]))
    else:
        col_clause = ", ".join(campos)
        ph_clause = ", ".join("?" for _ in campos)
        conn.execute(
            f"INSERT INTO ponto (usuario_id, data, {col_clause}) VALUES (?,?,{ph_clause})",
            (usuario_id, data, *valores),
        )
    conn.commit()
    conn.close()


def historico_ponto(usuario_id, limite=30):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM ponto WHERE usuario_id=? ORDER BY data DESC LIMIT ?",
        (usuario_id, limite),
    ).fetchall()
    conn.close()
    return rows


def relatorio_ponto(usuario_id=None, data_inicio=None, data_fim=None):
    conn = get_conn()
    sql = """SELECT p.*, u.nome AS usuario_nome FROM ponto p
             JOIN usuarios u ON u.id = p.usuario_id WHERE 1=1"""
    params = []
    if usuario_id:
        sql += " AND p.usuario_id=?"
        params.append(usuario_id)
    if data_inicio:
        sql += " AND p.data >= ?"
        params.append(data_inicio)
    if data_fim:
        sql += " AND p.data <= ?"
        params.append(data_fim)
    sql += " ORDER BY p.data DESC, u.nome COLLATE NOCASE"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


# ─── Chamada ──────────────────────────────────────────────────────────────────

def chamada_do_dia(turma_id, data):
    """Alunos ativos da turma com o status da chamada nesse dia (None se ainda não marcado)."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT a.id, a.nome, c.status
        FROM alunos a
        LEFT JOIN chamada c ON c.aluno_id = a.id AND c.turma_id = ? AND c.data = ?
        WHERE a.turma_id = ? AND a.ativo = 1
        ORDER BY a.nome COLLATE NOCASE
    """, (turma_id, data, turma_id)).fetchall()
    conn.close()
    return rows


def chamada_ja_feita(turma_id, data):
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM chamada WHERE turma_id=? AND data=? LIMIT 1", (turma_id, data)
    ).fetchone()
    conn.close()
    return row is not None


def salvar_chamada(turma_id, data, registros, registrado_por):
    """registros: lista de dicts {'aluno_id':.., 'status':..}."""
    conn = get_conn()
    for r in registros:
        conn.execute("""
            INSERT INTO chamada (aluno_id, turma_id, data, status, registrado_por)
            VALUES (?,?,?,?,?)
            ON CONFLICT(aluno_id, turma_id, data)
            DO UPDATE SET status=excluded.status, registrado_por=excluded.registrado_por
        """, (r["aluno_id"], turma_id, data, r["status"], registrado_por))
    conn.commit()
    conn.close()


def listar_chamadas_resumo(turma_id=None, data_inicio=None, data_fim=None):
    """Uma linha por turma+data, com contagem de presentes/ausentes/justificadas."""
    conn = get_conn()
    sql = """
        SELECT c.turma_id, t.nome AS turma_nome, c.data,
               SUM(CASE WHEN c.status='presente' THEN 1 ELSE 0 END) AS presentes,
               SUM(CASE WHEN c.status='ausente' THEN 1 ELSE 0 END) AS ausentes,
               SUM(CASE WHEN c.status='justificada' THEN 1 ELSE 0 END) AS justificadas,
               COUNT(*) AS total,
               u.nome AS registrado_por_nome
        FROM chamada c
        JOIN turmas t ON t.id = c.turma_id
        LEFT JOIN usuarios u ON u.id = c.registrado_por
        WHERE 1=1
    """
    params = []
    if turma_id:
        sql += " AND c.turma_id=?"
        params.append(turma_id)
    if data_inicio:
        sql += " AND c.data >= ?"
        params.append(data_inicio)
    if data_fim:
        sql += " AND c.data <= ?"
        params.append(data_fim)
    sql += " GROUP BY c.turma_id, c.data ORDER BY c.data DESC, t.nome COLLATE NOCASE"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


# ─── Ficha de Bordo (veículos) ─────────────────────────────────────────────────

def listar_fichas_bordo(apenas_em_andamento=False):
    conn = get_conn()
    sql = "SELECT * FROM fichas_bordo"
    if apenas_em_andamento:
        sql += " WHERE km_final IS NULL"
    sql += " ORDER BY data_saida DESC, hora_saida DESC"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows


def obter_ficha_bordo(fid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM fichas_bordo WHERE id=?", (fid,)).fetchone()
    conn.close()
    return row


def veiculos_usados_recentemente(limite=10):
    """Lista de veículos já usados, para sugestão (datalist) no formulário."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT veiculo FROM fichas_bordo ORDER BY criado_em DESC LIMIT ?",
        (limite,),
    ).fetchall()
    conn.close()
    return [r["veiculo"] for r in rows]


def registrar_saida_veiculo(veiculo, motorista, destino, data_saida, hora_saida,
                             km_inicial, foto_km_inicial, observacao_missao, registrado_por):
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO fichas_bordo
            (veiculo, motorista, destino, data_saida, hora_saida, km_inicial,
             foto_km_inicial, observacao_missao, registrado_por)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (veiculo, motorista, destino, data_saida, hora_saida, km_inicial,
          foto_km_inicial, observacao_missao, registrado_por))
    conn.commit()
    fid = cur.lastrowid
    conn.close()
    return fid


def registrar_chegada_veiculo(fid, data_volta, hora_volta, km_final, foto_km_final, observacao_missao):
    conn = get_conn()
    conn.execute("""
        UPDATE fichas_bordo
        SET data_volta=?, hora_volta=?, km_final=?, foto_km_final=?, observacao_missao=?
        WHERE id=?
    """, (data_volta, hora_volta, km_final, foto_km_final, observacao_missao, fid))
    conn.commit()
    conn.close()


# ─── Foto do dia (turma) ────────────────────────────────────────────────────

def foto_turma_do_dia(turma_id, data):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM fotos_turma WHERE turma_id=? AND data=?", (turma_id, data)
    ).fetchone()
    conn.close()
    return row


def registrar_foto_turma(turma_id, data, foto, registrado_por):
    conn = get_conn()
    conn.execute("""
        INSERT INTO fotos_turma (turma_id, data, foto, registrado_por)
        VALUES (?,?,?,?)
        ON CONFLICT(turma_id, data) DO UPDATE SET foto=excluded.foto, registrado_por=excluded.registrado_por
    """, (turma_id, data, foto, registrado_por))
    conn.commit()
    conn.close()
