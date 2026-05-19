import streamlit as st
import gspread
import pandas as pd
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from datetime import datetime, date, time
import hashlib
import time as time_mod
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit


# =====================================================
# SISTEMA DRONEPOL CABO FRIO - CONTROLE DE DRONES
# Streamlit + Google Sheets + Pandas + ReportLab
# =====================================================

st.set_page_config(
    page_title="DRONEPOL Cabo Frio - Controle Operacional",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CSS
# =====================================================
st.markdown("""
<style>
    .main-title {
        font-size: 2rem;
        font-weight: 900;
        margin-bottom: 0.2rem;
        color: #0f172a;
    }
    .sub-title {
        color: #64748b;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #0f172a, #1e293b);
        padding: 18px;
        border-radius: 18px;
        color: white;
        box-shadow: 0 4px 18px rgba(0,0,0,0.16);
        border: 1px solid rgba(255,255,255,0.08);
        min-height: 110px;
    }
    .metric-card h4 {
        margin: 0;
        font-size: 0.92rem;
        color: #cbd5e1;
        font-weight: 600;
    }
    .metric-card h2 {
        margin: 8px 0 0 0;
        font-size: 2rem;
        font-weight: 900;
        color: #ffffff;
    }
    .section-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 14px;
    }
    .danger-box {
        background: #fff1f2;
        border: 1px solid #fecdd3;
        border-radius: 14px;
        padding: 14px;
    }
    .ok-box {
        background: #ecfdf5;
        border: 1px solid #bbf7d0;
        border-radius: 14px;
        padding: 14px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🚁 DRONEPOL Cabo Frio – Controle Operacional de Drones</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Gestão de aeronaves, cautelas, inspeções de voo, avaliação de risco, missões, relatórios PDF e auditoria.</div>', unsafe_allow_html=True)

# =====================================================
# CONSTANTES
# =====================================================
TZ = ZoneInfo("America/Sao_Paulo")
STATUS_ATIVO = "ATIVO"
STATUS_INATIVO = "INATIVO"
STATUS_DISPONIVEL = "DISPONÍVEL"
STATUS_CAUTELADO = "CAUTELADO"
STATUS_MANUTENCAO = "MANUTENÇÃO"
STATUS_BAIXADO = "BAIXADO"

TIPOS_USUARIO = {
    "Administrador": "admin",
    "Gestor": "gestor",
    "Piloto/Agente": "agente",
}

ABAS = {
    "drones": [
        "id", "matricula_aeronave", "modelo", "numero_serie", "fabricante",
        "apelido", "status", "data_cadastro", "observacoes"
    ],
    "usuarios": [
        "id", "tipo_usuario", "login", "nome", "matricula", "id_piloto",
        "senha", "primeiro_acesso", "status"
    ],
    "cautelas": [
        "id", "id_drone", "matricula_aeronave", "modelo", "numero_serie",
        "data_retirada", "hora_retirada", "finalidade", "operador_nome",
        "operador_matricula", "responsavel_entrega", "data_devolucao",
        "hora_devolucao", "responsavel_devolucao", "recebido_por",
        "status", "observacoes", "usuario_registro", "data_registro"
    ],
    "inspecoes": [
        "id", "ordem_voo", "id_drone", "matricula_aeronave", "data",
        "horario", "solicitante", "local_coordenadas", "piloto_nome",
        "piloto_id", "observador_nome", "observador_id",
        "pre_update_firmware", "pre_cartao_sd", "pre_asas", "pre_cabos",
        "pre_carregador", "pre_cameras", "pre_documentos_autorizacoes",
        "pre_epis", "pre_aspecto_geral", "pre_protetor_gimbal",
        "pre_calibracao_bussola", "pre_area_decolagem_pouso",
        "pre_download_mapas", "pre_carga_bateria", "pre_carga_radio",
        "pre_carga_dispositivo", "pre_formatacao_sd", "pre_analise_risco",
        "pre_plano_voo", "pre_config_software",
        "dur_carga_bateria", "dur_voltagem_bateria", "dur_satelites",
        "dur_modo_voo", "dur_parametros_visuais", "dur_telemetria",
        "dur_performance",
        "pos_carga_bateria", "pos_carga_radio", "pos_aspecto_geral",
        "pos_imagens_salvas", "pos_relatorio_operacional",
        "observacoes", "usuario_registro", "data_registro"
    ],
    "relatorios_operacionais": [
        "id", "numero_relatorio", "data", "id_drone", "matricula_aeronave",
        "clima", "vento", "obstaculos", "local_pouso_decolagem",
        "mitigacao", "observacoes_risco", "localidade", "historico",
        "quantidade_fotos", "quantidade_videos", "fotos_backup",
        "videos_backup", "tempo_total_voo_min", "piloto", "observador",
        "usuario_registro", "data_registro"
    ],
    "voos_relatorio": [
        "id", "id_relatorio", "acionamento", "corte", "tempo_voo_min",
        "piloto", "observador"
    ],
    "log_auditoria": [
        "data", "hora", "usuario", "acao", "detalhes"
    ]
}


# =====================================================
# SEGURANÇA
# =====================================================
def make_hashes(password):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def check_hashes(password, hashed_text):
    return make_hashes(password) == str(hashed_text)


def init_session():
    defaults = {
        "logado": False,
        "usuario_id": None,
        "tipo_usuario": None,
        "nome_usuario": "",
        "login_usuario": "",
        "primeiro_acesso": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def logout():
    for k in ["logado", "usuario_id", "tipo_usuario", "nome_usuario", "login_usuario", "primeiro_acesso"]:
        st.session_state[k] = False if k in ["logado", "primeiro_acesso"] else ""
    st.rerun()


init_session()


# =====================================================
# GOOGLE SHEETS
# =====================================================
@st.cache_resource
def conectar_planilha():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(
            st.secrets["google_service_account"],
            scopes=scope
        )
        client = gspread.authorize(creds)

        # Configure em .streamlit/secrets.toml:
        # spreadsheet_key = "1aWIkmMQg6R2HBfE9eYcl5VBZO35PLpEQzYMgBbJAzfA"
        spreadsheet_key = st.secrets.get("spreadsheet_key", "")
        if not spreadsheet_key:
            st.error("Informe spreadsheet_key no arquivo .streamlit/secrets.toml.")
            st.stop()

        return client.open_by_key(spreadsheet_key)
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Sheets: {e}")
        st.stop()


def obter_aba(nome):
    planilha = conectar_planilha()
    try:
        aba = planilha.worksheet(nome)
    except Exception:
        cols = max(len(ABAS[nome]), 10)
        aba = planilha.add_worksheet(title=nome, rows=3000, cols=cols)
        aba.append_row(ABAS[nome])
    return aba


SHEETS = {nome: obter_aba(nome) for nome in ABAS.keys()}


def bootstrap_admin():
    aba = SHEETS["usuarios"]
    registros = aba.get_all_records()
    df = pd.DataFrame(registros)
    if df.empty:
        aba.append_row([
            1, "admin", "admin", "ADMINISTRADOR", "", "",
            make_hashes("admin123"), 1, STATUS_ATIVO
        ])
        return

    df.columns = df.columns.str.strip().str.lower()
    existe = not df[
        (df["tipo_usuario"].astype(str).str.lower() == "admin") &
        (df["login"].astype(str).str.lower() == "admin") &
        (df["status"].astype(str).str.upper() == STATUS_ATIVO)
    ].empty

    if not existe:
        ids = pd.to_numeric(df.get("id", pd.Series(dtype=float)), errors="coerce").dropna()
        novo_id = int(ids.max()) + 1 if not ids.empty else 1
        aba.append_row([
            novo_id, "admin", "admin", "ADMINISTRADOR", "", "",
            make_hashes("admin123"), 1, STATUS_ATIVO
        ])


bootstrap_admin()


# =====================================================
# CACHE / LEITURA
# =====================================================
@st.cache_data(ttl=60)
def carregar_aba(nome):
    dados = SHEETS[nome].get_all_records()
    df = pd.DataFrame(dados)
    if not df.empty:
        df.columns = df.columns.str.strip().str.lower()
    return df


def limpar_cache(*nomes):
    if not nomes:
        carregar_aba.clear()
        return
    carregar_aba.clear()


def gerar_id(df):
    if df.empty or "id" not in df.columns:
        return 1
    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    return int(ids.max()) + 1 if not ids.empty else 1


def agora_str():
    a = datetime.now(TZ)
    return a.strftime("%d/%m/%Y"), a.strftime("%H:%M:%S")


def registrar_log(usuario, acao, detalhes=""):
    data, hora = agora_str()
    SHEETS["log_auditoria"].append_row([
        data, hora, str(usuario).upper(), str(acao).upper(), str(detalhes).upper()
    ])
    limpar_cache("log_auditoria")


# =====================================================
# VALIDADORES
# =====================================================
def validar_data_manual(data_str):
    try:
        data_str = str(data_str).strip().replace("-", "/").replace(".", "/").replace("\\", "/")
        if not data_str:
            return False, None
        if "/" not in data_str:
            num = "".join(ch for ch in data_str if ch.isdigit())
            if len(num) == 8:
                data_str = f"{num[:2]}/{num[2:4]}/{num[4:]}"
            elif len(num) == 6:
                data_str = f"{num[:2]}/{num[2:4]}/20{num[4:]}"
            else:
                return False, None
        else:
            partes = data_str.split("/")
            if len(partes) != 3:
                return False, None
            d, m, a = partes
            data_str = f"{d.zfill(2)}/{m.zfill(2)}/{('20' + a) if len(a) == 2 else a}"
        obj = datetime.strptime(data_str, "%d/%m/%Y")
        return True, obj
    except Exception:
        return False, None


def validar_hora_manual(hora_str):
    try:
        hora_str = str(hora_str).strip().replace(".", "").replace("-", "").replace(" ", "")
        if not hora_str:
            return False, None
        if ":" not in hora_str:
            if len(hora_str) == 4:
                hora_str = f"{hora_str[:2]}:{hora_str[2:]}"
            elif len(hora_str) == 3:
                hora_str = f"0{hora_str[0]}:{hora_str[1:]}"
            else:
                return False, None
        obj = datetime.strptime(hora_str, "%H:%M")
        return True, obj.strftime("%H:%M")
    except Exception:
        return False, None


def data_hoje_br():
    return datetime.now(TZ).strftime("%d/%m/%Y")


def hora_agora_br():
    return datetime.now(TZ).strftime("%H:%M")


def fmt_int(v):
    try:
        return int(float(v))
    except Exception:
        return 0


def normalizar_texto(s):
    return str(s).strip().upper()


# =====================================================
# PDF
# =====================================================
def gerar_pdf_texto(titulo, linhas, usuario_emissor):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    margem = 40
    largura_texto = largura - 2 * margem
    y = altura - 40

    def cabecalho():
        nonlocal y
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margem, y, "PREFEITURA MUNICIPAL DE CABO FRIO")
        y -= 14
        pdf.drawString(margem, y, "SECRETARIA DE SEGURANÇA E ORDEM PÚBLICA")
        y -= 14
        pdf.drawString(margem, y, "GUARDA CIVIL MUNICIPAL - DRONEPOL")
        y -= 22
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawCentredString(largura / 2, y, titulo)
        y -= 20
        pdf.setFont("Helvetica", 8)
        pdf.drawString(margem, y, f"Emitido em: {datetime.now(TZ).strftime('%d/%m/%Y %H:%M:%S')} | Usuário: {usuario_emissor}")
        y -= 20

    def nova_pagina():
        nonlocal y
        pdf.showPage()
        y = altura - 40
        cabecalho()

    pdf.setTitle(titulo)
    cabecalho()
    pdf.setFont("Helvetica", 10)

    for item in linhas:
        texto = str(item)
        if texto.startswith("## "):
            y -= 6
            if y < 60:
                nova_pagina()
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawString(margem, y, texto.replace("## ", ""))
            y -= 16
            pdf.setFont("Helvetica", 10)
            continue

        for linha in simpleSplit(texto, "Helvetica", 10, largura_texto):
            if y < 50:
                nova_pagina()
            pdf.drawString(margem, y, linha)
            y -= 14
        if texto == "":
            y -= 6

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def download_pdf(label, titulo, linhas, arquivo_base):
    pdf_bytes = gerar_pdf_texto(titulo, linhas, st.session_state.get("nome_usuario", "SISTEMA"))
    st.download_button(
        label=label,
        data=pdf_bytes,
        file_name=f"{arquivo_base}.pdf",
        mime="application/pdf",
        use_container_width=True
    )


# =====================================================
# USUÁRIOS
# =====================================================
def buscar_usuario_login(tipo_usuario, login):
    df = carregar_aba("usuarios")
    if df.empty:
        return None
    filtro = (
        (df["tipo_usuario"].astype(str).str.lower() == str(tipo_usuario).lower()) &
        (df["login"].astype(str).str.lower() == str(login).strip().lower()) &
        (df["status"].astype(str).str.upper() == STATUS_ATIVO)
    )
    res = df[filtro]
    return None if res.empty else res.iloc[0]


def login_usuario(tipo_usuario, login, senha):
    user = buscar_usuario_login(tipo_usuario, login)
    if user is not None and check_hashes(senha, user["senha"]):
        return {
            "sucesso": True,
            "id": int(user["id"]),
            "nome": str(user["nome"]),
            "login": str(user["login"]),
            "primeiro_acesso": bool(int(user.get("primeiro_acesso", 0) or 0))
        }
    return {"sucesso": False}


def linha_usuario_por_id(id_usuario):
    df = carregar_aba("usuarios")
    if df.empty:
        return None, None
    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    res = df[df["id"] == int(id_usuario)]
    if res.empty:
        return None, None
    idx = res.index[0]
    return idx + 2, res.iloc[0]


def alterar_senha(id_usuario, nova_senha):
    linha, user = linha_usuario_por_id(id_usuario)
    if linha is None:
        return False
    SHEETS["usuarios"].update(f"G{linha}:H{linha}", [[make_hashes(nova_senha), 0]])
    registrar_log(user.get("nome", "USUARIO"), "ALTERAÇÃO DE SENHA", f"ID {id_usuario}")
    limpar_cache("usuarios")
    return True


def validar_senha_por_id(id_usuario, senha):
    _, user = linha_usuario_por_id(id_usuario)
    if user is None:
        return False
    return check_hashes(senha, user["senha"])


def cadastrar_usuario(tipo_usuario, login, nome, matricula, id_piloto, senha_inicial="1234"):
    df = carregar_aba("usuarios")
    if not df.empty:
        existe = df[
            (df["tipo_usuario"].astype(str).str.lower() == tipo_usuario.lower()) &
            (df["login"].astype(str).str.lower() == login.lower()) &
            (df["status"].astype(str).str.upper() == STATUS_ATIVO)
        ]
        if not existe.empty:
            return False
    novo_id = gerar_id(df)
    SHEETS["usuarios"].append_row([
        novo_id, tipo_usuario, login, normalizar_texto(nome), normalizar_texto(matricula),
        normalizar_texto(id_piloto), make_hashes(senha_inicial), 1, STATUS_ATIVO
    ])
    registrar_log(st.session_state.get("nome_usuario", "SISTEMA"), "CADASTRO USUÁRIO", f"{tipo_usuario} | {login} | {nome}")
    limpar_cache("usuarios")
    return True


def listar_usuarios(tipo=None):
    df = carregar_aba("usuarios")
    if df.empty:
        return df
    if tipo:
        df = df[(df["tipo_usuario"].astype(str).str.lower() == tipo.lower()) & (df["status"].astype(str).str.upper() == STATUS_ATIVO)]
    return df


def resetar_senha(id_usuario, nova_senha="1234"):
    linha, user = linha_usuario_por_id(id_usuario)
    if linha is None:
        return False
    SHEETS["usuarios"].update(f"G{linha}:H{linha}", [[make_hashes(nova_senha), 1]])
    registrar_log(st.session_state.get("nome_usuario", "SISTEMA"), "RESET SENHA", f"ID {id_usuario} | LOGIN {user.get('login','')}")
    limpar_cache("usuarios")
    return True


def inativar_usuario(id_usuario):
    linha, user = linha_usuario_por_id(id_usuario)
    if linha is None:
        return False
    SHEETS["usuarios"].update(f"I{linha}", [[STATUS_INATIVO]])
    registrar_log(st.session_state.get("nome_usuario", "SISTEMA"), "INATIVAÇÃO USUÁRIO", f"ID {id_usuario} | LOGIN {user.get('login','')}")
    limpar_cache("usuarios")
    return True


# =====================================================
# LOGIN
# =====================================================
if not st.session_state["logado"]:
    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        st.subheader("🔐 Acesso ao Sistema")
        with st.form("form_login"):
            perfil = st.radio("Entrar como:", list(TIPOS_USUARIO.keys()), horizontal=True)
            login_label = "Usuário" if perfil != "Piloto/Agente" else "Matrícula/Login do Piloto"
            login_input = st.text_input(login_label)
            senha_input = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar", use_container_width=True)

        if entrar:
            tipo = TIPOS_USUARIO[perfil]
            resultado = login_usuario(tipo, login_input.strip(), senha_input)
            if resultado["sucesso"]:
                st.session_state["logado"] = True
                st.session_state["tipo_usuario"] = tipo
                st.session_state["usuario_id"] = resultado["id"]
                st.session_state["nome_usuario"] = resultado["nome"]
                st.session_state["login_usuario"] = resultado["login"]
                st.session_state["primeiro_acesso"] = resultado["primeiro_acesso"]
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")

    st.info("Acesso inicial: usuário `admin` e senha `admin123`. Altere a senha no primeiro acesso.")
    st.stop()


if bool(st.session_state.get("primeiro_acesso", False)):
    st.warning("⚠️ Por segurança, altere sua senha inicial.")

    with st.form(key="form_primeiro_acesso"):
        nova1 = st.text_input(
            "Nova senha",
            type="password",
            key="nova_senha_1"
        )

        nova2 = st.text_input(
            "Confirme a nova senha",
            type="password",
            key="nova_senha_2"
        )

        enviar = st.form_submit_button(
            "Atualizar senha",
            use_container_width=True
        )

    if enviar:
        if nova1 != nova2:
            st.error("As senhas não coincidem.")

        elif len(nova1) < 4:
            st.error("A senha deve ter pelo menos 4 caracteres.")

        else:
            alterar_senha(st.session_state["usuario_id"], nova1)

            st.session_state.update({
                "primeiro_acesso": False
            })

            st.success("Senha atualizada com sucesso.")
            time_mod.sleep(1)
            st.rerun()

    st.stop()

# =====================================================
# SIDEBAR / MENU
# =====================================================
st.sidebar.success(f"Logado como: {st.session_state['nome_usuario']}")
st.sidebar.write(f"Perfil: {st.session_state['tipo_usuario'].upper()}")
if st.sidebar.button("Sair / Logout"):
    logout()

perfil = st.session_state["tipo_usuario"]

menus_admin = [
    "📊 Dashboard",
    "🚁 Cadastro de Drone",
    "📦 Cautela de Uso",
    "🔁 Devolução de Drone",
    "✅ Inspeção de Voo",
    "🛡️ Relatório / Avaliação Operacional",
    "🔎 Consulta Geral",
    "🖨️ Relatórios PDF",
    "👤 Cadastrar Usuário",
    "📋 Gerenciar Usuários",
    "🔐 Minha Conta",
    "📜 Log de Auditoria"
]

menus_agente = [
    "📊 Dashboard",
    "📦 Cautela de Uso",
    "🔁 Devolução de Drone",
    "✅ Inspeção de Voo",
    "🛡️ Relatório / Avaliação Operacional",
    "🔎 Consulta Geral",
    "🖨️ Relatórios PDF",
    "🔐 Minha Conta"
]

menu = st.sidebar.radio("Menu Principal", menus_admin if perfil in ["admin", "gestor"] else menus_agente)


# =====================================================
# HELPERS DE DRONE
# =====================================================
def carregar_drones():
    df = carregar_aba("drones")
    if df.empty:
        return df
    if "id" in df.columns:
        df["id"] = pd.to_numeric(df["id"], errors="coerce")
    return df


def drone_opcoes(status=None):
    df = carregar_drones()
    if df.empty:
        return []
    if status:
        df = df[df["status"].astype(str).str.upper() == status]
    return (
        df["id"].astype(str) + " - " +
        df["matricula_aeronave"].astype(str) + " - " +
        df["modelo"].astype(str) + " - " +
        df["numero_serie"].astype(str)
    ).tolist()


def selecionar_drone_por_opcao(opcao):
    id_drone = int(str(opcao).split(" - ")[0])
    df = carregar_drones()
    row = df[df["id"] == id_drone].iloc[0]
    return id_drone, row


def atualizar_status_drone(id_drone, status):
    df = carregar_drones()
    linha = df.index[df["id"] == int(id_drone)][0] + 2
    # coluna G = status
    SHEETS["drones"].update(f"G{linha}", [[status]])
    limpar_cache("drones")


def card_metrica(titulo, valor):
    st.markdown(f"""
        <div class="metric-card">
            <h4>{titulo}</h4>
            <h2>{valor}</h2>
        </div>
    """, unsafe_allow_html=True)


# =====================================================
# DASHBOARD
# =====================================================
if menu == "📊 Dashboard":
    st.subheader("Dashboard Operacional")

    df_drones = carregar_aba("drones")
    df_cautelas = carregar_aba("cautelas")
    df_inspecoes = carregar_aba("inspecoes")
    df_rel = carregar_aba("relatorios_operacionais")

    total_drones = len(df_drones)
    disponiveis = len(df_drones[df_drones["status"].astype(str).str.upper() == STATUS_DISPONIVEL]) if not df_drones.empty and "status" in df_drones.columns else 0
    cautelados = len(df_drones[df_drones["status"].astype(str).str.upper() == STATUS_CAUTELADO]) if not df_drones.empty and "status" in df_drones.columns else 0
    manutencao = len(df_drones[df_drones["status"].astype(str).str.upper() == STATUS_MANUTENCAO]) if not df_drones.empty and "status" in df_drones.columns else 0
    missoes = len(df_rel)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: card_metrica("Drones cadastrados", total_drones)
    with c2: card_metrica("Disponíveis", disponiveis)
    with c3: card_metrica("Cautelados", cautelados)
    with c4: card_metrica("Manutenção", manutencao)
    with c5: card_metrica("Relatórios operacionais", missoes)

    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["Frota", "Operação", "Produtividade"])

    with tab1:
        if df_drones.empty:
            st.info("Nenhum drone cadastrado.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Drones por status**")
                st.bar_chart(df_drones["status"].astype(str).str.upper().value_counts())
            with col2:
                st.markdown("**Drones por modelo**")
                st.bar_chart(df_drones["modelo"].astype(str).str.upper().value_counts())

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Cautelas por status**")
            if not df_cautelas.empty:
                st.bar_chart(df_cautelas["status"].astype(str).str.upper().value_counts())
            else:
                st.info("Sem cautelas.")
        with col2:
            st.markdown("**Relatórios por localidade**")
            if not df_rel.empty and "localidade" in df_rel.columns:
                st.bar_chart(df_rel["localidade"].astype(str).str.upper().value_counts().head(10))
            else:
                st.info("Sem relatórios.")

    with tab3:
        if not df_rel.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Tempo total de voo por piloto (min)**")
                tmp = df_rel.copy()
                tmp["tempo_total_voo_min"] = pd.to_numeric(tmp["tempo_total_voo_min"], errors="coerce").fillna(0)
                st.bar_chart(tmp.groupby("piloto")["tempo_total_voo_min"].sum().sort_values(ascending=False).head(10))
            with col2:
                st.markdown("**Quantidade de fotos por relatório**")
                tmp = df_rel.copy()
                tmp["quantidade_fotos"] = pd.to_numeric(tmp["quantidade_fotos"], errors="coerce").fillna(0)
                st.bar_chart(tmp.groupby("piloto")["quantidade_fotos"].sum().sort_values(ascending=False).head(10))
        else:
            st.info("Sem dados de produtividade.")


# =====================================================
# CADASTRO DE DRONE
# =====================================================
elif menu == "🚁 Cadastro de Drone":
    st.subheader("Cadastro de Aeronave Remotamente Pilotada")

    with st.form("form_drone", clear_on_submit=True):
        matricula = st.text_input("ID / Matrícula da Aeronave")
        modelo = st.text_input("Modelo")
        numero_serie = st.text_input("Nº de Série")
        fabricante = st.text_input("Fabricante")
        apelido = st.text_input("Apelido / Identificação interna")
        status = st.selectbox("Status", [STATUS_DISPONIVEL, STATUS_MANUTENCAO, STATUS_BAIXADO])
        obs = st.text_area("Observações")
        submit = st.form_submit_button("Cadastrar Drone", use_container_width=True)

        if submit:
            if not matricula or not modelo or not numero_serie:
                st.warning("Informe matrícula, modelo e número de série.")
            else:
                df = carregar_aba("drones")
                if not df.empty and (
                    (df["matricula_aeronave"].astype(str).str.upper() == matricula.upper()).any() or
                    (df["numero_serie"].astype(str).str.upper() == numero_serie.upper()).any()
                ):
                    st.error("Já existe drone com esta matrícula ou número de série.")
                else:
                    novo_id = gerar_id(df)
                    SHEETS["drones"].append_row([
                        novo_id, normalizar_texto(matricula), normalizar_texto(modelo),
                        normalizar_texto(numero_serie), normalizar_texto(fabricante),
                        normalizar_texto(apelido), status, data_hoje_br(), normalizar_texto(obs)
                    ])
                    registrar_log(st.session_state["nome_usuario"], "CADASTRO DRONE", f"{matricula} | {modelo} | {numero_serie}")
                    limpar_cache("drones")
                    st.success("✅ Drone cadastrado com sucesso.")


# =====================================================
# CAUTELA
# =====================================================
elif menu == "📦 Cautela de Uso":
    st.subheader("Cautela de Drone – Responsabilidade de Uso")

    opcoes = drone_opcoes(STATUS_DISPONIVEL)
    if not opcoes:
        st.info("Não há drones disponíveis para cautela.")
    else:
        with st.form("form_cautela", clear_on_submit=True):
            drone_sel = st.selectbox("Aeronave", opcoes)
            data_retirada = st.text_input("Data de Retirada", value=data_hoje_br())
            hora_retirada = st.text_input("Hora de Retirada", value=hora_agora_br())
            finalidade = st.text_area("Finalidade da utilização")
            operador_nome = st.text_input("Operador responsável pela retirada", value=st.session_state["nome_usuario"])
            operador_matricula = st.text_input("Matrícula do operador", value=st.session_state["login_usuario"])
            responsavel_entrega = st.text_input("Responsável pela entrega")
            observacoes = st.text_area("Observações")
            submit = st.form_submit_button("Registrar Cautela", use_container_width=True)

            if submit:
                data_ok, data_obj = validar_data_manual(data_retirada)
                hora_ok, hora_fmt = validar_hora_manual(hora_retirada)
                if not finalidade or not operador_nome or not operador_matricula or not responsavel_entrega:
                    st.warning("Preencha finalidade, operador, matrícula e responsável pela entrega.")
                elif not data_ok:
                    st.error("Data inválida.")
                elif not hora_ok:
                    st.error("Hora inválida.")
                else:
                    id_drone, drow = selecionar_drone_por_opcao(drone_sel)
                    df = carregar_aba("cautelas")
                    novo_id = gerar_id(df)
                    SHEETS["cautelas"].append_row([
                        novo_id, id_drone, drow["matricula_aeronave"], drow["modelo"], drow["numero_serie"],
                        data_obj.strftime("%d/%m/%Y"), hora_fmt, normalizar_texto(finalidade),
                        normalizar_texto(operador_nome), normalizar_texto(operador_matricula),
                        normalizar_texto(responsavel_entrega), "", "", "", "", "ABERTA",
                        normalizar_texto(observacoes), st.session_state["nome_usuario"],
                        datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")
                    ])
                    atualizar_status_drone(id_drone, STATUS_CAUTELADO)
                    registrar_log(st.session_state["nome_usuario"], "CAUTELA DRONE", f"DRONE {drow['matricula_aeronave']} | OPERADOR {operador_nome}")
                    limpar_cache("cautelas")
                    st.success("✅ Cautela registrada com sucesso.")


# =====================================================
# DEVOLUÇÃO
# =====================================================
elif menu == "🔁 Devolução de Drone":
    st.subheader("Devolução de Drone Cautelado")
    df = carregar_aba("cautelas")
    if df.empty:
        st.info("Não há cautelas registradas.")
    else:
        abertas = df[df["status"].astype(str).str.upper() == "ABERTA"].copy()
        if abertas.empty:
            st.info("Não há cautelas abertas.")
        else:
            opcoes = (
                abertas["id"].astype(str) + " - " +
                abertas["matricula_aeronave"].astype(str) + " - " +
                abertas["operador_nome"].astype(str) + " - " +
                abertas["data_retirada"].astype(str)
            ).tolist()

            with st.form("form_devolucao", clear_on_submit=True):
                cautela_sel = st.selectbox("Cautela aberta", opcoes)
                data_dev = st.text_input("Data de Devolução", value=data_hoje_br())
                hora_dev = st.text_input("Hora de Devolução", value=hora_agora_br())
                responsavel_devolucao = st.text_input("Responsável pela devolução", value=st.session_state["nome_usuario"])
                recebido_por = st.text_input("Recebido por")
                status_drone_pos = st.selectbox("Status do drone após devolução", [STATUS_DISPONIVEL, STATUS_MANUTENCAO])
                obs = st.text_area("Observações da devolução")
                submit = st.form_submit_button("Registrar Devolução", use_container_width=True)

                if submit:
                    data_ok, data_obj = validar_data_manual(data_dev)
                    hora_ok, hora_fmt = validar_hora_manual(hora_dev)
                    if not responsavel_devolucao or not recebido_por:
                        st.warning("Informe responsável pela devolução e quem recebeu.")
                    elif not data_ok or not hora_ok:
                        st.error("Data ou hora inválida.")
                    else:
                        id_cautela = int(cautela_sel.split(" - ")[0])
                        linha = df.index[df["id"].astype(int) == id_cautela][0] + 2
                        row = df[df["id"].astype(int) == id_cautela].iloc[0]
                        # L:Q = data_devolucao, hora_devolucao, responsavel_devolucao, recebido_por, status, observacoes
                        SHEETS["cautelas"].update(f"L{linha}:Q{linha}", [[
                            data_obj.strftime("%d/%m/%Y"), hora_fmt,
                            normalizar_texto(responsavel_devolucao), normalizar_texto(recebido_por),
                            "DEVOLVIDA", normalizar_texto(obs)
                        ]])
                        atualizar_status_drone(int(row["id_drone"]), status_drone_pos)
                        registrar_log(st.session_state["nome_usuario"], "DEVOLUÇÃO DRONE", f"CAUTELA {id_cautela} | DRONE {row['matricula_aeronave']}")
                        limpar_cache("cautelas")
                        st.success("✅ Devolução registrada com sucesso.")


# =====================================================
# INSPEÇÃO
# =====================================================
elif menu == "✅ Inspeção de Voo":
    st.subheader("Ficha de Inspeção de Voo")

    opcoes = drone_opcoes()
    if not opcoes:
        st.info("Cadastre ao menos um drone antes de registrar inspeções.")
    else:
        with st.form("form_inspecao", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                data_ins = st.text_input("Data", value=data_hoje_br())
            with c2:
                horario = st.text_input("Horário", value=hora_agora_br())
            with c3:
                ordem_voo = st.text_input("Ordem de Voo / OS nº")

            drone_sel = st.selectbox("RPA nº / Aeronave", opcoes)
            solicitante = st.text_input("Solicitante")
            local_coord = st.text_area("Local / Coordenadas")

            c4, c5 = st.columns(2)
            with c4:
                piloto_nome = st.text_input("Piloto em comando", value=st.session_state["nome_usuario"])
                piloto_id = st.text_input("ID do piloto")
            with c5:
                observador_nome = st.text_input("Observador de RPA")
                observador_id = st.text_input("ID do observador")

            st.markdown("### Verificações")
            st.caption("Marque V para verificado, X em caso de alteração ou N/A quando não aplicável.")

            vals = ["V", "X", "N/A"]
            tab_pre, tab_dur, tab_pos = st.tabs(["Antes do voo", "Durante o voo", "Após o voo"])

            pre_campos = [
                ("pre_update_firmware", "Update de firmware"),
                ("pre_cartao_sd", "Cartão SD"),
                ("pre_asas", "Asas rotativas/fixas"),
                ("pre_cabos", "Cabos (USB, HDMI, AC...)"),
                ("pre_carregador", "Carregador"),
                ("pre_cameras", "Câmeras"),
                ("pre_documentos_autorizacoes", "Documentos e autorizações"),
                ("pre_epis", "EPIs"),
                ("pre_aspecto_geral", "Aspecto geral"),
                ("pre_protetor_gimbal", "Protetor gimbal"),
                ("pre_calibracao_bussola", "Calibração bússola"),
                ("pre_area_decolagem_pouso", "Área de decolagem e pouso"),
                ("pre_download_mapas", "Download de mapas"),
                ("pre_carga_bateria", "Carga da bateria"),
                ("pre_carga_radio", "Carga do rádio"),
                ("pre_carga_dispositivo", "Carga smartphone/tablet/notebook"),
                ("pre_formatacao_sd", "Formatação do cartão SD"),
                ("pre_analise_risco", "Análise de risco"),
                ("pre_plano_voo", "Plano de voo"),
                ("pre_config_software", "Configuração do software de voo"),
            ]
            dur_campos = [
                ("dur_carga_bateria", "Carga da bateria"),
                ("dur_voltagem_bateria", "Voltagem da bateria"),
                ("dur_satelites", "Número de satélites"),
                ("dur_modo_voo", "Modo de voo"),
                ("dur_parametros_visuais", "Parâmetros visuais"),
                ("dur_telemetria", "Telemetria"),
                ("dur_performance", "Performance"),
            ]
            pos_campos = [
                ("pos_carga_bateria", "Carga da bateria"),
                ("pos_carga_radio", "Carga do rádio"),
                ("pos_aspecto_geral", "Aspecto geral"),
                ("pos_imagens_salvas", "Imagens salvas"),
                ("pos_relatorio_operacional", "Relatório operacional"),
            ]

            respostas = {}
            with tab_pre:
                for key, label in pre_campos:
                    respostas[key] = st.radio(label, vals, index=0, horizontal=True, key=key)
            with tab_dur:
                for key, label in dur_campos:
                    respostas[key] = st.radio(label, vals, index=0, horizontal=True, key=key)
            with tab_pos:
                for key, label in pos_campos:
                    respostas[key] = st.radio(label, vals, index=0, horizontal=True, key=key)

            observacoes = st.text_area("Observações")
            submit = st.form_submit_button("Registrar Inspeção", use_container_width=True)

            if submit:
                data_ok, data_obj = validar_data_manual(data_ins)
                hora_ok, hora_fmt = validar_hora_manual(horario)
                if not ordem_voo or not solicitante or not local_coord or not piloto_nome:
                    st.warning("Preencha ordem de voo, solicitante, local e piloto.")
                elif not data_ok or not hora_ok:
                    st.error("Data ou horário inválido.")
                else:
                    id_drone, drow = selecionar_drone_por_opcao(drone_sel)
                    df = carregar_aba("inspecoes")
                    novo_id = gerar_id(df)
                    row = [
                        novo_id, normalizar_texto(ordem_voo), id_drone, drow["matricula_aeronave"],
                        data_obj.strftime("%d/%m/%Y"), hora_fmt, normalizar_texto(solicitante),
                        normalizar_texto(local_coord), normalizar_texto(piloto_nome),
                        normalizar_texto(piloto_id), normalizar_texto(observador_nome),
                        normalizar_texto(observador_id)
                    ]
                    for key, _ in pre_campos + dur_campos + pos_campos:
                        row.append(respostas[key])
                    row += [normalizar_texto(observacoes), st.session_state["nome_usuario"], datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")]
                    SHEETS["inspecoes"].append_row(row)
                    registrar_log(st.session_state["nome_usuario"], "INSPEÇÃO DE VOO", f"OS {ordem_voo} | DRONE {drow['matricula_aeronave']}")
                    limpar_cache("inspecoes")
                    st.success("✅ Ficha de inspeção registrada com sucesso.")


# =====================================================
# RELATÓRIO OPERACIONAL / AVALIAÇÃO
# =====================================================
elif menu == "🛡️ Relatório / Avaliação Operacional":
    st.subheader("Relatório de Avaliação de Risco Operacional")

    opcoes = drone_opcoes()
    if not opcoes:
        st.info("Cadastre ao menos um drone antes de registrar relatório operacional.")
    else:
        with st.form("form_relatorio", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                numero = st.text_input("Relatório Operacional nº")
            with c2:
                data_rel = st.text_input("Data", value=data_hoje_br())
            with c3:
                drone_sel = st.selectbox("Nº Aeronave", opcoes)

            st.markdown("### Análise de risco")
            clima = st.text_input("Clima (chuva, garoa, sol, nublado...)")
            vento = st.text_input("Vento (leve, moderado, forte...)")
            obstaculos = st.text_area("Obstáculos (prédios, árvores, aeronaves, aves, pipas...)")
            local_pouso = st.text_input("Local de pouso/decolagem (apropriado, impróprio...)")
            mitigacao = st.text_area("Mitigação (sim, não, especificar nas observações)")
            obs_risco = st.text_area("Observações da análise de risco")

            st.markdown("### Registros de voo")
            qtd_voos = st.number_input("Quantidade de linhas de voo", min_value=1, max_value=10, value=1, step=1)
            voos = []
            for i in range(int(qtd_voos)):
                st.markdown(f"**Voo {i+1}**")
                vc1, vc2, vc3, vc4, vc5 = st.columns(5)
                with vc1:
                    acionamento = st.text_input("Acionamento", key=f"acionamento_{i}", placeholder="Ex: 09:10")
                with vc2:
                    corte = st.text_input("Corte", key=f"corte_{i}", placeholder="Ex: 09:35")
                with vc3:
                    tempo_voo = st.number_input("Tempo voo (min)", min_value=0, max_value=600, value=0, step=1, key=f"tempo_{i}")
                with vc4:
                    piloto = st.text_input("Piloto", key=f"piloto_{i}", value=st.session_state["nome_usuario"] if i == 0 else "")
                with vc5:
                    observador = st.text_input("Observador", key=f"observador_{i}")
                voos.append({
                    "acionamento": acionamento, "corte": corte, "tempo_voo_min": tempo_voo,
                    "piloto": piloto, "observador": observador
                })

            tempo_total = sum([v["tempo_voo_min"] for v in voos])

            st.markdown("### Histórico e mídias")
            localidade = st.text_input("Localidade")
            historico = st.text_area("Histórico")
            qtd_fotos = st.number_input("Quantidade de fotos", min_value=0, value=0, step=1)
            qtd_videos = st.number_input("Quantidade de vídeos", min_value=0, value=0, step=1)
            fotos_backup = st.text_area("Quais fotos salvar em backup? Informe os nomes dos arquivos")
            videos_backup = st.text_area("Quais vídeos salvar em backup? Informe tempo/nome dos vídeos")
            piloto_final = st.text_input("Assinatura/nome do piloto", value=st.session_state["nome_usuario"])
            observador_final = st.text_input("Assinatura/nome do observador")

            submit = st.form_submit_button("Registrar Relatório Operacional", use_container_width=True)

            if submit:
                data_ok, data_obj = validar_data_manual(data_rel)
                if not numero or not clima or not vento or not localidade or not historico:
                    st.warning("Preencha relatório nº, clima, vento, localidade e histórico.")
                elif not data_ok:
                    st.error("Data inválida.")
                else:
                    id_drone, drow = selecionar_drone_por_opcao(drone_sel)
                    df = carregar_aba("relatorios_operacionais")
                    novo_id = gerar_id(df)
                    SHEETS["relatorios_operacionais"].append_row([
                        novo_id, normalizar_texto(numero), data_obj.strftime("%d/%m/%Y"),
                        id_drone, drow["matricula_aeronave"], normalizar_texto(clima),
                        normalizar_texto(vento), normalizar_texto(obstaculos),
                        normalizar_texto(local_pouso), normalizar_texto(mitigacao),
                        normalizar_texto(obs_risco), normalizar_texto(localidade),
                        normalizar_texto(historico), int(qtd_fotos), int(qtd_videos),
                        normalizar_texto(fotos_backup), normalizar_texto(videos_backup),
                        int(tempo_total), normalizar_texto(piloto_final),
                        normalizar_texto(observador_final), st.session_state["nome_usuario"],
                        datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")
                    ])

                    df_voos = carregar_aba("voos_relatorio")
                    for v in voos:
                        if v["acionamento"] or v["corte"] or v["tempo_voo_min"] > 0:
                            SHEETS["voos_relatorio"].append_row([
                                gerar_id(df_voos), novo_id, normalizar_texto(v["acionamento"]),
                                normalizar_texto(v["corte"]), int(v["tempo_voo_min"]),
                                normalizar_texto(v["piloto"]), normalizar_texto(v["observador"])
                            ])
                            df_voos = carregar_aba("voos_relatorio")

                    registrar_log(st.session_state["nome_usuario"], "RELATÓRIO OPERACIONAL", f"REL {numero} | DRONE {drow['matricula_aeronave']}")
                    limpar_cache("relatorios_operacionais", "voos_relatorio")
                    st.success("✅ Relatório operacional registrado com sucesso.")


# =====================================================
# CONSULTA GERAL
# =====================================================
elif menu == "🔎 Consulta Geral":
    st.subheader("Consulta Geral / Inventário Operacional")
    tab1, tab2, tab3, tab4 = st.tabs(["Drones", "Cautelas", "Inspeções", "Relatórios Operacionais"])

    with tab1:
        df = carregar_aba("drones")
        if df.empty:
            st.info("Sem drones cadastrados.")
        else:
            f1, f2, f3 = st.columns(3)
            status = f1.selectbox("Status", ["Todos", STATUS_DISPONIVEL, STATUS_CAUTELADO, STATUS_MANUTENCAO, STATUS_BAIXADO])
            modelo = f2.text_input("Modelo contém")
            serie = f3.text_input("Série/Matrícula contém")
            dff = df.copy()
            if status != "Todos":
                dff = dff[dff["status"].astype(str).str.upper() == status]
            if modelo:
                dff = dff[dff["modelo"].astype(str).str.contains(modelo, case=False, na=False)]
            if serie:
                dff = dff[
                    dff["numero_serie"].astype(str).str.contains(serie, case=False, na=False) |
                    dff["matricula_aeronave"].astype(str).str.contains(serie, case=False, na=False)
                ]
            st.dataframe(dff, use_container_width=True)

    with tab2:
        df = carregar_aba("cautelas")
        if df.empty:
            st.info("Sem cautelas.")
        else:
            status = st.selectbox("Status da cautela", ["Todos", "ABERTA", "DEVOLVIDA"], key="status_cautela")
            dff = df.copy()
            if status != "Todos":
                dff = dff[dff["status"].astype(str).str.upper() == status]
            st.dataframe(dff, use_container_width=True)

    with tab3:
        df = carregar_aba("inspecoes")
        if df.empty:
            st.info("Sem inspeções.")
        else:
            termo = st.text_input("Buscar por OS, piloto, local ou drone", key="busca_inspecao")
            dff = df.copy()
            if termo:
                mask = pd.Series(False, index=dff.index)
                for col in ["ordem_voo", "matricula_aeronave", "local_coordenadas", "piloto_nome"]:
                    if col in dff.columns:
                        mask |= dff[col].astype(str).str.contains(termo, case=False, na=False)
                dff = dff[mask]
            st.dataframe(dff, use_container_width=True)

    with tab4:
        df = carregar_aba("relatorios_operacionais")
        if df.empty:
            st.info("Sem relatórios.")
        else:
            termo = st.text_input("Buscar por nº, localidade, piloto ou histórico", key="busca_rel")
            dff = df.copy()
            if termo:
                mask = pd.Series(False, index=dff.index)
                for col in ["numero_relatorio", "localidade", "piloto", "historico"]:
                    if col in dff.columns:
                        mask |= dff[col].astype(str).str.contains(termo, case=False, na=False)
                dff = dff[mask]
            st.dataframe(dff, use_container_width=True)


# =====================================================
# RELATÓRIOS PDF
# =====================================================
elif menu == "🖨️ Relatórios PDF":
    st.subheader("Emissão de Relatórios em PDF")
    tipo = st.selectbox("Tipo de relatório", [
        "Cautela de Drone",
        "Ficha de Inspeção de Voo",
        "Relatório Operacional",
        "Inventário de Drones",
        "Log de Auditoria"
    ])

    if tipo == "Cautela de Drone":
        df = carregar_aba("cautelas")
        if df.empty:
            st.info("Sem cautelas.")
        else:
            opcoes = (df["id"].astype(str) + " - " + df["matricula_aeronave"].astype(str) + " - " + df["operador_nome"].astype(str)).tolist()
            sel = st.selectbox("Selecione", opcoes)
            id_sel = int(sel.split(" - ")[0])
            r = df[df["id"].astype(int) == id_sel].iloc[0]
            linhas = [
                "## 1. IDENTIFICAÇÃO DA AERONAVE",
                f"ID / Matrícula: {r.get('matricula_aeronave','')}",
                f"Modelo: {r.get('modelo','')}",
                f"Nº de Série: {r.get('numero_serie','')}",
                "",
                "## 2. PERÍODO DE RESPONSABILIDADE",
                f"Data de Retirada: {r.get('data_retirada','')} | Hora: {r.get('hora_retirada','')}",
                f"Data de Devolução: {r.get('data_devolucao','')} | Hora: {r.get('hora_devolucao','')}",
                "",
                "## 3. FINALIDADE DA UTILIZAÇÃO",
                r.get("finalidade", ""),
                "",
                "## 4. TERMO DE RESPONSABILIDADE",
                "Declaro que recebi a aeronave remotamente pilotada acima identificada em perfeitas condições de uso, assumindo responsabilidade por sua utilização, guarda, conservação, transporte e devolução.",
                "Comprometo-me a utilizar o equipamento exclusivamente em atividades institucionais, operar conforme normas vigentes, zelar pela integridade do equipamento e comunicar dano, extravio ou irregularidade.",
                "",
                "## 5. ASSINATURAS",
                f"Operador: {r.get('operador_nome','')} | Matrícula: {r.get('operador_matricula','')}",
                f"Responsável pela entrega: {r.get('responsavel_entrega','')}",
                f"Responsável pela devolução: {r.get('responsavel_devolucao','')}",
                f"Recebido por: {r.get('recebido_por','')}",
                "",
                f"Observações: {r.get('observacoes','')}",
            ]
            download_pdf("Baixar Cautela em PDF", "CAUTELA DE DRONE – RESPONSABILIDADE DE USO", linhas, f"cautela_drone_{id_sel}")

    elif tipo == "Ficha de Inspeção de Voo":
        df = carregar_aba("inspecoes")
        if df.empty:
            st.info("Sem inspeções.")
        else:
            opcoes = (df["id"].astype(str) + " - OS " + df["ordem_voo"].astype(str) + " - " + df["matricula_aeronave"].astype(str)).tolist()
            sel = st.selectbox("Selecione", opcoes)
            id_sel = int(sel.split(" - ")[0])
            r = df[df["id"].astype(int) == id_sel].iloc[0]
            linhas = [
                "## DADOS DA INSPEÇÃO",
                f"Data: {r.get('data','')} | Horário: {r.get('horario','')}",
                f"Ordem de Voo / OS nº: {r.get('ordem_voo','')}",
                f"RPA nº: {r.get('matricula_aeronave','')}",
                f"Solicitante: {r.get('solicitante','')}",
                f"Local/Coordenadas: {r.get('local_coordenadas','')}",
                f"Piloto em comando: {r.get('piloto_nome','')} | ID: {r.get('piloto_id','')}",
                f"Observador de RPA: {r.get('observador_nome','')} | ID: {r.get('observador_id','')}",
                "",
                "## VERIFICAÇÃO ANTES DO VOO",
                f"Update firmware: {r.get('pre_update_firmware','')} | Cartão SD: {r.get('pre_cartao_sd','')} | Asas: {r.get('pre_asas','')}",
                f"Cabos: {r.get('pre_cabos','')} | Carregador: {r.get('pre_carregador','')} | Câmeras: {r.get('pre_cameras','')}",
                f"Documentos/autorizações: {r.get('pre_documentos_autorizacoes','')} | EPIs: {r.get('pre_epis','')}",
                f"Aspecto geral: {r.get('pre_aspecto_geral','')} | Protetor gimbal: {r.get('pre_protetor_gimbal','')}",
                f"Calibração bússola: {r.get('pre_calibracao_bussola','')} | Área de decolagem/pouso: {r.get('pre_area_decolagem_pouso','')}",
                f"Download mapas: {r.get('pre_download_mapas','')} | Bateria: {r.get('pre_carga_bateria','')} | Rádio: {r.get('pre_carga_radio','')}",
                f"Dispositivo: {r.get('pre_carga_dispositivo','')} | Formatação SD: {r.get('pre_formatacao_sd','')}",
                f"Análise de risco: {r.get('pre_analise_risco','')} | Plano de voo: {r.get('pre_plano_voo','')} | Software: {r.get('pre_config_software','')}",
                "",
                "## DURANTE O VOO",
                f"Carga bateria: {r.get('dur_carga_bateria','')} | Voltagem: {r.get('dur_voltagem_bateria','')} | Satélites: {r.get('dur_satelites','')}",
                f"Modo de voo: {r.get('dur_modo_voo','')} | Parâmetros visuais: {r.get('dur_parametros_visuais','')} | Telemetria: {r.get('dur_telemetria','')} | Performance: {r.get('dur_performance','')}",
                "",
                "## APÓS O VOO",
                f"Carga bateria: {r.get('pos_carga_bateria','')} | Carga rádio: {r.get('pos_carga_radio','')} | Aspecto geral: {r.get('pos_aspecto_geral','')}",
                f"Imagens salvas: {r.get('pos_imagens_salvas','')} | Relatório operacional: {r.get('pos_relatorio_operacional','')}",
                "",
                f"Observações: {r.get('observacoes','')}",
                "",
                "Assinatura Piloto: ____________________________    Assinatura Observador: ____________________________",
            ]
            download_pdf("Baixar Inspeção em PDF", "FICHA DE INSPEÇÃO DE VOO", linhas, f"inspecao_voo_{id_sel}")

    elif tipo == "Relatório Operacional":
        df = carregar_aba("relatorios_operacionais")
        df_voos = carregar_aba("voos_relatorio")
        if df.empty:
            st.info("Sem relatórios.")
        else:
            opcoes = (df["id"].astype(str) + " - Nº " + df["numero_relatorio"].astype(str) + " - " + df["matricula_aeronave"].astype(str)).tolist()
            sel = st.selectbox("Selecione", opcoes)
            id_sel = int(sel.split(" - ")[0])
            r = df[df["id"].astype(int) == id_sel].iloc[0]
            linhas = [
                f"Relatório Operacional nº: {r.get('numero_relatorio','')}",
                f"Data: {r.get('data','')} | Nº Aeronave: {r.get('matricula_aeronave','')}",
                "",
                "## ANÁLISE DE RISCO",
                f"Clima: {r.get('clima','')}",
                f"Vento: {r.get('vento','')}",
                f"Obstáculos: {r.get('obstaculos','')}",
                f"Local pouso/decolagem: {r.get('local_pouso_decolagem','')}",
                f"Mitigação: {r.get('mitigacao','')}",
                f"Observações: {r.get('observacoes_risco','')}",
                "",
                "## VOOS",
            ]
            if not df_voos.empty:
                vv = df_voos[df_voos["id_relatorio"].astype(str) == str(id_sel)]
                for _, v in vv.iterrows():
                    linhas.append(f"Acionamento: {v.get('acionamento','')} | Corte: {v.get('corte','')} | Tempo: {v.get('tempo_voo_min','')} min | Piloto: {v.get('piloto','')} | Observador: {v.get('observador','')}")
            linhas += [
                f"Tempo total de voo: {r.get('tempo_total_voo_min','')} min",
                f"Localidade: {r.get('localidade','')}",
                "",
                "## HISTÓRICO",
                r.get("historico", ""),
                "",
                f"Quantidade de fotos: {r.get('quantidade_fotos','')}",
                f"Quantidade de vídeos: {r.get('quantidade_videos','')}",
                f"Fotos para backup: {r.get('fotos_backup','')}",
                f"Vídeos para backup: {r.get('videos_backup','')}",
                "",
                f"Ass. piloto: {r.get('piloto','')}",
                f"Ass. observador: {r.get('observador','')}",
            ]
            download_pdf("Baixar Relatório Operacional em PDF", "RELATÓRIO DE AVALIAÇÃO DE RISCO OPERACIONAL", linhas, f"relatorio_operacional_{id_sel}")

    elif tipo == "Inventário de Drones":
        df = carregar_aba("drones")
        linhas = ["## INVENTÁRIO DE DRONES"]
        if df.empty:
            linhas.append("Nenhum drone cadastrado.")
        else:
            for _, r in df.iterrows():
                linhas.append(f"ID {r.get('id','')} | Matrícula: {r.get('matricula_aeronave','')} | Modelo: {r.get('modelo','')} | Série: {r.get('numero_serie','')} | Status: {r.get('status','')}")
        download_pdf("Baixar Inventário em PDF", "INVENTÁRIO DE DRONES", linhas, "inventario_drones")

    elif tipo == "Log de Auditoria":
        df = carregar_aba("log_auditoria")
        linhas = ["## LOG DE AUDITORIA"]
        if df.empty:
            linhas.append("Nenhum log registrado.")
        else:
            for _, r in df.tail(500).iterrows():
                linhas.append(f"{r.get('data','')} {r.get('hora','')} | {r.get('usuario','')} | {r.get('acao','')} | {r.get('detalhes','')}")
        download_pdf("Baixar Log em PDF", "LOG DE AUDITORIA", linhas, "log_auditoria")


# =====================================================
# CADASTRO DE USUÁRIO
# =====================================================
elif menu == "👤 Cadastrar Usuário":
    st.subheader("Cadastro de Usuário")
    tipo_label = st.selectbox("Tipo de usuário", ["Piloto/Agente", "Gestor"])
    tipo = "agente" if tipo_label == "Piloto/Agente" else "gestor"

    with st.form("form_cad_usuario", clear_on_submit=True):
        login = st.text_input("Login / Matrícula")
        nome = st.text_input("Nome")
        matricula = st.text_input("Matrícula funcional")
        id_piloto = st.text_input("ID de piloto / credencial operacional")
        senha = st.text_input("Senha inicial", value="1234", type="password")
        submit = st.form_submit_button("Cadastrar usuário", use_container_width=True)

        if submit:
            if not login or not nome:
                st.warning("Informe login/matrícula e nome.")
            else:
                ok = cadastrar_usuario(tipo, login.strip(), nome.strip(), matricula.strip(), id_piloto.strip(), senha.strip())
                if ok:
                    st.success("✅ Usuário cadastrado com sucesso. No primeiro acesso deverá trocar a senha.")
                else:
                    st.error("Já existe usuário ativo com este login.")


# =====================================================
# GERENCIAR USUÁRIOS
# =====================================================
elif menu == "📋 Gerenciar Usuários":
    st.subheader("Gerenciamento de Usuários")
    df = listar_usuarios()
    if df.empty:
        st.info("Nenhum usuário cadastrado.")
    else:
        ativos = df[df["status"].astype(str).str.upper() == STATUS_ATIVO]
        st.dataframe(ativos.drop(columns=["senha"], errors="ignore"), use_container_width=True)

        opcoes = (ativos["id"].astype(str) + " - " + ativos["tipo_usuario"].astype(str) + " - " + ativos["login"].astype(str) + " - " + ativos["nome"].astype(str)).tolist()
        if opcoes:
            sel = st.selectbox("Selecione usuário", opcoes)
            id_user = int(sel.split(" - ")[0])
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Resetar senha para 1234", use_container_width=True):
                    resetar_senha(id_user, "1234")
                    st.success("Senha resetada.")
                    time_mod.sleep(1)
                    st.rerun()
            with c2:
                if st.button("Inativar usuário", type="primary", use_container_width=True):
                    inativar_usuario(id_user)
                    st.success("Usuário inativado.")
                    time_mod.sleep(1)
                    st.rerun()


# =====================================================
# MINHA CONTA
# =====================================================
elif menu == "🔐 Minha Conta":
    st.subheader("Minha Conta")
    with st.form("form_minha_conta"):
        senha_atual = st.text_input("Senha atual", type="password")
        nova = st.text_input("Nova senha", type="password")
        conf = st.text_input("Confirmar nova senha", type="password")
        submit = st.form_submit_button("Alterar senha", use_container_width=True)
        if submit:
            if not validar_senha_por_id(st.session_state["usuario_id"], senha_atual):
                st.error("Senha atual incorreta.")
            elif nova != conf:
                st.error("A nova senha e a confirmação não coincidem.")
            elif len(nova) < 4:
                st.error("A senha deve ter pelo menos 4 caracteres.")
            else:
                alterar_senha(st.session_state["usuario_id"], nova)
                st.success("Senha alterada com sucesso.")


# =====================================================
# LOG
# =====================================================
elif menu == "📜 Log de Auditoria":
    st.subheader("Log de Auditoria")
    df = carregar_aba("log_auditoria")
    if df.empty:
        st.info("Nenhum log registrado.")
    else:
        usuario = st.text_input("Filtrar por usuário")
        acao = st.text_input("Filtrar por ação")
        dff = df.copy()
        if usuario:
            dff = dff[dff["usuario"].astype(str).str.contains(usuario, case=False, na=False)]
        if acao:
            dff = dff[dff["acao"].astype(str).str.contains(acao, case=False, na=False)]
        st.dataframe(dff.sort_index(ascending=False), use_container_width=True)
