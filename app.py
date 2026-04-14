"""ERP Interface Simulator — Painel de controle para reconhecimento facial."""

import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import sqlite3

# ─── Logging ─────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Configuração ────────────────────────────────────────────────

ENTRADA_DIR = os.environ.get("ERP_ENTRADA_DIR", "data/erp-integration/entrada")
SAIDA_DIR = os.environ.get("ERP_SAIDA_DIR", "data/erp-integration/saida")
DB_PATH = os.environ.get("ERP_DB_PATH", "/app/data/erp.db")
FACIAL_URL = os.environ.get("FACIAL_URL", "http://host.docker.internal:8080")
POLL_TIMEOUT_S = int(os.environ.get("POLL_TIMEOUT_S", "300"))
POLL_INTERVAL_S = int(os.environ.get("POLL_INTERVAL_S", "2"))

st.set_page_config(page_title="ERP Interface", page_icon="🎯", layout="wide")

# ─── Banco de Dados (Clientes ERP) ──────────────────────────────


def init_db():
    """Cria tabelas se não existirem."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT,
            telefone TEXT,
            facial_cadastrado INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS log_operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operacao TEXT NOT NULL,
            id_cliente TEXT NOT NULL,
            nome_cliente TEXT,
            id_solicitacao TEXT,
            resultado TEXT,
            detalhes TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def listar_clientes() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM clientes ORDER BY criado_em DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def cliente_existe(id_cliente: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT 1 FROM clientes WHERE id = ?", (id_cliente,))
    existe = cur.fetchone() is not None
    conn.close()
    return existe


def cadastrar_cliente(id_cliente: str, nome: str, email: str = "", telefone: str = ""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO clientes (id, nome, email, telefone) VALUES (?, ?, ?, ?)",
        (id_cliente, nome, email, telefone),
    )
    conn.commit()
    conn.close()
    logger.info("Cliente cadastrado: %s — %s", id_cliente, nome)


def remover_cliente(id_cliente: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM clientes WHERE id = ?", (id_cliente,))
    conn.commit()
    conn.close()
    logger.info("Cliente removido: %s", id_cliente)


def atualizar_status_facial(id_cliente: str, cadastrado: bool):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE clientes SET facial_cadastrado = ? WHERE id = ?",
        (1 if cadastrado else 0, id_cliente),
    )
    conn.commit()
    conn.close()


def registrar_log(operacao: str, id_cliente: str, nome_cliente: str,
                  id_solicitacao: str = "", resultado: str = "", detalhes: str = ""):
    """Registra operação no log de auditoria."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO log_operacoes
           (operacao, id_cliente, nome_cliente, id_solicitacao, resultado, detalhes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (operacao, id_cliente, nome_cliente, id_solicitacao, resultado, detalhes),
    )
    conn.commit()
    conn.close()
    logger.info("Log: %s — %s — %s", operacao, id_cliente, resultado)


def listar_logs() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM log_operacoes ORDER BY timestamp DESC LIMIT 100")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ─── Helpers (Integração Facial) ─────────────────────────────────


def ensure_dirs():
    """Cria diretórios se não existirem."""
    Path(ENTRADA_DIR).mkdir(parents=True, exist_ok=True)
    Path(SAIDA_DIR).mkdir(parents=True, exist_ok=True)


