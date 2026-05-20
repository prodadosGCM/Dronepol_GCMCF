import streamlit as st
import gspread
import pandas as pd
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from datetime import datetime
import hashlib
import time as time_mod
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from streamlit_option_menu import option_menu

# =====================================================
# SIG-GCM – Sistema Integrado de Gestão da GCM
# Secretaria Municipal de Segurança e Ordem Pública
# Cabo Frio / RJ  |  Streamlit + Google Sheets
# =====================================================

st.set_page_config(
    page_title="SIG-GCM · Cabo Frio",
    page_icon="🚔",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# TEMA / CSS  (espelha o visual React)
# ─────────────────────────────────────────
st.markdown("""
<style>
/* ── variáveis de cor ── */
:root {
    --accent:      #eab308;
    --accent-fg:   #0f172a;
    --sidebar-bg:  #0f172a;
    --sidebar-fg:  #e2e8f0;
    --surface:     #ffffff;
    --muted:       #64748b;
    --border:      #e2e8f0;
    --success:     #22c55e;
    --destructive: #ef4444;
}

/* ── topbar ── */
header[data-testid="stHeader"] { display: none !important; }

/* ── sidebar ── */
[data-testid="stSidebar"] {
    background: var(--sidebar-bg) !important;
    border-right: 1px solid #1e293b;
}
[data-testid="stSidebar"] * { color: var(--sidebar-fg) !important; }
[data-testid="stSidebar"] .nav-link-selected { background: var(--accent) !important; color: var(--accent-fg) !important; }

/* ── brand bar no topo da sidebar ── */
.brand-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px 10px;
    border-bottom: 1px solid #1e293b;
    margin-bottom: 4px;
}
.brand-icon {
    width: 36px; height: 36px;
    border-radius: 6px;
    background: linear-gradient(135deg, var(--accent), #ca8a04);
    display: flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 18px;
    color: var(--accent-fg);
    flex-shrink: 0;
}
.brand-text { line-height: 1.25; }
.brand-text .name  { font-size: 0.8rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--accent) !important; }
.brand-text .sub   { font-size: 0.65rem; color: #94a3b8 !important; }

/* ── topbar fake ── */
.topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 20px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    margin-bottom: 18px;
}
.topbar-left  { font-size: .85rem; font-weight: 600; color: #0f172a; }
.topbar-right { font-size: .75rem; color: var(--muted); font-family: monospace; }

/* ── cards de métrica ── */
.metric-card {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    padding: 18px 20px;
    border-radius: 14px;
    color: white;
    box-shadow: 0 4px 16px rgba(0,0,0,.18);
    border: 1px solid rgba(255,255,255,.07);
    min-height: 108px;
}
.metric-card .mc-label { margin: 0; font-size: .82rem; color: #94a3b8; font-weight: 600; }
.metric-card .mc-value { margin: 8px 0 0; font-size: 2.1rem; font-weight: 900; color: #ffffff; line-height: 1; }
.metric-card .mc-icon  { font-size: 1.4rem; float: right; opacity: .5; }

/* ── status badges ── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 99px;
    font-size: .72rem;
    font-weight: 700;
    letter-spacing: .04em;
}
.badge-green  { background:#dcfce7; color:#15803d; }
.badge-yellow { background:#fef9c3; color:#854d0e; }
.badge-red    { background:#fee2e2; color:#991b1b; }
.badge-gray   { background:#f1f5f9; color:#475569; }
.badge-blue   { background:#dbeafe; color:#1d4ed8; }

/* ── section box ── */
.section-box {
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 14px;
}

/* ── footer ── */
.footer-bar {
    margin-top: 32px;
    padding: 10px 20px;
    background: var(--surface);
    border-top: 1px solid var(--border);
    display: flex; justify-content: space-between;
    font-size: .7rem; color: var(--muted); font-family: monospace;
}
.footer-status { display: flex; align-items: center; gap: 6px; }
.dot-green { width: 8px; height: 8px; border-radius: 50%; background: var(--success); display: inline-block; }

/* ── form containers ── */
div[data-testid="stForm"] {
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px !important;
}

/* ── dataframe ── */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* ── buttons ── */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    font-size: .85rem;
}
.stButton > button[kind="primary"] { background: var(--accent) !important; color: var(--accent-fg) !important; border: none !important; }

/* ── tabs ── */
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    border-bottom: 2px solid var(--accent) !important;
    color: #0f172a !important; font-weight: 700 !important;
}

/* scrollbar minimalista */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 99px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────
TZ = ZoneInfo("America/Sao_Paulo")
STATUS_ATIVO       = "ATIVO"
STATUS_INATIVO     = "INATIVO"
STATUS_DISPONIVEL  = "DISPONÍVEL"
STATUS_CAUTELADO   = "CAUTELADO"
STATUS_MANUTENCAO  = "MANUTENÇÃO"
STATUS_BAIXADO     = "BAIXADO"

TIPOS_USUARIO = {"Administrador": "admin", "Gestor": "gestor", "Piloto/Agente": "agente"}

ABAS = {
    "drones": [
        "id","matricula_aeronave","modelo","numero_serie","fabricante",
        "apelido","status","data_cadastro","observacoes"
    ],
    "usuarios": [
        "id","tipo_usuario","login","nome","matricula","id_piloto",
        "senha","primeiro_acesso","status"
    ],
    "cautelas": [
        "id","id_drone","matricula_aeronave","modelo","numero_serie",
        "data_retirada","hora_retirada","finalidade","operador_nome",
        "operador_matricula","responsavel_entrega","data_devolucao",
        "hora_devolucao","responsavel_devolucao","recebido_por",
        "status","observacoes","usuario_registro","data_registro"
    ],
    "inspecoes": [
        "id","ordem_voo","id_drone","matricula_aeronave","data","horario",
        "solicitante","local_coordenadas","piloto_nome","piloto_id",
        "observador_nome","observador_id",
        "pre_update_firmware","pre_cartao_sd","pre_asas","pre_cabos",
        "pre_carregador","pre_cameras","pre_documentos_autorizacoes",
        "pre_epis","pre_aspecto_geral","pre_protetor_gimbal",
        "pre_calibracao_bussola","pre_area_decolagem_pouso",
        "pre_download_mapas","pre_carga_bateria","pre_carga_radio",
        "pre_carga_dispositivo","pre_formatacao_sd","pre_analise_risco",
        "pre_plano_voo","pre_config_software",
        "dur_carga_bateria","dur_voltagem_bateria","dur_satelites",
        "dur_modo_voo","dur_parametros_visuais","dur_telemetria","dur_performance",
        "pos_carga_bateria","pos_carga_radio","pos_aspecto_geral",
        "pos_imagens_salvas","pos_relatorio_operacional",
        "observacoes","usuario_registro","data_registro"
    ],
    "relatorios_operacionais": [
        "id","numero_relatorio","data","id_drone","matricula_aeronave",
        "clima","vento","obstaculos","local_pouso_decolagem","mitigacao",
        "observacoes_risco","localidade","historico","quantidade_fotos",
        "quantidade_videos","fotos_backup","videos_backup",
        "tempo_total_voo_min","piloto","observador","usuario_registro","data_registro"
    ],
    "voos_relatorio": [
        "id","id_relatorio","acionamento","corte","tempo_voo_min","piloto","observador"
    ],
    "ocorrencias": [
        "id","numero","data","hora","tipo","descricao","local","agente_responsavel",
        "viatura","status","resolucao","usuario_registro","data_registro"
    ],
    "agentes": [
        "id","matricula","nome","cargo","turno","status","observacoes","data_cadastro"
    ],
    "viaturas": [
        "id","placa","modelo","ano","status","km_atual","observacoes","data_cadastro"
    ],
    "log_auditoria": ["data","hora","usuario","acao","detalhes"],
}

# ─────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────
def make_hashes(p):  return hashlib.sha256(str(p).encode()).hexdigest()
def check_hashes(p, h): return make_hashes(p) == str(h)
def agora_str():
    a = datetime.now(TZ)
    return a.strftime("%d/%m/%Y"), a.strftime("%H:%M:%S")
def data_hoje_br(): return datetime.now(TZ).strftime("%d/%m/%Y")
def hora_agora_br(): return datetime.now(TZ).strftime("%H:%M")
def normalizar(s): return str(s).strip().upper()

def gerar_id(df):
    if df.empty or "id" not in df.columns: return 1
    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    return int(ids.max()) + 1 if not ids.empty else 1

def validar_data(s):
    try:
        s = str(s).strip().replace("-","/").replace(".","/")
        partes = s.split("/")
        if len(partes) == 3:
            d,m,a = partes
            s = f"{d.zfill(2)}/{m.zfill(2)}/{('20'+a if len(a)==2 else a)}"
        return True, datetime.strptime(s, "%d/%m/%Y")
    except: return False, None

def validar_hora(s):
    try:
        s = str(s).strip()
        if ":" not in s:
            if len(s)==4: s=f"{s[:2]}:{s[2:]}"
            elif len(s)==3: s=f"0{s[0]}:{s[1:]}"
        return True, datetime.strptime(s,"%H:%M").strftime("%H:%M")
    except: return False, None

def badge(txt, cor="gray"):
    cores = {"green":"badge-green","yellow":"badge-yellow","red":"badge-red","blue":"badge-blue","gray":"badge-gray"}
    return f'<span class="badge {cores.get(cor,"badge-gray")}">{txt}</span>'

def status_cor(s):
    s = str(s).upper()
    if s in (STATUS_DISPONIVEL,"ATIVO","DEVOLVIDA","ENCERRADA"): return "green"
    if s in (STATUS_CAUTELADO,"ABERTA","EM ANDAMENTO"): return "yellow"
    if s in (STATUS_MANUTENCAO,"BAIXADO","INATIVO"): return "red"
    return "gray"

# ─────────────────────────────────────────
# SESSÃO
# ─────────────────────────────────────────
def init_session():
    defaults = {
        "logado": False, "usuario_id": None, "tipo_usuario": None,
        "nome_usuario": "", "login_usuario": "", "primeiro_acesso": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

init_session()

# ─────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────
@st.cache_resource
def conectar_planilha():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["google_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        client = gspread.authorize(creds)
        key = st.secrets.get("spreadsheet_key","")
        if not key:
            st.error("Informe spreadsheet_key em .streamlit/secrets.toml")
            st.stop()
        return client.open_by_key(key)
    except Exception as e:
        st.error(f"Erro Google Sheets: {e}")
        st.stop()

def obter_aba(nome):
    p = conectar_planilha()
    try:
        return p.worksheet(nome)
    except:
        aba = p.add_worksheet(title=nome, rows=3000, cols=max(len(ABAS[nome]),10))
        aba.append_row(ABAS[nome])
        return aba

SHEETS = {n: obter_aba(n) for n in ABAS}

@st.cache_data(ttl=60)
def carregar_aba(nome):
    df = pd.DataFrame(SHEETS[nome].get_all_records())
    if not df.empty: df.columns = df.columns.str.strip().str.lower()
    return df

def limpar_cache(): carregar_aba.clear()

def registrar_log(usuario, acao, detalhes=""):
    d, h = agora_str()
    SHEETS["log_auditoria"].append_row([d, h, str(usuario).upper(), str(acao).upper(), str(detalhes).upper()])
    limpar_cache()

# bootstrap admin
def bootstrap_admin():
    df = pd.DataFrame(SHEETS["usuarios"].get_all_records())
    if df.empty:
        SHEETS["usuarios"].append_row([1,"admin","admin","ADMINISTRADOR","","",make_hashes("admin123"),1,STATUS_ATIVO])
        return
    df.columns = df.columns.str.strip().str.lower()
    existe = not df[(df["tipo_usuario"].str.lower()=="admin")&(df["login"].str.lower()=="admin")&(df["status"].str.upper()==STATUS_ATIVO)].empty
    if not existe:
        ids = pd.to_numeric(df.get("id",pd.Series(dtype=float)),errors="coerce").dropna()
        nid = int(ids.max())+1 if not ids.empty else 1
        SHEETS["usuarios"].append_row([nid,"admin","admin","ADMINISTRADOR","","",make_hashes("admin123"),1,STATUS_ATIVO])

bootstrap_admin()

# ─────────────────────────────────────────
# USUÁRIOS
# ─────────────────────────────────────────
def buscar_usuario(tipo, login):
    df = carregar_aba("usuarios")
    if df.empty: return None
    m = (df["tipo_usuario"].str.lower()==tipo.lower())&(df["login"].str.lower()==login.strip().lower())&(df["status"].str.upper()==STATUS_ATIVO)
    r = df[m]
    return None if r.empty else r.iloc[0]

def login_usuario(tipo, login, senha):
    u = buscar_usuario(tipo, login)
    if u is not None and check_hashes(senha, u["senha"]):
        return {"sucesso":True,"id":int(u["id"]),"nome":str(u["nome"]),"login":str(u["login"]),"primeiro_acesso":bool(int(u.get("primeiro_acesso",0) or 0))}
    return {"sucesso":False}

def linha_usuario(id_u):
    df = carregar_aba("usuarios")
    if df.empty: return None, None
    df["id"] = pd.to_numeric(df["id"],errors="coerce")
    r = df[df["id"]==int(id_u)]
    if r.empty: return None, None
    return r.index[0]+2, r.iloc[0]

def alterar_senha(id_u, nova):
    l, u = linha_usuario(id_u)
    if l is None: return False
    SHEETS["usuarios"].update(f"G{l}:H{l}", [[make_hashes(nova),0]])
    registrar_log(u.get("nome","USUARIO"),"ALTERAÇÃO DE SENHA",f"ID {id_u}")
    limpar_cache(); return True

def validar_senha(id_u, senha):
    _, u = linha_usuario(id_u)
    return u is not None and check_hashes(senha, u["senha"])

def cadastrar_usuario(tipo, login, nome, matricula, id_piloto, senha="1234"):
    df = carregar_aba("usuarios")
    if not df.empty:
        if not df[(df["tipo_usuario"].str.lower()==tipo.lower())&(df["login"].str.lower()==login.lower())&(df["status"].str.upper()==STATUS_ATIVO)].empty:
            return False
    SHEETS["usuarios"].append_row([gerar_id(df),tipo,login,normalizar(nome),normalizar(matricula),normalizar(id_piloto),make_hashes(senha),1,STATUS_ATIVO])
    registrar_log(st.session_state.get("nome_usuario","SISTEMA"),"CADASTRO USUÁRIO",f"{tipo}|{login}|{nome}")
    limpar_cache(); return True

def resetar_senha(id_u, nova="1234"):
    l, u = linha_usuario(id_u)
    if l is None: return False
    SHEETS["usuarios"].update(f"G{l}:H{l}", [[make_hashes(nova),1]])
    registrar_log(st.session_state.get("nome_usuario","SISTEMA"),"RESET SENHA",f"ID {id_u}")
    limpar_cache(); return True

def inativar_usuario(id_u):
    l, u = linha_usuario(id_u)
    if l is None: return False
    SHEETS["usuarios"].update(f"I{l}", [[STATUS_INATIVO]])
    registrar_log(st.session_state.get("nome_usuario","SISTEMA"),"INATIVAÇÃO",f"ID {id_u}")
    limpar_cache(); return True

# ─────────────────────────────────────────
# DRONES
# ─────────────────────────────────────────
def carregar_drones():
    df = carregar_aba("drones")
    if not df.empty and "id" in df.columns:
        df["id"] = pd.to_numeric(df["id"],errors="coerce")
    return df

def drone_opcoes(status=None):
    df = carregar_drones()
    if df.empty: return []
    if status: df = df[df["status"].str.upper()==status]
    return (df["id"].astype(str)+" - "+df["matricula_aeronave"].astype(str)+" - "+df["modelo"].astype(str)+" - "+df["numero_serie"].astype(str)).tolist()

def selecionar_drone(opcao):
    id_d = int(str(opcao).split(" - ")[0])
    df = carregar_drones()
    return id_d, df[df["id"]==id_d].iloc[0]

def atualizar_status_drone(id_d, status):
    df = carregar_drones()
    l = df.index[df["id"]==int(id_d)][0]+2
    SHEETS["drones"].update(f"G{l}", [[status]])
    limpar_cache()

# ─────────────────────────────────────────
# PDF
# ─────────────────────────────────────────
def gerar_pdf(titulo, linhas, usuario):
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    W, H = A4; mg = 40; yt = W - 2*mg; y = H - 40
    def cab():
        nonlocal y
        pdf.setFont("Helvetica-Bold",11)
        pdf.drawString(mg,y,"PREFEITURA MUNICIPAL DE CABO FRIO"); y-=14
        pdf.drawString(mg,y,"SECRETARIA DE SEGURANÇA E ORDEM PÚBLICA"); y-=14
        pdf.drawString(mg,y,"GUARDA CIVIL MUNICIPAL – SIG-GCM"); y-=22
        pdf.setFont("Helvetica-Bold",14)
        pdf.drawCentredString(W/2,y,titulo); y-=20
        pdf.setFont("Helvetica",8)
        pdf.drawString(mg,y,f"Emitido em: {datetime.now(TZ).strftime('%d/%m/%Y %H:%M:%S')} | Usuário: {usuario}"); y-=20
    def np():
        nonlocal y; pdf.showPage(); y=H-40; cab()
    pdf.setTitle(titulo); cab(); pdf.setFont("Helvetica",10)
    for item in linhas:
        t = str(item)
        if t.startswith("## "):
            y-=6
            if y<60: np()
            pdf.setFont("Helvetica-Bold",11); pdf.drawString(mg,y,t[3:]); y-=16; pdf.setFont("Helvetica",10)
            continue
        for l in simpleSplit(t,"Helvetica",10,yt):
            if y<50: np()
            pdf.drawString(mg,y,l); y-=14
        if t=="": y-=6
    pdf.save(); buf.seek(0)
    return buf.getvalue()

def btn_pdf(label, titulo, linhas, base):
    b = gerar_pdf(titulo, linhas, st.session_state.get("nome_usuario","SISTEMA"))
    st.download_button(label=label, data=b, file_name=f"{base}.pdf", mime="application/pdf", use_container_width=True)

# ─────────────────────────────────────────
# COMPONENTES DE UI
# ─────────────────────────────────────────
def card_metrica(titulo, valor, icone="📊"):
    st.markdown(f"""
    <div class="metric-card">
        <span class="mc-icon">{icone}</span>
        <p class="mc-label">{titulo}</p>
        <p class="mc-value">{valor}</p>
    </div>""", unsafe_allow_html=True)

def topbar():
    perfil = st.session_state.get("tipo_usuario","")
    nome = st.session_state.get("nome_usuario","")
    d, h = agora_str()
    perfil_label = {"admin":"Administrador","gestor":"Gestor","agente":"Piloto/Agente"}.get(perfil,perfil.upper())
    st.markdown(f"""
    <div class="topbar">
        <span class="topbar-left">🚔 SIG-GCM &nbsp;·&nbsp; Cabo Frio / RJ</span>
        <span class="topbar-right">{nome} &nbsp;·&nbsp; {perfil_label} &nbsp;·&nbsp; {d} {h}</span>
    </div>""", unsafe_allow_html=True)

def footer():
    st.markdown("""
    <div class="footer-bar">
        <span>SIG-GCM v1.0.0 · Secretaria Municipal de Segurança e Ordem Pública · Cabo Frio/RJ</span>
        <span class="footer-status"><span class="dot-green"></span> Servidor operacional</span>
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
#  LOGIN
# ═══════════════════════════════════════════════════════
if not st.session_state["logado"]:
    c1,c2,c3 = st.columns([1,1.2,1])
    with c2:
        st.markdown("""
        <div style='text-align:center;padding:24px 0 8px'>
            <div style='font-size:3rem'>🚔</div>
            <h2 style='margin:4px 0 2px;color:#0f172a;font-size:1.5rem'>SIG-GCM</h2>
            <p style='color:#64748b;font-size:.85rem;margin:0'>Secretaria de Segurança e Ordem Pública · Cabo Frio/RJ</p>
        </div>""", unsafe_allow_html=True)
        with st.form("login"):
            perfil = st.radio("Entrar como:", list(TIPOS_USUARIO.keys()), horizontal=True)
            login_input = st.text_input("Usuário / Matrícula")
            senha_input = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar →", use_container_width=True):
                res = login_usuario(TIPOS_USUARIO[perfil], login_input.strip(), senha_input)
                if res["sucesso"]:
                    st.session_state.update({"logado":True,"tipo_usuario":TIPOS_USUARIO[perfil],
                        "usuario_id":res["id"],"nome_usuario":res["nome"],
                        "login_usuario":res["login"],"primeiro_acesso":res["primeiro_acesso"]})
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
        st.caption("Acesso inicial: usuário `admin`, senha `admin123`.")
    st.stop()

# ─ primeiro acesso ─
if st.session_state.get("primeiro_acesso"):
    st.warning("⚠️ Altere sua senha inicial antes de continuar.")
    with st.form("form_pa"):
        n1 = st.text_input("Nova senha", type="password")
        n2 = st.text_input("Confirmar nova senha", type="password")
        if st.form_submit_button("Atualizar senha", use_container_width=True):
            if n1!=n2: st.error("As senhas não coincidem.")
            elif len(n1)<4: st.error("Mínimo 4 caracteres.")
            else:
                alterar_senha(st.session_state["usuario_id"],n1)
                st.session_state["primeiro_acesso"]=False
                st.success("Senha atualizada!"); time_mod.sleep(1); st.rerun()
    st.stop()

# ═══════════════════════════════════════════════════════
#  SIDEBAR / MENU  (espelhando o NAV do React)
# ═══════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div class="brand-bar">
        <div class="brand-icon">G</div>
        <div class="brand-text">
            <div class="name">SIG-GCM</div>
            <div class="sub">Cabo Frio / RJ</div>
        </div>
    </div>""", unsafe_allow_html=True)

    perfil = st.session_state["tipo_usuario"]
    is_admin = perfil in ("admin","gestor")

    # ─ menu completo (admin/gestor) ─
    if is_admin:
        menu = option_menu(
            menu_title=None,
            options=[
                "Dashboard","Ocorrências","Central 153","Despacho",
                "Monitoramento","DRONEPOL","Fiscalização",
                "Agentes","Viaturas","Equipes","RAS / Extra",
                "Relatórios","Auditoria",
                "──────────",
                "Usuários","Minha Conta","Sair"
            ],
            icons=[
                "speedometer2","clipboard-data","telephone","broadcast",
                "camera-video","controller","megaphone",
                "people","truck","shield-check","calendar3",
                "bar-chart","journal-text",
                "dash",
                "person-gear","person-circle","box-arrow-right"
            ],
            default_index=0,
            styles={
                "container":{"padding":"4px 8px","background-color":"#0f172a"},
                "icon":{"color":"#94a3b8","font-size":"15px"},
                "nav-link":{"font-size":"13px","color":"#e2e8f0","padding":"9px 12px",
                            "border-radius":"8px","margin":"1px 0","--hover-color":"#1e293b"},
                "nav-link-selected":{"background-color":"#eab308","color":"#0f172a",
                                     "font-weight":"700"},
                "menu-title":{"display":"none"},
            }
        )
    else:
        # ─ menu piloto/agente ─
        menu = option_menu(
            menu_title=None,
            options=["Dashboard","DRONEPOL","Relatórios","Minha Conta","Sair"],
            icons=["speedometer2","controller","bar-chart","person-circle","box-arrow-right"],
            default_index=0,
            styles={
                "container":{"padding":"4px 8px","background-color":"#0f172a"},
                "icon":{"color":"#94a3b8","font-size":"15px"},
                "nav-link":{"font-size":"13px","color":"#e2e8f0","padding":"9px 12px",
                            "border-radius":"8px","margin":"1px 0","--hover-color":"#1e293b"},
                "nav-link-selected":{"background-color":"#eab308","color":"#0f172a","font-weight":"700"},
            }
        )

    st.markdown(f"""
    <div style='padding:12px 12px 8px;border-top:1px solid #1e293b;margin-top:8px'>
        <div style='font-size:.75rem;color:#94a3b8'>Conectado como</div>
        <div style='font-size:.85rem;font-weight:700;color:#e2e8f0;margin-top:2px'>{st.session_state["nome_usuario"]}</div>
        <div style='font-size:.68rem;color:#64748b;font-family:monospace'>{perfil.upper()}</div>
    </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────
if menu == "Sair":
    for k in ["logado","usuario_id","tipo_usuario","nome_usuario","login_usuario","primeiro_acesso"]:
        st.session_state[k] = False if k in ("logado","primeiro_acesso") else ""
    st.rerun()

# ─────────────────────────────────────────
# SEPARADOR VISUAL DO MENU
# ─────────────────────────────────────────
if menu == "──────────":
    menu = "Dashboard"

# topbar sempre visível
topbar()

# ═══════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════
if menu == "Dashboard":
    st.subheader("📊 Dashboard Operacional")

    df_dr  = carregar_aba("drones")
    df_ca  = carregar_aba("cautelas")
    df_oc  = carregar_aba("ocorrencias")
    df_ag  = carregar_aba("agentes")
    df_vt  = carregar_aba("viaturas")
    df_rel = carregar_aba("relatorios_operacionais")

    tot_drones  = len(df_dr)
    disp        = len(df_dr[df_dr["status"].str.upper()==STATUS_DISPONIVEL]) if not df_dr.empty else 0
    caut        = len(df_dr[df_dr["status"].str.upper()==STATUS_CAUTELADO])  if not df_dr.empty else 0
    manut       = len(df_dr[df_dr["status"].str.upper()==STATUS_MANUTENCAO]) if not df_dr.empty else 0
    ocorrencias = len(df_oc)
    agentes_at  = len(df_ag[df_ag["status"].str.upper()==STATUS_ATIVO]) if not df_ag.empty and "status" in df_ag.columns else len(df_ag)
    viaturas_ok = len(df_vt[df_vt["status"].str.upper()==STATUS_DISPONIVEL]) if not df_vt.empty and "status" in df_vt.columns else len(df_vt)
    missoes     = len(df_rel)

    cols = st.columns(4)
    with cols[0]: card_metrica("Ocorrências",    ocorrencias, "🚨")
    with cols[1]: card_metrica("Agentes Ativos", agentes_at,  "👮")
    with cols[2]: card_metrica("Viaturas OK",    viaturas_ok, "🚗")
    with cols[3]: card_metrica("Missões Drone",  missoes,     "🚁")

    st.markdown("<br>", unsafe_allow_html=True)
    cols2 = st.columns(4)
    with cols2[0]: card_metrica("Drones cadastrados", tot_drones, "🚁")
    with cols2[1]: card_metrica("Disponíveis",         disp,       "✅")
    with cols2[2]: card_metrica("Cautelados",          caut,       "🔒")
    with cols2[3]: card_metrica("Manutenção",          manut,      "🔧")

    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["🚁 Frota de Drones", "📋 Ocorrências", "📈 Produtividade"])

    with tab1:
        if df_dr.empty:
            st.info("Nenhum drone cadastrado.")
        else:
            c1,c2 = st.columns(2)
            with c1:
                st.caption("**Drones por status**")
                st.bar_chart(df_dr["status"].str.upper().value_counts())
            with c2:
                st.caption("**Drones por modelo**")
                st.bar_chart(df_dr["modelo"].str.upper().value_counts())

    with tab2:
        if df_oc.empty:
            st.info("Nenhuma ocorrência registrada.")
        else:
            c1,c2 = st.columns(2)
            with c1:
                st.caption("**Ocorrências por tipo**")
                if "tipo" in df_oc.columns: st.bar_chart(df_oc["tipo"].str.upper().value_counts().head(8))
            with c2:
                st.caption("**Ocorrências por status**")
                if "status" in df_oc.columns: st.bar_chart(df_oc["status"].str.upper().value_counts())

    with tab3:
        if not df_rel.empty:
            c1,c2 = st.columns(2)
            with c1:
                st.caption("**Tempo de voo por piloto (min)**")
                tmp = df_rel.copy(); tmp["tempo_total_voo_min"] = pd.to_numeric(tmp["tempo_total_voo_min"],errors="coerce").fillna(0)
                st.bar_chart(tmp.groupby("piloto")["tempo_total_voo_min"].sum().sort_values(ascending=False).head(10))
            with c2:
                st.caption("**Fotos registradas por piloto**")
                tmp["quantidade_fotos"] = pd.to_numeric(tmp["quantidade_fotos"],errors="coerce").fillna(0)
                st.bar_chart(tmp.groupby("piloto")["quantidade_fotos"].sum().sort_values(ascending=False).head(10))
        else:
            st.info("Sem dados de produtividade.")

# ═══════════════════════════════════════════════════════
#  OCORRÊNCIAS
# ═══════════════════════════════════════════════════════
elif menu == "Ocorrências":
    st.subheader("📋 Ocorrências")
    aba_oc = st.tabs(["Registrar","Consultar"])

    with aba_oc[0]:
        with st.form("form_oc", clear_on_submit=True):
            c1,c2,c3 = st.columns(3)
            with c1: num_oc   = st.text_input("Nº da Ocorrência")
            with c2: data_oc  = st.text_input("Data", value=data_hoje_br())
            with c3: hora_oc  = st.text_input("Hora", value=hora_agora_br())
            tipo_oc  = st.selectbox("Tipo", ["Furto","Roubo","Vandalismo","Perturbação de sossego","Acidente","Fiscalização","Apoio SAMU","Outro"])
            local_oc = st.text_input("Local / Endereço")
            desc_oc  = st.text_area("Descrição")
            c4,c5 = st.columns(2)
            with c4: agente_oc = st.text_input("Agente responsável", value=st.session_state["nome_usuario"])
            with c5: viatura_oc = st.text_input("Viatura (placa)")
            res_oc = st.text_area("Resolução / Encaminhamento")
            if st.form_submit_button("Registrar Ocorrência", use_container_width=True):
                dok,_=validar_data(data_oc); hok,_=validar_hora(hora_oc)
                if not num_oc or not local_oc or not desc_oc: st.warning("Preencha nº, local e descrição.")
                elif not dok or not hok: st.error("Data ou hora inválida.")
                else:
                    df=carregar_aba("ocorrencias"); nid=gerar_id(df)
                    SHEETS["ocorrencias"].append_row([nid,normalizar(num_oc),data_oc,hora_oc,tipo_oc,normalizar(desc_oc),normalizar(local_oc),normalizar(agente_oc),normalizar(viatura_oc),"ABERTA",normalizar(res_oc),st.session_state["nome_usuario"],datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")])
                    registrar_log(st.session_state["nome_usuario"],"OCORRÊNCIA",f"{num_oc}|{tipo_oc}|{local_oc}")
                    limpar_cache(); st.success("✅ Ocorrência registrada com sucesso.")

    with aba_oc[1]:
        df=carregar_aba("ocorrencias")
        if df.empty: st.info("Sem ocorrências.")
        else:
            c1,c2=st.columns(2)
            filtro_status = c1.selectbox("Status",["Todos","ABERTA","EM ANDAMENTO","ENCERRADA"])
            filtro_tipo   = c2.text_input("Tipo ou local contém")
            dff=df.copy()
            if filtro_status!="Todos": dff=dff[dff["status"].str.upper()==filtro_status]
            if filtro_tipo:
                mask=pd.Series(False,index=dff.index)
                for col in ["tipo","local","descricao","agente_responsavel"]:
                    if col in dff.columns: mask|=dff[col].str.contains(filtro_tipo,case=False,na=False)
                dff=dff[mask]
            st.dataframe(dff, use_container_width=True)

# ═══════════════════════════════════════════════════════
#  CENTRAL 153 / DESPACHO / MONITORAMENTO / FISCALIZAÇÃO
# ═══════════════════════════════════════════════════════
elif menu in ("Central 153","Despacho","Monitoramento","Fiscalização"):
    icones = {"Central 153":"📞","Despacho":"📡","Monitoramento":"📷","Fiscalização":"📢"}
    st.subheader(f"{icones.get(menu,'🔧')} {menu}")
    st.info(f"Módulo **{menu}** em desenvolvimento. Esta seção estará disponível em breve.")
    st.markdown("""
    <div class="section-box">
        <p style='margin:0;color:#64748b;font-size:.9rem'>
        💡 Para solicitar este módulo ou relatar necessidades específicas, 
        entre em contato com a administração do sistema.
        </p>
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════
#  DRONEPOL
# ═══════════════════════════════════════════════════════
elif menu == "DRONEPOL":
    st.subheader("🚁 DRONEPOL – Controle Operacional de Drones")
    sub = st.tabs(["Cadastrar Drone","Cautelas","Devoluções","Inspeções de Voo","Relatório Operacional","Consulta"])

    # ── Cadastrar Drone ──
    with sub[0]:
        st.markdown("#### Cadastro de Aeronave Remotamente Pilotada")
        with st.form("form_drone", clear_on_submit=True):
            c1,c2 = st.columns(2)
            with c1:
                matricula = st.text_input("ID / Matrícula da Aeronave")
                modelo    = st.text_input("Modelo")
                fabricante= st.text_input("Fabricante")
            with c2:
                serie   = st.text_input("Nº de Série")
                apelido = st.text_input("Apelido / ID interna")
                status_d= st.selectbox("Status", [STATUS_DISPONIVEL, STATUS_MANUTENCAO, STATUS_BAIXADO])
            obs_d = st.text_area("Observações")
            if st.form_submit_button("Cadastrar Drone ✈️", use_container_width=True):
                if not matricula or not modelo or not serie: st.warning("Preencha matrícula, modelo e nº de série.")
                else:
                    df=carregar_drones()
                    dup = not df.empty and ((df["matricula_aeronave"].str.upper()==matricula.upper()).any() or (df["numero_serie"].str.upper()==serie.upper()).any())
                    if dup: st.error("Drone com esta matrícula ou série já existe.")
                    else:
                        nid=gerar_id(df)
                        SHEETS["drones"].append_row([nid,normalizar(matricula),normalizar(modelo),normalizar(serie),normalizar(fabricante),normalizar(apelido),status_d,data_hoje_br(),normalizar(obs_d)])
                        registrar_log(st.session_state["nome_usuario"],"CADASTRO DRONE",f"{matricula}|{modelo}")
                        limpar_cache(); st.success("✅ Drone cadastrado com sucesso.")

        df_dr_lista = carregar_drones()
        if not df_dr_lista.empty:
            st.markdown("##### Frota cadastrada")
            st.dataframe(df_dr_lista, use_container_width=True)

    # ── Cautelas ──
    with sub[1]:
        st.markdown("#### Cautela de Drone – Responsabilidade de Uso")
        opcoes = drone_opcoes(STATUS_DISPONIVEL)
        if not opcoes: st.info("Nenhum drone disponível para cautela.")
        else:
            with st.form("form_cautela", clear_on_submit=True):
                drone_sel = st.selectbox("Aeronave", opcoes)
                c1,c2 = st.columns(2)
                with c1:
                    dr = st.text_input("Data de Retirada", value=data_hoje_br())
                    hr = st.text_input("Hora de Retirada",value=hora_agora_br())
                with c2:
                    op_nome = st.text_input("Operador responsável", value=st.session_state["nome_usuario"])
                    op_mat  = st.text_input("Matrícula do operador", value=st.session_state["login_usuario"])
                finalidade  = st.text_area("Finalidade da utilização")
                resp_entrega= st.text_input("Responsável pela entrega")
                obs_c       = st.text_area("Observações")
                if st.form_submit_button("Registrar Cautela 🔒", use_container_width=True):
                    dok,dobj=validar_data(dr); hok,hfmt=validar_hora(hr)
                    if not finalidade or not op_nome or not op_mat or not resp_entrega: st.warning("Preencha todos os campos obrigatórios.")
                    elif not dok: st.error("Data inválida.")
                    elif not hok: st.error("Hora inválida.")
                    else:
                        id_d,row=selecionar_drone(drone_sel)
                        df=carregar_aba("cautelas"); nid=gerar_id(df)
                        SHEETS["cautelas"].append_row([nid,int(id_d),str(row["matricula_aeronave"]),str(row["modelo"]),str(row["numero_serie"]),dobj.strftime("%d/%m/%Y"),hfmt,normalizar(finalidade),normalizar(op_nome),normalizar(op_mat),normalizar(resp_entrega),"","","","","ABERTA",normalizar(obs_c),st.session_state["nome_usuario"],datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")])
                        atualizar_status_drone(id_d, STATUS_CAUTELADO)
                        registrar_log(st.session_state["nome_usuario"],"CAUTELA",f"DRONE {row['matricula_aeronave']}")
                        limpar_cache(); st.success("✅ Cautela registrada.")

    # ── Devoluções ──
    with sub[2]:
        st.markdown("#### Devolução de Drone Cautelado")
        df_ca=carregar_aba("cautelas")
        abertas = df_ca[df_ca["status"].str.upper()=="ABERTA"].copy() if not df_ca.empty and "status" in df_ca.columns else pd.DataFrame()
        if abertas.empty: st.info("Nenhuma cautela aberta.")
        else:
            op_dev=(abertas["id"].astype(str)+" - "+abertas["matricula_aeronave"].astype(str)+" - "+abertas["operador_nome"].astype(str)+" - "+abertas["data_retirada"].astype(str)).tolist()
            with st.form("form_dev", clear_on_submit=True):
                sel_dev = st.selectbox("Cautela aberta", op_dev)
                c1,c2=st.columns(2)
                with c1:
                    dd=st.text_input("Data de Devolução", value=data_hoje_br())
                    hd=st.text_input("Hora de Devolução", value=hora_agora_br())
                with c2:
                    resp_dev=st.text_input("Responsável pela devolução", value=st.session_state["nome_usuario"])
                    receb   =st.text_input("Recebido por")
                status_pos=st.selectbox("Status do drone após devolução",[STATUS_DISPONIVEL,STATUS_MANUTENCAO])
                obs_dev=st.text_area("Observações")
                if st.form_submit_button("Registrar Devolução 🔓", use_container_width=True):
                    dok,dobj=validar_data(dd); hok,hfmt=validar_hora(hd)
                    if not resp_dev or not receb: st.warning("Informe responsável e quem recebeu.")
                    elif not dok or not hok: st.error("Data ou hora inválida.")
                    else:
                        id_caut=int(sel_dev.split(" - ")[0])
                        df_ca2=carregar_aba("cautelas")
                        l=df_ca2.index[df_ca2["id"].astype(int)==id_caut][0]+2
                        row_ca=df_ca2[df_ca2["id"].astype(int)==id_caut].iloc[0]
                        SHEETS["cautelas"].update(f"L{l}:Q{l}",[[dobj.strftime("%d/%m/%Y"),hfmt,normalizar(resp_dev),normalizar(receb),"DEVOLVIDA",normalizar(obs_dev)]])
                        atualizar_status_drone(int(row_ca["id_drone"]),status_pos)
                        registrar_log(st.session_state["nome_usuario"],"DEVOLUÇÃO",f"CAUTELA {id_caut}")
                        limpar_cache(); st.success("✅ Devolução registrada.")

    # ── Inspeções ──
    with sub[3]:
        st.markdown("#### Ficha de Inspeção de Voo")
        opcoes=drone_opcoes()
        if not opcoes: st.info("Cadastre ao menos um drone.")
        else:
            PRE=[("pre_update_firmware","Update de firmware"),("pre_cartao_sd","Cartão SD"),("pre_asas","Asas rotativas/fixas"),("pre_cabos","Cabos"),("pre_carregador","Carregador"),("pre_cameras","Câmeras"),("pre_documentos_autorizacoes","Documentos e autorizações"),("pre_epis","EPIs"),("pre_aspecto_geral","Aspecto geral"),("pre_protetor_gimbal","Protetor gimbal"),("pre_calibracao_bussola","Calibração bússola"),("pre_area_decolagem_pouso","Área de decolagem/pouso"),("pre_download_mapas","Download de mapas"),("pre_carga_bateria","Carga da bateria"),("pre_carga_radio","Carga do rádio"),("pre_carga_dispositivo","Carga dispositivo"),("pre_formatacao_sd","Formatação SD"),("pre_analise_risco","Análise de risco"),("pre_plano_voo","Plano de voo"),("pre_config_software","Config. software de voo")]
            DUR=[("dur_carga_bateria","Carga da bateria"),("dur_voltagem_bateria","Voltagem da bateria"),("dur_satelites","Nº de satélites"),("dur_modo_voo","Modo de voo"),("dur_parametros_visuais","Parâmetros visuais"),("dur_telemetria","Telemetria"),("dur_performance","Performance")]
            POS=[("pos_carga_bateria","Carga da bateria"),("pos_carga_radio","Carga do rádio"),("pos_aspecto_geral","Aspecto geral"),("pos_imagens_salvas","Imagens salvas"),("pos_relatorio_operacional","Relatório operacional")]
            VALS=["V","X","N/A"]
            with st.form("form_insp", clear_on_submit=True):
                c1,c2,c3=st.columns(3)
                with c1: data_i=st.text_input("Data",value=data_hoje_br())
                with c2: hora_i=st.text_input("Horário",value=hora_agora_br())
                with c3: ordem_v=st.text_input("Ordem de Voo / OS nº")
                drone_s=st.selectbox("RPA / Aeronave",opcoes)
                solic=st.text_input("Solicitante")
                local_i=st.text_area("Local / Coordenadas")
                c4,c5=st.columns(2)
                with c4:
                    pn=st.text_input("Piloto em comando",value=st.session_state["nome_usuario"])
                    pi=st.text_input("ID do piloto")
                with c5:
                    on=st.text_input("Observador de RPA")
                    oi=st.text_input("ID do observador")
                t1,t2,t3=st.tabs(["Antes do Voo","Durante o Voo","Após o Voo"])
                respostas={}
                with t1:
                    st.caption("Marque V=Verificado · X=Alteração · N/A=Não aplicável")
                    for k,lb in PRE: respostas[k]=st.radio(lb,VALS,index=0,horizontal=True,key=k)
                with t2:
                    for k,lb in DUR: respostas[k]=st.radio(lb,VALS,index=0,horizontal=True,key=k)
                with t3:
                    for k,lb in POS: respostas[k]=st.radio(lb,VALS,index=0,horizontal=True,key=k)
                obs_i=st.text_area("Observações finais")
                if st.form_submit_button("Registrar Inspeção ✅", use_container_width=True):
                    dok,dobj=validar_data(data_i); hok,hfmt=validar_hora(hora_i)
                    if not ordem_v or not solic or not local_i or not pn: st.warning("Preencha ordem de voo, solicitante, local e piloto.")
                    elif not dok or not hok: st.error("Data ou horário inválido.")
                    else:
                        id_d,drow=selecionar_drone(drone_s)
                        df=carregar_aba("inspecoes"); nid=gerar_id(df)
                        row=[nid,normalizar(ordem_v),id_d,drow["matricula_aeronave"],dobj.strftime("%d/%m/%Y"),hfmt,normalizar(solic),normalizar(local_i),normalizar(pn),normalizar(pi),normalizar(on),normalizar(oi)]
                        for k,_ in PRE+DUR+POS: row.append(respostas[k])
                        row+=[normalizar(obs_i),st.session_state["nome_usuario"],datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")]
                        SHEETS["inspecoes"].append_row(row)
                        registrar_log(st.session_state["nome_usuario"],"INSPEÇÃO",f"OS {ordem_v}|{drow['matricula_aeronave']}")
                        limpar_cache(); st.success("✅ Ficha de inspeção registrada.")

    # ── Relatório Operacional ──
    with sub[4]:
        st.markdown("#### Relatório de Avaliação de Risco Operacional")
        opcoes=drone_opcoes()
        if not opcoes: st.info("Cadastre ao menos um drone.")
        else:
            with st.form("form_rel", clear_on_submit=True):
                c1,c2,c3=st.columns(3)
                with c1: num_r=st.text_input("Relatório Operacional nº")
                with c2: data_r=st.text_input("Data",value=data_hoje_br())
                with c3: dr_s=st.selectbox("Nº Aeronave",opcoes)
                st.markdown("**Análise de risco**")
                clima=st.text_input("Clima")
                vento=st.text_input("Vento")
                obst =st.text_area("Obstáculos")
                lp   =st.text_input("Local de pouso/decolagem")
                mit  =st.text_area("Mitigação")
                obs_r=st.text_area("Observações de risco")
                st.markdown("**Registros de voo**")
                qtd_v=st.number_input("Quantidade de voos",min_value=1,max_value=10,value=1,step=1)
                voos=[]
                for i in range(int(qtd_v)):
                    st.markdown(f"*Voo {i+1}*")
                    a1,a2,a3,a4,a5=st.columns(5)
                    with a1: aci=st.text_input("Acionamento",key=f"ac{i}",placeholder="09:10")
                    with a2: cor=st.text_input("Corte",key=f"co{i}",placeholder="09:35")
                    with a3: tv =st.number_input("Tempo (min)",min_value=0,max_value=600,value=0,step=1,key=f"tv{i}")
                    with a4: pv =st.text_input("Piloto",key=f"pv{i}",value=st.session_state["nome_usuario"] if i==0 else "")
                    with a5: ov =st.text_input("Observador",key=f"ov{i}")
                    voos.append({"acionamento":aci,"corte":cor,"tempo_voo_min":tv,"piloto":pv,"observador":ov})
                tempo_total=sum(v["tempo_voo_min"] for v in voos)
                st.markdown("**Histórico e mídias**")
                loc=st.text_input("Localidade")
                hist=st.text_area("Histórico")
                c_a,c_b=st.columns(2)
                with c_a: qf=st.number_input("Qtd fotos",min_value=0,value=0,step=1); fob=st.text_area("Fotos p/ backup")
                with c_b: qv=st.number_input("Qtd vídeos",min_value=0,value=0,step=1); vob=st.text_area("Vídeos p/ backup")
                pf=st.text_input("Assinatura do piloto",value=st.session_state["nome_usuario"])
                of=st.text_input("Assinatura do observador")
                if st.form_submit_button("Registrar Relatório Operacional 🛡️", use_container_width=True):
                    dok,dobj=validar_data(data_r)
                    if not num_r or not clima or not vento or not loc or not hist: st.warning("Preencha relatório nº, clima, vento, localidade e histórico.")
                    elif not dok: st.error("Data inválida.")
                    else:
                        id_d,drow=selecionar_drone(dr_s)
                        df=carregar_aba("relatorios_operacionais"); nid=gerar_id(df)
                        SHEETS["relatorios_operacionais"].append_row([nid,normalizar(num_r),dobj.strftime("%d/%m/%Y"),id_d,drow["matricula_aeronave"],normalizar(clima),normalizar(vento),normalizar(obst),normalizar(lp),normalizar(mit),normalizar(obs_r),normalizar(loc),normalizar(hist),int(qf),int(qv),normalizar(fob),normalizar(vob),int(tempo_total),normalizar(pf),normalizar(of),st.session_state["nome_usuario"],datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")])
                        df_voos=carregar_aba("voos_relatorio")
                        for v in voos:
                            if v["acionamento"] or v["corte"] or v["tempo_voo_min"]>0:
                                SHEETS["voos_relatorio"].append_row([gerar_id(df_voos),nid,normalizar(v["acionamento"]),normalizar(v["corte"]),int(v["tempo_voo_min"]),normalizar(v["piloto"]),normalizar(v["observador"])])
                                df_voos=carregar_aba("voos_relatorio")
                        registrar_log(st.session_state["nome_usuario"],"RELATÓRIO OPERACIONAL",f"REL {num_r}")
                        limpar_cache(); st.success("✅ Relatório operacional registrado.")

    # ── Consulta ──
    with sub[5]:
        st.markdown("#### Consulta / Inventário")
        tc1,tc2,tc3,tc4=st.tabs(["Drones","Cautelas","Inspeções","Relatórios Operacionais"])
        with tc1:
            df=carregar_drones()
            if df.empty: st.info("Sem drones.")
            else:
                f1,f2=st.columns(2)
                fs=f1.selectbox("Status",["Todos",STATUS_DISPONIVEL,STATUS_CAUTELADO,STATUS_MANUTENCAO,STATUS_BAIXADO])
                fm=f2.text_input("Modelo / matrícula contém")
                dff=df.copy()
                if fs!="Todos": dff=dff[dff["status"].str.upper()==fs]
                if fm: dff=dff[dff["modelo"].str.contains(fm,case=False,na=False)|dff["matricula_aeronave"].str.contains(fm,case=False,na=False)]
                st.dataframe(dff, use_container_width=True)
        with tc2:
            df=carregar_aba("cautelas")
            if df.empty: st.info("Sem cautelas.")
            else:
                fs=st.selectbox("Status",["Todos","ABERTA","DEVOLVIDA"])
                dff=df.copy()
                if fs!="Todos": dff=dff[dff["status"].str.upper()==fs]
                st.dataframe(dff, use_container_width=True)
        with tc3:
            df=carregar_aba("inspecoes")
            if df.empty: st.info("Sem inspeções.")
            else:
                t=st.text_input("Buscar por OS, piloto ou drone")
                dff=df.copy()
                if t:
                    mask=pd.Series(False,index=dff.index)
                    for col in ["ordem_voo","matricula_aeronave","piloto_nome","local_coordenadas"]:
                        if col in dff.columns: mask|=dff[col].str.contains(t,case=False,na=False)
                    dff=dff[mask]
                st.dataframe(dff, use_container_width=True)
        with tc4:
            df=carregar_aba("relatorios_operacionais")
            if df.empty: st.info("Sem relatórios.")
            else:
                t=st.text_input("Buscar por nº, localidade ou piloto")
                dff=df.copy()
                if t:
                    mask=pd.Series(False,index=dff.index)
                    for col in ["numero_relatorio","localidade","piloto","historico"]:
                        if col in dff.columns: mask|=dff[col].str.contains(t,case=False,na=False)
                    dff=dff[mask]
                st.dataframe(dff, use_container_width=True)

# ═══════════════════════════════════════════════════════
#  AGENTES
# ═══════════════════════════════════════════════════════
elif menu == "Agentes":
    st.subheader("👮 Gestão de Agentes")
    tabs_ag = st.tabs(["Cadastrar","Consultar"])
    with tabs_ag[0]:
        with st.form("form_ag", clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1:
                mat_ag=st.text_input("Matrícula")
                nome_ag=st.text_input("Nome completo")
                cargo_ag=st.selectbox("Cargo",["GCM","GCM Inspetor","GCM Supervisor","GCM Superintendente","GCM Corregedor"])
            with c2:
                turno_ag=st.selectbox("Turno",["Diurno A","Diurno B","Noturno A","Noturno B","Plantão"])
                status_ag=st.selectbox("Status",[STATUS_ATIVO,STATUS_INATIVO])
                obs_ag=st.text_area("Observações")
            if st.form_submit_button("Cadastrar Agente", use_container_width=True):
                if not mat_ag or not nome_ag: st.warning("Preencha matrícula e nome.")
                else:
                    df=carregar_aba("agentes"); nid=gerar_id(df)
                    SHEETS["agentes"].append_row([nid,normalizar(mat_ag),normalizar(nome_ag),cargo_ag,turno_ag,status_ag,normalizar(obs_ag),data_hoje_br()])
                    registrar_log(st.session_state["nome_usuario"],"CADASTRO AGENTE",f"{mat_ag}|{nome_ag}")
                    limpar_cache(); st.success("✅ Agente cadastrado.")
    with tabs_ag[1]:
        df=carregar_aba("agentes")
        if df.empty: st.info("Nenhum agente cadastrado.")
        else:
            f1,f2=st.columns(2)
            fs=f1.selectbox("Status",["Todos",STATUS_ATIVO,STATUS_INATIVO])
            ft=f2.text_input("Nome ou matrícula contém")
            dff=df.copy()
            if fs!="Todos": dff=dff[dff["status"].str.upper()==fs]
            if ft: dff=dff[dff["nome"].str.contains(ft,case=False,na=False)|dff["matricula"].str.contains(ft,case=False,na=False)]
            st.dataframe(dff, use_container_width=True)

# ═══════════════════════════════════════════════════════
#  VIATURAS
# ═══════════════════════════════════════════════════════
elif menu == "Viaturas":
    st.subheader("🚗 Gestão de Viaturas")
    tabs_vt=st.tabs(["Cadastrar","Consultar"])
    with tabs_vt[0]:
        with st.form("form_vt", clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1:
                placa_v=st.text_input("Placa")
                modelo_v=st.text_input("Modelo")
                ano_v=st.text_input("Ano")
            with c2:
                status_v=st.selectbox("Status",[STATUS_DISPONIVEL,STATUS_MANUTENCAO,"EM USO",STATUS_BAIXADO])
                km_v=st.number_input("KM atual",min_value=0,value=0,step=1)
                obs_v=st.text_area("Observações")
            if st.form_submit_button("Cadastrar Viatura", use_container_width=True):
                if not placa_v or not modelo_v: st.warning("Preencha placa e modelo.")
                else:
                    df=carregar_aba("viaturas"); nid=gerar_id(df)
                    SHEETS["viaturas"].append_row([nid,normalizar(placa_v),normalizar(modelo_v),normalizar(ano_v),status_v,int(km_v),normalizar(obs_v),data_hoje_br()])
                    registrar_log(st.session_state["nome_usuario"],"CADASTRO VIATURA",f"{placa_v}|{modelo_v}")
                    limpar_cache(); st.success("✅ Viatura cadastrada.")
    with tabs_vt[1]:
        df=carregar_aba("viaturas")
        if df.empty: st.info("Nenhuma viatura cadastrada.")
        else: st.dataframe(df, use_container_width=True)

# ═══════════════════════════════════════════════════════
#  EQUIPES / RAS
# ═══════════════════════════════════════════════════════
elif menu in ("Equipes","RAS / Extra"):
    icones={"Equipes":"🛡️","RAS / Extra":"🗓️"}
    st.subheader(f"{icones.get(menu,'📋')} {menu}")
    st.info(f"Módulo **{menu}** em desenvolvimento.")

# ═══════════════════════════════════════════════════════
#  RELATÓRIOS (PDF)
# ═══════════════════════════════════════════════════════
elif menu == "Relatórios":
    st.subheader("🖨️ Emissão de Relatórios")
    tipo_pdf=st.selectbox("Tipo de relatório",[
        "Cautela de Drone","Ficha de Inspeção de Voo","Relatório Operacional",
        "Inventário de Drones","Ocorrências","Log de Auditoria"
    ])

    if tipo_pdf=="Cautela de Drone":
        df=carregar_aba("cautelas")
        if df.empty: st.info("Sem cautelas.")
        else:
            sel=st.selectbox("Selecione",(df["id"].astype(str)+" - "+df["matricula_aeronave"].astype(str)+" - "+df["operador_nome"].astype(str)).tolist())
            id_s=int(sel.split(" - ")[0]); r=df[df["id"].astype(int)==id_s].iloc[0]
            linhas=["## 1. IDENTIFICAÇÃO DA AERONAVE",f"Matrícula: {r.get('matricula_aeronave','')}",f"Modelo: {r.get('modelo','')}",f"Série: {r.get('numero_serie','')}","","## 2. PERÍODO",f"Retirada: {r.get('data_retirada','')} {r.get('hora_retirada','')}  |  Devolução: {r.get('data_devolucao','')} {r.get('hora_devolucao','')}","","## 3. FINALIDADE",r.get("finalidade",""),"","## 4. TERMO DE RESPONSABILIDADE","Declaro que recebi a aeronave em perfeitas condições, assumindo total responsabilidade pelo uso, guarda e devolução.","","## 5. ASSINATURAS",f"Operador: {r.get('operador_nome','')} | Matrícula: {r.get('operador_matricula','')}",f"Entrega: {r.get('responsavel_entrega','')}  |  Devolução: {r.get('responsavel_devolucao','')}  |  Recebido por: {r.get('recebido_por','')}",f"Obs: {r.get('observacoes','')}"]
            btn_pdf("⬇️ Baixar Cautela PDF","CAUTELA DE DRONE",linhas,f"cautela_{id_s}")

    elif tipo_pdf=="Ficha de Inspeção de Voo":
        df=carregar_aba("inspecoes")
        if df.empty: st.info("Sem inspeções.")
        else:
            sel=st.selectbox("Selecione",(df["id"].astype(str)+" - OS "+df["ordem_voo"].astype(str)+" - "+df["matricula_aeronave"].astype(str)).tolist())
            id_s=int(sel.split(" - ")[0]); r=df[df["id"].astype(int)==id_s].iloc[0]
            linhas=["## DADOS",f"Data: {r.get('data','')} {r.get('horario','')}  |  OS: {r.get('ordem_voo','')}",f"RPA: {r.get('matricula_aeronave','')}  |  Solicitante: {r.get('solicitante','')}",f"Local: {r.get('local_coordenadas','')}",f"Piloto: {r.get('piloto_nome','')} ({r.get('piloto_id','')})  |  Observador: {r.get('observador_nome','')} ({r.get('observador_id','')})",
                "","## ANTES DO VOO",f"Firmware:{r.get('pre_update_firmware','')} SD:{r.get('pre_cartao_sd','')} Asas:{r.get('pre_asas','')} Cabos:{r.get('pre_cabos','')} Câm.:{r.get('pre_cameras','')}",f"Docs:{r.get('pre_documentos_autorizacoes','')} EPI:{r.get('pre_epis','')} Gimbal:{r.get('pre_protetor_gimbal','')} Bússola:{r.get('pre_calibracao_bussola','')}",f"Bat:{r.get('pre_carga_bateria','')} Rádio:{r.get('pre_carga_radio','')} Disp.:{r.get('pre_carga_dispositivo','')} Risco:{r.get('pre_analise_risco','')} Plano:{r.get('pre_plano_voo','')}",
                "","## DURANTE O VOO",f"Bat:{r.get('dur_carga_bateria','')} Volt:{r.get('dur_voltagem_bateria','')} Sat:{r.get('dur_satelites','')} Modo:{r.get('dur_modo_voo','')} Telem:{r.get('dur_telemetria','')} Perf:{r.get('dur_performance','')}",
                "","## APÓS O VOO",f"Bat:{r.get('pos_carga_bateria','')} Rádio:{r.get('pos_carga_radio','')} Asp.:{r.get('pos_aspecto_geral','')} Imgs:{r.get('pos_imagens_salvas','')} Rel:{r.get('pos_relatorio_operacional','')}",
                "",f"Obs: {r.get('observacoes','')}","","Assinatura Piloto: ____________________    Assinatura Observador: ____________________"]
            btn_pdf("⬇️ Baixar Inspeção PDF","FICHA DE INSPEÇÃO DE VOO",linhas,f"inspecao_{id_s}")

    elif tipo_pdf=="Relatório Operacional":
        df=carregar_aba("relatorios_operacionais"); df_v=carregar_aba("voos_relatorio")
        if df.empty: st.info("Sem relatórios.")
        else:
            sel=st.selectbox("Selecione",(df["id"].astype(str)+" - Nº "+df["numero_relatorio"].astype(str)+" - "+df["matricula_aeronave"].astype(str)).tolist())
            id_s=int(sel.split(" - ")[0]); r=df[df["id"].astype(int)==id_s].iloc[0]
            linhas=[f"Relatório nº: {r.get('numero_relatorio','')}  |  Data: {r.get('data','')}  |  Aeronave: {r.get('matricula_aeronave','')}","","## ANÁLISE DE RISCO",f"Clima: {r.get('clima','')}  |  Vento: {r.get('vento','')}",f"Obstáculos: {r.get('obstaculos','')}",f"Local pouso/decolagem: {r.get('local_pouso_decolagem','')}",f"Mitigação: {r.get('mitigacao','')}",f"Obs risco: {r.get('observacoes_risco','')}","","## VOOS"]
            if not df_v.empty:
                vv=df_v[df_v["id_relatorio"].astype(str)==str(id_s)]
                for _,v in vv.iterrows(): linhas.append(f"Acion.:{v.get('acionamento','')} Corte:{v.get('corte','')} Tempo:{v.get('tempo_voo_min','')}min Piloto:{v.get('piloto','')} Obs.:{v.get('observador','')}")
            linhas+=[f"Tempo total: {r.get('tempo_total_voo_min','')} min","","## HISTÓRICO",r.get("historico",""),"",f"Fotos:{r.get('quantidade_fotos','')} Vídeos:{r.get('quantidade_videos','')}",f"Backup fotos:{r.get('fotos_backup','')}",f"Backup vídeos:{r.get('videos_backup','')}","",f"Piloto: {r.get('piloto','')}   Observador: {r.get('observador','')}"]
            btn_pdf("⬇️ Baixar Relatório PDF","RELATÓRIO OPERACIONAL",linhas,f"relatorio_{id_s}")

    elif tipo_pdf=="Inventário de Drones":
        df=carregar_drones()
        linhas=["## INVENTÁRIO DE DRONES – SIG-GCM",""]
        if df.empty: linhas.append("Nenhum drone cadastrado.")
        else:
            for _,r in df.iterrows(): linhas.append(f"ID:{r.get('id','')} | Mat:{r.get('matricula_aeronave','')} | Modelo:{r.get('modelo','')} | Série:{r.get('numero_serie','')} | Status:{r.get('status','')}")
        btn_pdf("⬇️ Baixar Inventário PDF","INVENTÁRIO DE DRONES",linhas,"inventario_drones")

    elif tipo_pdf=="Ocorrências":
        df=carregar_aba("ocorrencias")
        linhas=["## RELATÓRIO DE OCORRÊNCIAS",""]
        if df.empty: linhas.append("Nenhuma ocorrência registrada.")
        else:
            for _,r in df.iterrows(): linhas.append(f"{r.get('data','')} {r.get('hora','')} | Nº:{r.get('numero','')} | {r.get('tipo','')} | {r.get('local','')} | Ag.:{r.get('agente_responsavel','')} | Status:{r.get('status','')}")
        btn_pdf("⬇️ Baixar Ocorrências PDF","RELATÓRIO DE OCORRÊNCIAS",linhas,"ocorrencias")

    elif tipo_pdf=="Log de Auditoria":
        df=carregar_aba("log_auditoria")
        linhas=["## LOG DE AUDITORIA",""]
        if df.empty: linhas.append("Nenhum log.")
        else:
            for _,r in df.tail(500).iterrows(): linhas.append(f"{r.get('data','')} {r.get('hora','')} | {r.get('usuario','')} | {r.get('acao','')} | {r.get('detalhes','')}")
        btn_pdf("⬇️ Baixar Log PDF","LOG DE AUDITORIA",linhas,"log_auditoria")

# ═══════════════════════════════════════════════════════
#  USUÁRIOS
# ═══════════════════════════════════════════════════════
elif menu == "Usuários":
    if not is_admin:
        st.warning("Acesso restrito."); st.stop()
    st.subheader("👥 Gestão de Usuários")
    tabs_us=st.tabs(["Cadastrar","Gerenciar"])

    with tabs_us[0]:
        with st.form("form_cad_us", clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1:
                tipo_u=st.selectbox("Tipo",["Piloto/Agente","Gestor"])
                login_u=st.text_input("Login / Matrícula")
                nome_u=st.text_input("Nome")
            with c2:
                mat_u=st.text_input("Matrícula funcional")
                idp_u=st.text_input("ID de piloto / credencial")
                senha_u=st.text_input("Senha inicial",value="1234",type="password")
            if st.form_submit_button("Cadastrar Usuário", use_container_width=True):
                if not login_u or not nome_u: st.warning("Informe login e nome.")
                else:
                    ok=cadastrar_usuario("agente" if tipo_u=="Piloto/Agente" else "gestor",login_u.strip(),nome_u.strip(),mat_u.strip(),idp_u.strip(),senha_u.strip())
                    if ok: st.success("✅ Usuário cadastrado. No primeiro acesso deverá trocar a senha.")
                    else: st.error("Já existe usuário ativo com este login.")

    with tabs_us[1]:
        df_u=carregar_aba("usuarios")
        if df_u.empty: st.info("Nenhum usuário.")
        else:
            ativos=df_u[df_u["status"].str.upper()==STATUS_ATIVO]
            st.dataframe(ativos.drop(columns=["senha"],errors="ignore"), use_container_width=True)
            if not ativos.empty:
                sel_u=(ativos["id"].astype(str)+" - "+ativos["tipo_usuario"]+" - "+ativos["login"]+" - "+ativos["nome"]).tolist()
                uu=st.selectbox("Selecione usuário",sel_u)
                id_u=int(uu.split(" - ")[0])
                c1,c2=st.columns(2)
                with c1:
                    if st.button("🔑 Resetar senha para 1234", use_container_width=True):
                        resetar_senha(id_u); st.success("Senha resetada."); time_mod.sleep(1); st.rerun()
                with c2:
                    if st.button("🚫 Inativar usuário", type="primary", use_container_width=True):
                        inativar_usuario(id_u); st.success("Usuário inativado."); time_mod.sleep(1); st.rerun()

# ═══════════════════════════════════════════════════════
#  AUDITORIA
# ═══════════════════════════════════════════════════════
elif menu == "Auditoria":
    st.subheader("🔒 Log de Auditoria")
    df=carregar_aba("log_auditoria")
    if df.empty: st.info("Nenhum log registrado.")
    else:
        c1,c2=st.columns(2)
        fu=c1.text_input("Filtrar por usuário")
        fa=c2.text_input("Filtrar por ação")
        dff=df.copy()
        if fu: dff=dff[dff["usuario"].str.contains(fu,case=False,na=False)]
        if fa: dff=dff[dff["acao"].str.contains(fa,case=False,na=False)]
        st.dataframe(dff.sort_index(ascending=False), use_container_width=True)
        btn_pdf("⬇️ Exportar Log PDF","LOG DE AUDITORIA",[f"{r.get('data','')} {r.get('hora','')} | {r.get('usuario','')} | {r.get('acao','')} | {r.get('detalhes','')}" for _,r in dff.tail(500).iterrows()],"log_auditoria")

# ═══════════════════════════════════════════════════════
#  MINHA CONTA
# ═══════════════════════════════════════════════════════
elif menu == "Minha Conta":
    st.subheader("🔐 Minha Conta")
    c1,_,_=st.columns([1.2,1,1])
    with c1:
        st.markdown(f"""
        <div class="section-box">
            <b>Usuário:</b> {st.session_state["nome_usuario"]}<br>
            <b>Login:</b> {st.session_state["login_usuario"]}<br>
            <b>Perfil:</b> {st.session_state["tipo_usuario"].upper()}
        </div>""", unsafe_allow_html=True)
        with st.form("form_conta"):
            sa=st.text_input("Senha atual",type="password")
            n1=st.text_input("Nova senha",type="password")
            n2=st.text_input("Confirmar nova senha",type="password")
            if st.form_submit_button("Alterar senha", use_container_width=True):
                if not validar_senha(st.session_state["usuario_id"],sa): st.error("Senha atual incorreta.")
                elif n1!=n2: st.error("Senhas não coincidem.")
                elif len(n1)<4: st.error("Mínimo 4 caracteres.")
                else:
                    alterar_senha(st.session_state["usuario_id"],n1)
                    st.success("✅ Senha alterada com sucesso.")

# ─────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────
footer()
