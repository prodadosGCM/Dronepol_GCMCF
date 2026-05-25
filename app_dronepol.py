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
# CONFIGURAÇÃO DE SESSÃO (Evita erros de Inicialização)
# ─────────────────────────────────────────
if "menu_expandido" not in st.session_state:
    st.session_state["menu_expandido"] = True
if "menu_selecionado" not in st.session_state:
    st.session_state["menu_selecionado"] = "Dashboard"
if "logado" not in st.session_state:
    st.session_state["logado"] = False

# ─────────────────────────────────────────
# TEMA / CSS DINÂMICO E RESPONSIVO (Slim Sidebar Control)
# ─────────────────────────────────────────
# Definimos a largura da barra lateral dependendo se está expandida ou recolhida apenas com os ícones
largura_sidebar = "260px" if st.session_state["menu_expandido"] else "70px"

st.markdown(f"""
<style>
:root {{
    --accent:      #eab308;
    --accent-fg:   #0f172a;
    --sidebar-bg:  #0f172a;
    --sidebar-fg:  #e2e8f0;
    --surface:     #ffffff;
    --muted:       #64748b;
    --border:      #e2e8f0;
    --success:     #22c55e;
    --destructive: #ef4444;
}}

/* Esconde o botão específico do header solicitado */
button[data-testid="stBaseButton-headerNoPadding"] {{
    display: none !important;
}}            

header[data-testid="stHeader"] {{ display: none !important; }}

/* Remove o botão nativo de colapsar do Streamlit */
[data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
[data-testid="stSidebarUserContent"] {{ padding-top: 1rem !important; }}

/* CONTROLO RESPONSIVO E DINÂMICO DA LARGURA DA SIDEBAR */
[data-testid="stSidebar"] {{
    background: var(--sidebar-bg) !important;
    border-right: 1px solid #1e293b;
    min-width: {largura_sidebar} !important;
    max-width: {largura_sidebar} !important;
    width: {largura_sidebar} !important;
    transition: width 0.3s ease, min-width 0.3s ease, max-width 0.3s ease !important;
}}

/* Ajusta a área do conteúdo principal para acompanhar a redução da barra lateral */
[data-testid="stSidebar"] + section {{
    margin-left: 0px !important;
}}

[data-testid="stSidebar"] * {{ color: var(--sidebar-fg) !important; }}

/* Elementos visuais da Sidebar */
.brand-bar {{
    display: flex; align-items: center; gap: 10px;
    padding: 14px 16px 10px; border-bottom: 1px solid #1e293b; margin-bottom: 4px;
}}
.brand-icon {{
    width: 36px; height: 36px; border-radius: 6px;
    background: linear-gradient(135deg, var(--accent), #ca8a04);
    display: flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 18px; color: var(--accent-fg); flex-shrink: 0;
}}
.brand-text {{ line-height: 1.25; }}
.brand-text .name  {{ font-size: 0.8rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--accent) !important; }}
.brand-text .sub   {{ font-size: 0.65rem; color: #94a3b8 !important; }}

/* Força centralização perfeita dos ícones quando recolhido em ecrãs móveis */
.stButton > button {{
    border-radius: 8px; font-weight: 600; font-size: .85rem;
    display: flex; align-items: center; justify-content: {"flex-start" if st.session_state["menu_expandido"] else "center"} !important;
}}
.stButton > button[kind="primary"] {{ background: var(--accent) !important; color: var(--accent-fg) !important; border: none !important; }}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{ border-bottom: 2px solid var(--accent) !important; color: #0f172a !important; font-weight: 700 !important; }}

/* Topbar responsiva */
.topbar {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 20px; background: var(--surface); border-bottom: 1px solid var(--border); margin-bottom: 18px;
    flex-wrap: wrap; gap: 8px;
}}
.topbar-left  {{ font-size: .85rem; font-weight: 600; color: #0f172a; }}
.topbar-right {{ font-size: .75rem; color: var(--muted); font-family: monospace; }}

/* Media Query para ecrãs muito pequenos (Telemóveis) */
@media (max-width: 768px) {{
    [data-testid="stSidebar"] {{
        position: fixed !important;
        z-index: 999991 !important;
    }}
    .topbar {{
        flex-direction: column;
        align-items: flex-start;
    }}
}}

::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 99px; }}
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
# UTILITÁRIOS & GOOGLE SHEETS
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

@st.cache_resource
def conectar_planilha():
    try:
        creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets"])
        client = gspread.authorize(creds)
        key = st.secrets.get("spreadsheet_key","")
        if not key: st.stop()
        return client.open_by_key(key)
    except: st.stop()

@st.cache_resource
def iniciar_todas_abas():
    p = conectar_planilha()
    dicionario_abas = {}
    for nome in ABAS:
        try: dicionario_abas[nome] = p.worksheet(nome)
        except:
            aba = p.add_worksheet(title=nome, rows=3000, cols=max(len(ABAS[nome]),10))
            aba.append_row(ABAS[nome])
            dicionario_abas[nome] = aba
    return dicionario_abas

SHEETS = iniciar_todas_abas()

@st.cache_data(ttl=60)
def carregar_aba(nome):
    df = pd.DataFrame(SHEETS[nome].get_all_records())
    if not df.empty: df.columns = df.columns.str.strip().str.lower()
    return df

def buscar_usuario(tipo, login):
    df = carregar_aba("usuarios")
    if df.empty: return None
    m = (df["tipo_usuario"].str.lower()==tipo.lower())&(df["login"].str.lower()==login.strip().lower())&((df["status"].str.upper()=="ATIVO")|(df["status"]==""))
    return None if df[m].empty else df[m].iloc[0]

def login_usuario(tipo, login, senha):
    u = buscar_usuario(tipo, login)
    if u is not None and check_hashes(senha, u["senha"]):
        return {"sucesso":True,"id":int(u["id"]),"nome":str(u["nome"]),"login":str(u["login"]),"primeiro_acesso":bool(int(u.get("primeiro_acesso",0) or 0))}
    return {"sucesso":False}

# ═══════════════════════════════════════════════════════
#  LOGIN
# ═══════════════════════════════════════════════════════
if not st.session_state["logado"]:
    c1,c2,c3 = st.columns([1,1.2,1])
    with c2:
        st.markdown("<div style='text-align:center;padding:24px 0 8px'><div style='font-size:3rem'>🚔</div><h2 style='margin:4px 0 2px;color:#0f172a;font-size:1.5rem'>SIG-GCM</h2></div>", unsafe_allow_html=True)
        with st.form("login"):
            perfil = st.radio("Entrar como:", list(TIPOS_USUARIO.keys()), horizontal=True)
            login_input = st.text_input("Usuário / Matrícula")
            senha_input = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar →", use_container_width=True):
                res = login_usuario(TIPOS_USUARIO[perfil], login_input.strip(), senha_input)
                if res["sucesso"]:
                    st.session_state.update({"logado":True,"tipo_usuario":TIPOS_USUARIO[perfil],"usuario_id":res["id"],"nome_usuario":res["nome"],"login_usuario":res["login"],"primeiro_acesso":res["primeiro_acesso"]})
                    st.rerun()
                else: st.error("Usuário ou senha inválidos.")
    st.stop()

# ═══════════════════════════════════════════════════════
#  SIDEBAR RESPONSIVA (SLIM / EXPANDIDA)
# ═══════════════════════════════════════════════════════
perfil = st.session_state["tipo_usuario"]
is_admin = perfil in ("admin","gestor")

if is_admin:
    opcoes_menu = [
        {"label": "Dashboard", "icon": "📊"}, {"label": "Ocorrências", "icon": "🚨"},
        {"label": "Central 153", "icon": "📞"}, {"label": "Despacho", "icon": "📡"},
        {"label": "Monitoramento", "icon": "📷"}, {"label": "DRONEPOL", "icon": "🎮"},
        {"label": "Fiscalização", "icon": "📢"}, {"label": "Agentes", "icon": "👥"},
        {"label": "Viaturas", "icon": "🚗"}, {"label": "Minha Conta", "icon": "👤"},
        {"label": "Sair", "icon": "🚪"}
    ]
else:
    opcoes_menu = [
        {"label": "Dashboard", "icon": "📊"}, {"label": "DRONEPOL", "icon": "🎮"},
        {"label": "Minha Conta", "icon": "👤"}, {"label": "Sair", "icon": "🚪"}
    ]

with st.sidebar:
    # Ajusta o cabeçalho dinamicamente de acordo com a largura
    if st.session_state["menu_expandido"]:
        st.markdown('<div class="brand-bar"><div class="brand-icon">G</div><div class="brand-text"><div class="name">SIG-GCM</div><div class="sub">Cabo Frio / RJ</div></div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="brand-bar" style="justify-content: center; padding: 14px 0;"><div class="brand-icon">G</div></div>', unsafe_allow_html=True)

    # Botão Responsivo de Gatilho
    texto_botao = "◀ Recolher Menu" if st.session_state["menu_expandido"] else "▶"
    if st.button(texto_botao, key="toggle_sidebar_custom", use_container_width=True):
        st.session_state["menu_expandido"] = not st.session_state["menu_expandido"]
        st.rerun()
        
    st.markdown("---")
    
    # Renderização fluida dos botões (Centraliza ícones quando colapsado)
    for item in opcoes_menu:
        rotulo_visual = f"{item['icon']}   {item['label']}" if st.session_state["menu_expandido"] else item["icon"]
        
        if st.button(
            rotulo_visual, 
            key=f"btn_{item['label']}", 
            use_container_width=True,
            type="primary" if st.session_state["menu_selecionado"] == item["label"] else "secondary"
        ):
            st.session_state["menu_selecionado"] = item["label"]
            st.rerun()

    menu = st.session_state["menu_selecionado"]

    if st.session_state["menu_expandido"]:
        st.markdown(f"<div style='padding:12px 12px 8px; border-top:1px solid #1e293b; margin-top:16px'><div style='font-size:.75rem; color:#94a3b8'>Conectado como</div><div style='font-size:.85rem; font-weight:700; color:#e2e8f0; margin-top:2px'>{st.session_state['nome_usuario']}</div></div>", unsafe_allow_html=True)

if menu == "Sair":
    for k in ["logado","usuario_id","tipo_usuario","nome_usuario","login_usuario","primeiro_acesso", "menu_selecionado"]:
        if k in st.session_state: st.session_state[k] = False if k in ("logado","primeiro_acesso") else ""
    st.rerun()

topbar()

# ═══════════════════════════════════════════════════════
#  CONTEÚDO DO MÓDULO CORRESPONDENTE (DASHBOARD / OCORRÊNCIAS)
# ═══════════════════════════════════════════════════════
if menu == "Dashboard":
    st.subheader("📊 Dashboard Operacional")
    df_dr  = carregar_aba("drones")
    df_oc  = carregar_aba("ocorrencias")
    df_ag  = carregar_aba("agentes")
    df_vt  = carregar_aba("viaturas")
    df_rel = carregar_aba("relatorios_operacionais")

    cols = st.columns([1,1,1,1])
    with cols[0]: card_metrica("Ocorrências", len(df_oc), "🚨")
    with cols[1]: card_metrica("Agentes Ativos", len(df_ag), "👮")
    with cols[2]: card_metrica("Viaturas OK", len(df_vt), "🚗")
    with cols[3]: card_metrica("Missões Drone", len(df_rel), "🚁")

elif menu == "Ocorrências":
    st.subheader("📋 Ocorrências")
    aba_oc = st.tabs(["Registrar","Consultar"])
    with aba_oc[0]:
        with st.form("form_oc", clear_on_submit=True):
            st.text_input("Nº da Ocorrência")
            st.text_input("Local / Endereço")
            st.text_area("Descrição")
            st.form_submit_button("Registrar Ocorrência", use_container_width=True)
    with aba_oc[1]:
        df=carregar_aba("ocorrencias")
        st.dataframe(df, use_container_width=True)

elif menu in ("Central 153","Despacho","Monitoramento","Fiscalização","DRONEPOL","Agentes","Viaturas","Minha Conta"):
    st.subheader(f"🔧 Módulo {menu}")
    st.info(f"O módulo {menu} está adaptado para o novo layout responsivo.")