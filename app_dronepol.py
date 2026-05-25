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
# TEMA / CSS  (Otimizado e leve)
# ─────────────────────────────────────────
st.markdown("""
<style>
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

header[data-testid="stHeader"] { display: none !important; }

[data-testid="stSidebar"] {
    background: var(--sidebar-bg) !important;
    border-right: 1px solid #1e293b;
}
[data-testid="stSidebar"] * { color: var(--sidebar-fg) !important; }
[data-testid="stSidebar"] .nav-link-selected { background: var(--accent) !important; color: var(--accent-fg) !important; }

.brand-bar {
    display: flex; align-items: center; gap: 10px;
    padding: 14px 16px 10px; border-bottom: 1px solid #1e293b; margin-bottom: 4px;
}
.brand-icon {
    width: 36px; height: 36px; border-radius: 6px;
    background: linear-gradient(135deg, var(--accent), #ca8a04);
    display: flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 18px; color: var(--accent-fg); flex-shrink: 0;
}
.brand-text { line-height: 1.25; }
.brand-text .name  { font-size: 0.8rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--accent) !important; }
.brand-text .sub   { font-size: 0.65rem; color: #94a3b8 !important; }

.topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 20px; background: var(--surface); border-bottom: 1px solid var(--border); margin-bottom: 18px;
}
.topbar-left  { font-size: .85rem; font-weight: 600; color: #0f172a; }
.topbar-right { font-size: .75rem; color: var(--muted); font-family: monospace; }

.metric-card {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    padding: 18px 20px; border-radius: 14px; color: white;
    box-shadow: 0 4px 16px rgba(0,0,0,.18); border: 1px solid rgba(255,255,255,.07); min-height: 108px;
}
.metric-card .mc-label { margin: 0; font-size: .82rem; color: #94a3b8; font-weight: 600; }
.metric-card .mc-value { margin: 8px 0 0; font-size: 2.1rem; font-weight: 900; color: #ffffff; line-height: 1; }
.metric-card .mc-icon  { font-size: 1.4rem; float: right; opacity: .5; }

.badge { display: inline-block; padding: 2px 10px; border-radius: 99px; font-size: .72rem; font-weight: 700; letter-spacing: .04em; }
.badge-green  { background:#dcfce7; color:#15803d; }
.badge-yellow { background:#fef9c3; color:#854d0e; }
.badge-red    { background:#fee2e2; color:#991b1b; }
.badge-gray   { background:#f1f5f9; color:#475569; }
.badge-blue   { background:#dbeafe; color:#1d4ed8; }

.section-box { background: #f8fafc; border: 1px solid var(--border); border-radius: 14px; padding: 18px; margin-bottom: 14px; }

.footer-bar {
    margin-top: 32px; padding: 10px 20px; background: var(--surface); border-top: 1px solid var(--border);
    display: flex; justify-content: space-between; font-size: .7rem; color: var(--muted); font-family: monospace;
}
.footer-status { display: flex; align-items: center; gap: 6px; }
.dot-green { width: 8px; height: 8px; border-radius: 50%; background: var(--success); display: inline-block; }

div[data-testid="stForm"] { background: #f8fafc; border: 1px solid var(--border); border-radius: 14px; padding: 20px !important; }
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
.stButton > button { border-radius: 8px; font-weight: 600; font-size: .85rem; }
.stButton > button[kind="primary"] { background: var(--accent) !important; color: var(--accent-fg) !important; border: none !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { border-bottom: 2px solid var(--accent) !important; color: #0f172a !important; font-weight: 700 !important; }

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 99px; }

[data-testid="stSidebarCollapseButton"] button, [data-testid="collapsedControl"] {
    background: #1e293b !important; color: #94a3b8 !important; border: 1px solid #334155 !important; border-radius: 0 8px 8px 0 !important;
}
[data-testid="stSidebarCollapseButton"] button:hover, [data-testid="collapsedControl"]:hover { background: #334155 !important; color: #eab308 !important; }
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
    "drones": ["id","matricula_aeronave","modelo","numero_serie","fabricante","apelido","status","data_cadastro","observacoes"],
    "usuarios": ["id","tipo_usuario","login","nome","matricula","id_piloto","senha","primeiro_acesso","status"],
    "cautelas": ["id","id_drone","matricula_aeronave","modelo","numero_serie","data_retirada","hora_retirada","finalidade","operador_nome","operador_matricula","responsavel_entrega","data_devolucao","hora_devolucao","responsavel_devolucao","recebido_por","status","observacoes","usuario_registro","data_registro"],
    "inspecoes": ["id","ordem_voo","id_drone","matricula_aeronave","data","horario","solicitante","local_coordenadas","piloto_nome","piloto_id","observador_nome","observador_id","pre_update_firmware","pre_cartao_sd","pre_asas","pre_cabos","pre_carregador","pre_cameras","pre_documentos_autorizacoes","pre_epis","pre_aspecto_geral","pre_protetor_gimbal","pre_calibracao_bussola","pre_area_decolagem_pouso","pre_download_mapas","pre_carga_bateria","pre_carga_radio","pre_carga_dispositivo","pre_formatacao_sd","pre_analise_risco","pre_plano_voo","pre_config_software","dur_carga_bateria","dur_voltagem_bateria","dur_satelites","dur_modo_voo","dur_parametros_visuais","dur_telemetria","dur_performance","pos_carga_bateria","pos_carga_radio","pos_aspecto_geral","pos_imagens_salvas","pos_relatorio_operacional","observacoes","usuario_registro","data_registro"],
    "relatorios_operacionais": ["id","numero_relatorio","data","id_drone","matricula_aeronave","clima","vento","obstaculos","local_pouso_decolagem","mitigacao","observacoes_risco","localidade","historico","quantidade_fotos","quantidade_videos","fotos_backup","videos_backup","tempo_total_voo_min","piloto","observador","usuario_registro","data_registro"],
    "voos_relatorio": ["id","id_relatorio","acionamento","corte","tempo_voo_min","piloto","observador"],
    "ocorrencias": ["id","numero","data","hora","tipo","descricao","local","agente_responsavel","viatura","status","resolucao","usuario_registro","data_registro"],
    "agentes": ["id","matricula","nome","cargo","turno","status","observacoes","data_cadastro"],
    "viaturas": ["id","placa","modelo","ano","status","km_atual","observacoes","data_cadastro"],
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
# GOOGLE SHEETS OTIMIZADO (Cache de Recursos)
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

# Cacheado para evitar bater na API em todo rerun de clique
@st.cache_resource
def iniciar_todas_abas():
    p = conectar_planilha()
    dicionario_abas = {}
    for nome in ABAS:
        try:
            dicionario_abas[nome] = p.worksheet(nome)
        except:
            aba = p.add_worksheet(title=nome, rows=3000, cols=max(len(ABAS[nome]),10))
            aba.append_row(ABAS[nome])
            dicionario_abas[nome] = aba
    return dicionario_abas

# Carrega a estrutura de conexões de abas em memória global cacheada
SHEETS = iniciar_todas_abas()

@st.cache_data(ttl=60)
def carregar_aba(nome):
    df = pd.DataFrame(SHEETS[nome].get_all_records())
    if not df.empty: df.columns = df.columns.str.strip().str.lower()
    return df

def limpar_cache(): 
    carregar_aba.clear()

def registrar_log(usuario, acao, detalhes=""):
    d, h = agora_str()
    SHEETS["log_auditoria"].append_row([d, h, str(usuario).upper(), str(acao).upper(), str(detalhes).upper()])
    limpar_cache()

def bootstrap_admin():
    df = carregar_aba("usuarios")
    if df.empty:
        SHEETS["usuarios"].append_row([1,"admin","admin","ADMINISTRADOR","","",make_hashes("admin123"),1,STATUS_ATIVO])
        limpar_cache()
        return
    existe = not df[(df["tipo_usuario"].str.lower()=="admin")&(df["login"].str.lower()=="admin")&(df["status"].str.upper()==STATUS_ATIVO)].empty
    if not existe:
        ids = pd.to_numeric(df.get("id",pd.Series(dtype=float)),errors="coerce").dropna()
        nid = int(ids.max())+1 if not ids.empty else 1
        SHEETS["usuarios"].append_row([nid,"admin","admin","ADMINISTRADOR","","",make_hashes("admin123"),1,STATUS_ATIVO])
        limpar_cache()

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
        <span class="topbar-left">&#x1F694; SIG-GCM &nbsp;&middot;&nbsp; Cabo Frio / RJ</span>
        <span class="topbar-right">{nome} &nbsp;&middot;&nbsp; {perfil_label} &nbsp;&middot;&nbsp; {d} {h}</span>
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
                st.success("Senha updated!"); time_mod.sleep(1); st.rerun()
    st.stop()


# ═══════════════════════════════════════════════════════
#  CONTROLE DO ESTADO DO MENU (MINI / EXPANDIDO)
# ═══════════════════════════════════════════════════════
if "menu_expandido" not in st.session_state:
    st.session_state["menu_expandido"] = True  # Começa aberto

# CSS Injetado para criar a transição suave e o comportamento Slim
st.markdown("""
<style>
/* Remove o botão padrão de colapsar do Streamlit para não chocar com o nosso */
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* Ajusta o padding interno da sidebar do Streamlit */
[data-testid="stSidebarUserContent"] { padding-top: 1rem !important; }

/* Estilização dos itens do menu customizado */
.menu-container { display: flex; flex-direction: column; gap: 4px; width: 100%; }
.menu-item {
    display: flex; align-items: center; padding: 10px 12px;
    border-radius: 8px; color: #e2e8f0 !important;
    text-decoration: none; background: transparent; border: none;
    width: 100%; text-align: left; cursor: pointer; transition: all 0.2s ease;
}
.menu-item:hover { background-color: #1e293b; color: #eab308 !important; }
.menu-item-active { background-color: #eab308 !important; color: #0f172a !important; font-weight: 700; }
.menu-icon { font-size: 18px; min-width: 30px; display: inline-block; text-align: center; }
.menu-text { font-size: 14px; white-space: nowrap; transition: opacity 0.2s; }

/* Botão de alternar (Hambúrguer / Seta) */
.toggle-btn {
    background: #1e293b; color: #94a3b8; border: 1px solid #334155;
    padding: 6px; border-radius: 6px; cursor: pointer; margin-bottom: 15px;
    width: 100%; text-align: center; font-weight: bold;
}
.toggle-btn:hover { color: #eab308; background: #334155; }
</style>
""", unsafe_allow_html=True)

# Define as opções de menu com base no perfil
perfil = st.session_state["tipo_usuario"]
is_admin = perfil in ("admin", "gestor")

if is_admin:
    opcoes_menu = [
        {"label": "Dashboard", "icon": "📊"},
        {"label": "Ocorrências", "icon": "🚨"},
        {"label": "Central 153", "icon": "📞"},
        {"label": "Despacho", "icon": "📡"},
        {"label": "Monitoramento", "icon": "📷"},
        {"label": "DRONEPOL", "icon": "🎮"},
        {"label": "Fiscalização", "icon": "📢"},
        {"label": "Agentes", "icon": "👥"},
        {"label": "Viaturas", "icon": "🚗"},
        {"label": "Minha Conta", "icon": "👤"},
        {"label": "Sair", "icon": "🚪"}
    ]
else:
    opcoes_menu = [
        {"label": "Dashboard", "icon": "📊"},
        {"label": "DRONEPOL", "icon": "🎮"},
        {"label": "Minha Conta", "icon": "👤"},
        {"label": "Sair", "icon": "🚪"}
    ]

# Se não houver menu selecionado na sessão, define o padrão
if "menu_selecionado" not in st.session_state:
    st.session_state["menu_selecionado"] = "Dashboard"

# Renderização do Menu Lateral Customizado
with st.sidebar:
    # Botão de gatilho para expandir/recolher
    texto_botao = "◀ Recolher" if st.session_state["menu_expandido"] else "▶"
    if st.button(texto_botao, key="toggle_sidebar_custom", use_container_width=True):
        st.session_state["menu_expandido"] = not st.session_state["menu_expandido"]
        st.rerun()
        
    st.markdown("---")
    
    # Renderiza os itens
    for item in opcoes_menu:
        # Se estiver expandido, mostra Ícone + Texto. Se estiver colapsado, mostra apenas o Ícone.
        if st.session_state["menu_expandido"]:
            html_item = f"""
            <div class="menu-icon">{item['icon']}</div>
            <div class="menu-text">{item['label']}</div>
            """
        else:
            # CORREÇÃO AQUI: Alternância de aspas simples e duplas para evitar erro de sintaxe
            html_item = f'<div class="menu-icon" title="{item["label"]}">{item["icon"]}</div>'
            
        # Cria o botão com base no estado atual
        if st.button(item["label"] if st.session_state["menu_expandido"] else item["icon"], 
                     key=f"btn_{item['label']}", 
                     use_container_width=True,
                     type="primary" if st.session_state["menu_selecionado"] == item["label"] else "secondary"):
            st.session_state["menu_selecionado"] = item["label"]
            st.rerun()

    # Redireciona a variável antiga 'menu' para a nova estrutura baseada em estado
    menu = st.session_state["menu_selecionado"]

    if st.session_state["menu_expandido"]:
        st.markdown(f"""
        <div style='padding:12px 12px 8px; border-top:1px solid #1e293b; margin-top:16px'>
            <div style='font-size:.75rem; color:#94a3b8'>Conectado como</div>
            <div style='font-size:.85rem; font-weight:700; color:#e2e8f0; margin-top:2px'>{st.session_state["nome_usuario"]}</div>
            <div style='font-size:.68rem; color:#64748b; font-family:monospace'>{perfil.upper()}</div>
        </div>""", unsafe_allow_html=True)

# Executa a ação de logout caso o botão Sair seja pressionado
if menu == "Sair":
    for k in ["logado","usuario_id","tipo_usuario","nome_usuario","login_usuario","primeiro_acesso", "menu_selecionado"]:
        if k in st.session_state:
            st.session_state[k] = False if k in ("logado","primeiro_acesso") else ""
    st.rerun()

topbar()

# ═══════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════
if menu == "Dashboard":
    st.subheader("📊 Dashboard Operacional")

    df_dr  = carregar_aba("drones")
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
        if df_dr.empty: st.info("Nenhum drone cadastrado.")
        else:
            c1,c2 = st.columns(2)
            with c1:
                st.caption("**Drones por status**")
                st.bar_chart(df_dr["status"].str.upper().value_counts())
            with c2:
                st.caption("**Drones por modelo**")
                st.bar_chart(df_dr["modelo"].str.upper().value_counts())

    with tab2:
        if df_oc.empty: st.info("Nenhuma ocorrência registrada.")
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
                tmp = df_rel.copy()
                tmp["tempo_total_voo_min"] = pd.to_numeric(tmp["tempo_total_voo_min"], errors="coerce").fillna(0)
                st.bar_chart(tmp.groupby("piloto")["tempo_total_voo_min"].sum().sort_values(ascending=False).head(10))
            with c2:
                st.caption("**Fotos registradas por piloto**")
                tmp["quantidade_fotos"] = pd.to_numeric(tmp["quantidade_fotos"], errors="coerce").fillna(0)
                st.bar_chart(tmp.groupby("piloto")["quantidade_fotos"].sum().sort_values(ascending=False).head(10))
        else:
            st.info("Sem dados de produtividade.")

# ═══════════════════════════════════════════════════════
#  OCORRÊNCIAS (Correção da Busca Incompleta feita aqui)
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
                    st.success("✅ Ocorrência registrada com sucesso.")

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
                mask = pd.Series(False, index=dff.index)
                for col in ["tipo","local","descricao","agente_responsavel"]:
                    if col in dff.columns:
                        mask |= dff[col].astype(str).str.contains(filtro_tipo, case=False, na=False)
                dff = dff[mask]
            st.dataframe(dff, use_container_width=True)

# ═══════════════════════════════════════════════════════
#  MÓDULOS ADICIONAIS
# ═══════════════════════════════════════════════════════
elif menu in ("Central 153","Despacho","Monitoramento","Fiscalização","DRONEPOL","Agentes","Viaturas","Minha Conta"):
    st.subheader(f"🔧 Módulo {menu}")
    st.info(f"O módulo **{menu}** está operacional ou em adaptação de dados.")
    st.markdown("""
    <div class="section-box">
        <p style='margin:0;color:#64748b;font-size:.9rem'>
            💡 Use as conexões e formulários padrões do sistema para atualizar esta seção.
        </p>
    </div>""", unsafe_allow_html=True)