def gerar_nome_arquivo(id_cliente: str, funcao: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{id_cliente}_{ts}_{funcao}.json"


def enviar_solicitacao(payload: dict, funcao: str) -> str:
    nome = gerar_nome_arquivo(payload["id_cliente"], funcao)
    path = Path(ENTRADA_DIR) / nome
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Solicitação enviada: %s", nome)
    return nome


def buscar_resposta(nome_arquivo: str) -> dict | None:
    path = Path(SAIDA_DIR) / nome_arquivo
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def listar_respostas() -> list[dict]:
    resultados = []
    for f in sorted(Path(SAIDA_DIR).glob("*.json"), reverse=True):
        try:
            dados = json.loads(f.read_text(encoding="utf-8"))
            dados["_nome_arquivo"] = f.name
            dados["_timestamp"] = datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            resultados.append(dados)
        except (json.JSONDecodeError, OSError):
            continue
    return resultados


def aguardar_resposta(nome_arquivo: str, progress_placeholder, timeout: int = POLL_TIMEOUT_S) -> dict | None:
    """Faz polling em saida/ até encontrar resposta ou timeout."""
    inicio = time.time()
    while time.time() - inicio < timeout:
        resp = buscar_resposta(nome_arquivo)
        if resp:
            return resp
        elapsed = int(time.time() - inicio)
        progresso = min(elapsed / timeout, 1.0)
        progress_placeholder.progress(progresso, text=f"Aguardando resposta do sistema facial... ({elapsed}s / {timeout}s)")
        time.sleep(POLL_INTERVAL_S)
    return None


# ─── UI ──────────────────────────────────────────────────────────

st.title("🎯 ERP Interface — Reconhecimento Facial")
st.caption("Simulador de ERP para demonstração do módulo de biometria facial")

# Inicializa DB e diretórios
init_db()
ensure_dirs()

# Diagnóstico rápido
with st.sidebar:
    st.header("🔍 Diagnóstico")
    st.write(f"**Face Recognition:** `{FACIAL_URL}`")

    entrada_ok = Path(ENTRADA_DIR).exists()
    saida_ok = Path(SAIDA_DIR).exists()
    st.success(f"Entrada: `{ENTRADA_DIR}`") if entrada_ok else st.error(f"Entrada: `{ENTRADA_DIR}` não existe")
    st.success(f"Saída: `{SAIDA_DIR}`") if saida_ok else st.error(f"Saída: `{SAIDA_DIR}` não existe")

    if entrada_ok:
        arquivos_entrada = list(Path(ENTRADA_DIR).glob("*.json"))
        st.info(f"Arquivos em entrada: {len(arquivos_entrada)}")
    if saida_ok:
        arquivos_saida = list(Path(SAIDA_DIR).glob("*.json"))
        st.info(f"Respostas em saída: {len(arquivos_saida)}")

    st.divider()
    st.caption(f"Timeout: {POLL_TIMEOUT_S}s | Poll: {POLL_INTERVAL_S}s")

st.divider()

# Abas
tab_clientes, tab_cadastro, tab_validacao, tab_historico, tab_logs = st.tabs(
    ["👥 Clientes", "📝 Cadastro Facial", "🔐 Validação", "📋 Histórico", "📊 Logs"]
)

# ── Clientes (CRUD) ──────────────────────────────────────────────
with tab_clientes:
    st.subheader("Gestão de Clientes do ERP")

    col_form, col_list = st.columns([1, 2])

    with col_form:
        st.write("**Novo Cliente**")
        id_cliente = st.text_input("ID do Cliente", key="cliente_id")
        nome = st.text_input("Nome", key="cliente_nome")
        email = st.text_input("Email", key="cliente_email")
        telefone = st.text_input("Telefone", key="cliente_telefone")

        if st.button("Salvar Cliente", type="primary", use_container_width=True):
            if not id_cliente or not nome:
                st.error("ID e Nome são obrigatórios.")
            elif cliente_existe(id_cliente):
                st.error("Cliente com este ID já existe.")
            else:
                cadastrar_cliente(id_cliente, nome, email, telefone)
                registrar_log("CADASTRO_CLIENTE", id_cliente, nome, resultado="SUCESSO")
                st.success(f"Cliente `{id_cliente}` cadastrado com sucesso!")
                st.rerun()

    with col_list:
        st.write("**Clientes Cadastrados**")
        clientes = listar_clientes()
        if not clientes:
            st.info("Nenhum cliente cadastrado.")
        else:
            for c in clientes:
                status_icon = "✅" if c["facial_cadastrado"] else "⬜"
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"{status_icon} **{c['id']}** — {c['nome']}")
                        if c["email"]:
                            st.caption(f"📧 {c['email']}")
                        if c["telefone"]:
                            st.caption(f"📱 {c['telefone']}")
                    with col2:
                        st.caption(f"Criado: {c.get('criado_em', '?')[:10]}")
                    with col3:
                        if st.button("Remover", key=f"rm_{c['id']}", type="small"):
                            if st.session_state.get(f"confirm_rm_{c['id']}"):
                                remover_cliente(c["id"])
                                registrar_log("REMOCAO_CLIENTE", c["id"], c["nome"], resultado="SUCESSO")
                                st.session_state[f"confirm_rm_{c['id']}"] = False
                                st.rerun()
                            else:
                                st.session_state[f"confirm_rm_{c['id']}"] = True
                                st.rerun()

# ── Cadastro Facial ──────────────────────────────────────────────
with tab_cadastro:
    st.subheader("Solicitar Cadastro Facial")
    st.caption("Selecione um cliente do ERP e inicie a captura facial via iframe.")

    clientes = listar_clientes()
    if not clientes:
        st.warning("Nenhum cliente cadastrado. Cadastre um cliente na aba **Clientes** primeiro.")
    else:
        pendentes = [c for c in clientes if not c["facial_cadastrado"]]
        if not pendentes:
            st.info("Todos os clientes já possuem identidade facial cadastrada.")
        else:
            cliente_options = {f"{c['id']} — {c['nome']}": c["id"] for c in pendentes}
            selecionado = st.selectbox("Selecionar Cliente", list(cliente_options.keys()))
            qtd_fotos = st.number_input("Quantidade de Fotos", min_value=1, max_value=20, value=5)

            if st.button("🚀 Solicitar Cadastro Facial", type="primary", use_container_width=True):
                id_sel = cliente_options[selecionado]
                cliente_dados = next(c for c in clientes if c["id"] == id_sel)

                # 1. Gera JSON em entrada/
                payload = {
                    "funcao": "cadastrar",
                    "id_cliente": id_sel,
                    "nome_cliente": cliente_dados["nome"],
                    "qtd_fotos": qtd_fotos,
                }
                nome_arquivo = enviar_solicitacao(payload, "cadastrar")

                registrar_log("SOLICITACAO_CADASTRO", id_sel, cliente_dados["nome"],
                              resultado="ENVIADO", detalhes=nome_arquivo)

                # 2. Exibe iframe com a página do face-recognition
                st.session_state["mostrar_iframe"] = True
                st.session_state["iframe_nome_arquivo"] = nome_arquivo
                st.session_state["iframe_id_cliente"] = id_sel
                st.session_state["iframe_nome_cliente"] = cliente_dados["nome"]
                st.rerun()

            # Mostra iframe se estiver em processamento
            if st.session_state.get("mostrar_iframe"):
                nome_arquivo = st.session_state["iframe_nome_arquivo"]
                id_cliente = st.session_state.get("iframe_id_cliente", "")
                nome_cliente = st.session_state.get("iframe_nome_cliente", "")

                st.divider()
                st.info("📷 Captura facial em andamento — aguarde a conclusão...")

                # Iframe com o face-recognition
                components.iframe(
                    src=f"{FACIAL_URL}/erp-aguardando.html",
                    width=480,
                    height=600,
                )

                # 3. Monitora saida/ até resposta
                progress = st.empty()
                resp = aguardar_resposta(nome_arquivo, progress)

                # 4. Remove estado do iframe
                st.session_state["mostrar_iframe"] = False

                # 5. Processa resposta
                if resp:
                    resultado = resp.get("resultado", "")
                    id_solicitacao = resp.get("id_solicitacao", "")

                    if resultado in ("SUCESSO", "SUCESSO_PARCIAL"):
                        atualizar_status_facial(id_cliente, True)
                        registrar_log("CADASTRO_FACIAL", id_cliente, nome_cliente,
                                      id_solicitacao, resultado,
                                      f"fotos_validas={resp.get('fotos_validas', 0)}")
                        st.success(f"✅ {resultado} — {resp.get('fotos_validas', '?')} fotos válidas capturadas")
                        st.rerun()
                    else:
                        registrar_log("CADASTRO_FACIAL", id_cliente, nome_cliente,
                                      id_solicitacao, resultado,
                                      resp.get("observacoes", "Sem detalhes"))
                        st.error(f"❌ {resultado} — {resp.get('observacoes', 'Sem detalhes')}")
                        st.json(resp)
                else:
                    registrar_log("CADASTRO_FACIAL", id_cliente, nome_cliente,
                                  resultado="TIMEOUT", detalhes="Tempo esgotado")
                    st.warning("⏱️ Tempo esgotado. Verifique manualmente em `saida/`.")

# ── Validação ────────────────────────────────────────────────────
with tab_validacao:
    st.subheader("Solicitar Validação Facial")
    st.caption("Selecione um cliente com identidade facial para validar.")

    clientes = listar_clientes()
    cadastrados = [c for c in clientes if c["facial_cadastrado"]]

    if not cadastrados:
        st.warning("Nenhum cliente com identidade facial cadastrada. Faça o cadastro facial primeiro.")
    else:
        cliente_options = {f"{c['id']} — {c['nome']}": c["id"] for c in cadastrados}
        selecionado = st.selectbox("Selecionar Cliente", list(cliente_options.keys()))

        if st.button("🔐 Solicitar Validação Facial", type="primary", use_container_width=True):
            id_sel = cliente_options[selecionado]
            cliente_dados = next(c for c in clientes if c["id"] == id_sel)

            # 1. Gera JSON em entrada/
            payload = {
                "funcao": "validar",
                "id_cliente": id_sel,
                "nome_cliente": cliente_dados["nome"],
            }
            nome_arquivo = enviar_solicitacao(payload, "validar")

            registrar_log("SOLICITACAO_VALIDACAO", id_sel, cliente_dados["nome"],
                          resultado="ENVIADO", detalhes=nome_arquivo)

            st.session_state["mostrar_iframe_val"] = True
            st.session_state["iframe_val_nome_arquivo"] = nome_arquivo
            st.session_state["iframe_val_id_cliente"] = id_sel
            st.session_state["iframe_val_nome_cliente"] = cliente_dados["nome"]
            st.rerun()

            # Mostra iframe se estiver em processamento
            if st.session_state.get("mostrar_iframe_val"):
                nome_arquivo = st.session_state["iframe_val_nome_arquivo"]
                id_cliente = st.session_state.get("iframe_val_id_cliente", "")
                nome_cliente = st.session_state.get("iframe_val_nome_cliente", "")

                st.divider()
                st.info("🔐 Validação facial em andamento — aguarde a conclusão...")

                components.iframe(
                    src=f"{FACIAL_URL}/erp-aguardando.html",
                    width=480,
                    height=600,
                )

                progress = st.empty()
                resp = aguardar_resposta(nome_arquivo, progress)

                st.session_state["mostrar_iframe_val"] = False

                if resp:
                    resultado = resp.get("resultado", "")
                    id_solicitacao = resp.get("id_solicitacao", "")

                    if resultado == "MATCH":
                        registrar_log("VALIDACAO_FACIAL", id_cliente, nome_cliente,
                                      id_solicitacao, "MATCH",
                                      f"score={resp.get('score', 'N/A')}")
                        st.success(f"✅ MATCH — Score: {resp.get('score', 'N/A')} (threshold: {resp.get('threshold', 'N/A')})")
                    elif resultado == "NO_MATCH":
                        registrar_log("VALIDACAO_FACIAL", id_cliente, nome_cliente,
                                      id_solicitacao, "NO_MATCH",
                                      f"score={resp.get('score', 'N/A')}")
                        st.error(f"❌ NO_MATCH — Score: {resp.get('score', 'N/A')} (threshold: {resp.get('threshold', 'N/A')})")
                    else:
                        registrar_log("VALIDACAO_FACIAL", id_cliente, nome_cliente,
                                      id_solicitacao, resultado,
                                      resp.get("observacoes", "Sem detalhes"))
                        st.error(f"⚠️ ERRO — {resp.get('observacoes', 'Sem detalhes')}")
                    st.json(resp)
                else:
                    registrar_log("VALIDACAO_FACIAL", id_cliente, nome_cliente,
                                  resultado="TIMEOUT", detalhes="Tempo esgotado")
                    st.warning("⏱️ Tempo esgotado. Verifique manualmente em `saida/`.")

# ── Histórico ────────────────────────────────────────────────────
with tab_historico:
    st.subheader("Histórico de Respostas")
    if st.button("Atualizar"):
        st.rerun()

    respostas = listar_respostas()
    if not respostas:
        st.info("Nenhuma resposta registrada ainda.")
    else:
        for r in respostas:
            resultado = r.get("resultado", "")
            if resultado in ("SUCESSO", "SUCESSO_PARCIAL", "MATCH"):
                icon = "✅"
            elif resultado == "NO_MATCH":
                icon = "❌"
            else:
                icon = "⚠️"

            with st.expander(f"{icon} {r.get('funcao')} — {r.get('id_cliente')} — {resultado}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Arquivo:** `{r.get('_nome_arquivo')}`")
                with col2:
                    st.write(f"**Timestamp:** `{r.get('_timestamp')}`")
                st.json(r)

# ── Logs ─────────────────────────────────────────────────────────
with tab_logs:
    st.subheader("📊 Logs de Auditoria")
    if st.button("Atualizar Logs"):
        st.rerun()

    logs = listar_logs()
    if not logs:
        st.info("Nenhuma operação registrada.")
    else:
        for log in logs:
            operacao = log.get("operacao", "")
            resultado = log.get("resultado", "")

            if resultado in ("SUCESSO", "MATCH", "ENVIADO"):
                icon = "✅"
            elif resultado in ("TIMEOUT", "ERRO", "NO_MATCH"):
                icon = "❌"
            else:
                icon = "ℹ️"

            with st.expander(f"{icon} {operacao} — {log.get('id_cliente')} — {resultado}"):
                st.write(f"**Cliente:** `{log.get('id_cliente')}` — {log.get('nome_cliente')}")
                st.write(f"**ID Solicitação:** `{log.get('id_solicitacao')}`")
                st.write(f"**Resultado:** {resultado}")
                if log.get("detalhes"):
                    st.write(f"**Detalhes:** {log['detalhes']}")
                st.write(f"**Timestamp:** `{log.get('timestamp')}`")
