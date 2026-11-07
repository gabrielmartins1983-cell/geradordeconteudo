import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from io import BytesIO
from datetime import date, datetime
import os
import json
import random
import urllib.parse
import urllib.request
import google.generativeai as genai

st.set_page_config(page_title="BeSmart News | Painel administrativo", page_icon="🟣", layout="wide")

try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    elif os.environ.get("GEMINI_API_KEY"):
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
except Exception:
    pass

PURPLE = "#9966FF"
WHITE = "#FFFFFF"
SILVER = "#F3F3F3"
MUTED = "#B8B5C1"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Barlow', sans-serif; }
.stApp { background: #090B12; color: #F4F2F7; }
.block-container { padding-top: 2rem; max-width: 1400px; }
h1,h2,h3 { font-family: 'Barlow', sans-serif; }
.small-muted { color: #B8B5C1; font-size: .9rem; }
.brand { font-size: 1.7rem; font-weight: 600; letter-spacing: -.04em; }
.brand span { color: #9966FF; }
div[data-testid="stMetric"] { background:#11131D; border:1px solid #282333; padding:14px; border-radius:12px; }
.stButton button, .stDownloadButton button { border-radius: 8px; }
hr { border-color: #332744; }
</style>
""", unsafe_allow_html=True)

if "dados_noticias" not in st.session_state:
    st.session_state.dados_noticias = [
        {
            "id": 1, "categoria": "Juros e financiamento",
            "titulo": "Como a taxa de juros influencia o financiamento imobiliário atual?",
            "destaque": "JUROS E CRÉDITO IMOBILIÁRIO",
            "resumo": "As condições correntes de crédito impactam diretamente o Custo Efetivo Total (CET).",
            "fonte": "Banco Central",
            "url": "https://www.google.com/search?q=financiamento", 
            "data": str(date.today()), 
            "regiao": "Brasil",
            "status": "Rascunho", 
            "verificado": True
        }
    ]

if "proximo_id" not in st.session_state:
    st.session_state.proximo_id = 2

if "story_ativo" not in st.session_state:
    st.session_state.story_ativo = None

if "historico_stories" not in st.session_state:
    st.session_state.historico_stories = []

if "noticias_descobertas" not in st.session_state:
    st.session_state.noticias_descobertas = []

if "corretores_equipa" not in st.session_state:
    st.session_state.corretores_equipa = {
        "Gabriel Martins": {"cargo": "Head Comercial BeSmart", "insta": "@gabrielmartins.corretor"},
        "Equipe Comercial BeSmart": {"cargo": "Consultoria Imobiliária", "insta": "@besmartimoveis"}
    }

def obter_fonte(size, bold=False):
    candidatos = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans.ttf"
    ]
    for p in candidatos:
        try:
            return ImageFont.truetype(p, size)
        except IOError:
            continue
    return ImageFont.load_default()

def wrap_lines(draw, text, fnt, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        try:
            if hasattr(draw, 'textbbox'):
                bbox = draw.textbbox((0, 0), test, font=fnt)
                w = bbox[2] - bbox[0]
            else:
                w = len(test) * (fnt.size // 2)
        except Exception:
            w = len(test) * 15
        
        if w <= max_width:
            current = test
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    return lines

def carregar_imagem_contexto(item_id, categoria):
    base = "https://images.unsplash.com/photo-"
    fim = "?q=80&w=1080"
    
    curadoria = {
        "Juros e financiamento": ["1486406146926-c627a92ad1ab", "1526304640581-d334cdbbf45e"],
        "Bancos e crédito": ["1501167786227-4cba60f6d58f", "1601597111158-2fceff292cdc"],
        "Lançamentos imobiliários": ["1460317442991-0ec209397118", "1545324418-cc1a3fa10c00"],
        "Valorização de bairros": ["1449844908441-8829872d2607", "1519501025264-65ba15a82390"],
        "Mercado regional": ["1477959858617-67f85cf4f1df", "1480714378408-67cf0d13bc1b"],
        "Investimento imobiliário": ["1560518883-ce09059eeffa", "1558036117-15d82a90b9b1"],
        "Economia": ["1611974789855-9c2a0a7236a3", "1590283603385-17ffb3a7f29f"],
        "Legislação": ["1589829085413-56de8ae18c73", "1505664159854-232fb110c896"],
        "Infraestrutura": ["1541888086425-d81bb19240f5", "1503387762-592deb58ef4e"],
        "Conteúdo educativo": ["1524178232363-1fb2b075b655", "1513258496099-48166614a142"]
    }
    
    lista_ids = curadoria.get(categoria, curadoria["Investimento imobiliário"])
    foto_id = lista_ids[item_id % len(lista_ids)]
    url = base + foto_id + fim
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            img_data = resp.read()
            base_img = Image.open(BytesIO(img_data)).convert("RGB")
            
            w, h = base_img.size
            if w > h:
                left = (w - h * (1080/1920)) / 2
                base_img = base_img.crop((left, 0, w - left, h))
                
            base_img = base_img.resize((1080, 1920), Image.Resampling.LANCZOS)
            base_img = base_img.filter(ImageFilter.GaussianBlur(radius=6))
            overlay = Image.new("RGBA", (1080, 1920), (12, 10, 18, 225))
            im = Image.alpha_composite(base_img.convert("RGBA"), overlay).convert("RGB")
            return im
    except Exception:
        im = Image.new("RGB", (1080, 1920), (15, 13, 24))
        draw = ImageDraw.Draw(im)
        for i in range(0, 1920, 40):
            val = int(15 + (i / 1920) * 25)
            draw.line([(0, i), (1080, i)], fill=(val, val, val + 15), width=2)
        draw.rectangle([90, 90, 990, 1830], outline="#332744", width=3)
        return im

def inserir_logotipo_inteligente(im, x, y, largura_desejada=420):
    candidatos = [
        "BS - Imóveis Horizontal - Branco - BG Preto.png",
        "BS - Imóveis Horizontal - RGB - BG Branco.png",
        "BS - Imóveis Horizontal - Preto - BG Branco.png",
        "logo_oficial.png"
    ]
    logo_img = None
    for nome_arq in candidatos:
        if os.path.exists(nome_arq):
            try:
                logo_img = Image.open(nome_arq).convert("RGBA")
                break
            except Exception:
                continue
                
    if logo_img is not None:
        w_orig, h_orig = logo_img.size
        fator = largura_desejada / w_orig
        novo_h = int(h_orig * fator)
        logo_img = logo_img.resize((largura_desejada, novo_h), Image.Resampling.LANCZOS)
        im.paste(logo_img, (x, y), logo_img)
    else:
        d = ImageDraw.Draw(im)
        fnt_logo = obter_fonte(36, True)
        d.text((x, y), "be.smart imóveis", font=fnt_logo, fill=WHITE)

def make_story(item, corretores_selecionados):
    W, H = 1080, 1920
    im = carregar_imagem_contexto(item.get("id", 1), item.get("categoria", ""))
    
    margin = 90
    inserir_logotipo_inteligente(im, x=margin, y=110, largura_desejada=420)
    
    d = ImageDraw.Draw(im)
    d.line((margin, 270, W-margin, 270), fill="#4A3B66", width=2)

    cat = item.get("categoria", "").upper()
    fnt_cat = obter_fonte(30, True)
    d.text((margin, 340), cat[:38], font=fnt_cat, fill="#B99AE8")
    
    title_font = obter_fonte(72, True)
    lines = wrap_lines(d, item.get("destaque", "").strip(), title_font, W-2*margin)
    y = 430
    for line in lines[:4]:
        d.text((margin, y), line, font=title_font, fill=WHITE)
        y += 92

    y += 24
    d.rounded_rectangle((margin, y, margin+280, y+14), radius=7, fill=PURPLE)
    
    body_font = obter_fonte(44)
    body_lines = wrap_lines(d, item.get("resumo", "").strip(), body_font, W-2*margin)
    y += 90
    for line in body_lines[:6]:
        d.text((margin, y), line, font=body_font, fill=SILVER)
        y += 66

    y += 40
    fonte_texto = f"Fonte: {item.get('fonte', 'Verificado')}"
    fnt_fonte = obter_fonte(28, True)
    d.text((margin, y), fonte_texto[:60], font=fnt_fonte, fill="#A49CB8")

    card_corr_top = 1320
    avatar_x = 220
    espacamento_bloco = 150 if len(corretores_selecionados) <= 2 else 120
    
    for idx_corr, nome_corr in enumerate(corretores_selecionados[:3]):
        info_corr = st.session_state.corretores_equipa.get(nome_corr, {"cargo": "Consultor Imobiliário", "insta": "@besmartimoveis"})
        
        avatar_y = card_corr_top + (idx_corr * espacamento_bloco) + 50
        avatar_r = 55
        
        d.ellipse((avatar_x - avatar_r, avatar_y - avatar_r, avatar_x + avatar_r, avatar_y + avatar_r), fill="#9966FF")
        fnt_avatar = obter_fonte(38, True)
        iniciais = "".join([n[0] for n in nome_corr.split()[:2]]).upper()
        d.text((avatar_x - 24, avatar_y - 25), iniciais, font=fnt_avatar, fill=WHITE)

        text_left = avatar_x + avatar_r + 30
        bloco_top = card_corr_top + (idx_corr * espacamento_bloco)
        
        fnt_nome = obter_fonte(38, True)
        fnt_cargo = obter_fonte(24, True)
        fnt_insta = obter_fonte(22)
        
        d.text((text_left, bloco_top), nome_corr[:26], font=fnt_nome, fill=WHITE)
        d.text((text_left, bloco_top + 48), info_corr['cargo'][:32], font=fnt_cargo, fill="#B99AE8")
        d.text((text_left, bloco_top + 80), info_corr['insta'][:34], font=fnt_insta, fill=MUTED)

    footer_y = 1800
    d.line((margin, footer_y - 25, W-margin, footer_y - 25), fill="#4A3B66", width=2)
    fnt_foot1 = obter_fonte(26, True)
    d.text((margin, footer_y), "Fale com a nossa equipe • Be.Smart Imóveis", font=fnt_foot1, fill="#B99AE8")

    out = BytesIO()
    im.save(out, format="PNG")
    out.seek(0)
    return out

st.markdown('<div class="brand">be.smart <span>news</span></div><div class="small-muted">INTELIGÊNCIA IMOBILIÁRIA • PAINEL ADMINISTRATIVO</div>', unsafe_allow_html=True)
st.write("")

with st.sidebar:
    st.markdown("### ⚙️ Gestão de Corretores")
    
    lista_nomes = list(st.session_state.corretores_equipa.keys())
    selecao_edicao = st.selectbox("Selecionar Corretor", ["➕ Adicionar Novo Corretor"] + lista_nomes)
    
    if selecao_edicao == "➕ Adicionar Novo Corretor":
        with st.form("form_novo_corretor"):
            novo_nome = st.text_input("Nome do Corretor")
            novo_cargo = st.text_input("Cargo", value="Corretor Associado")
            novo_insta = st.text_input("Instagram", value="@besmartimoveis")
            salvar_novo = st.form_submit_button("💾 Salvar Novo Corretor", use_container_width=True)
            
            if salvar_novo:
                if novo_nome:
                    st.session_state.corretores_equipa[novo_nome] = {"cargo": novo_cargo, "insta": novo_insta}
                    st.success("Corretor gravado com sucesso!")
                    st.rerun()
                else:
                    st.error("Insira o nome do corretor.")
    else:
        dados_atuais = st.session_state.corretores_equipa[selecao_edicao]
        with st.form("form_edita_corretor"):
            edit_nome = st.text_input("Nome do Corretor", value=selecao_edicao)
            edit_cargo = st.text_input("Cargo", value=dados_atuais["cargo"])
            edit_insta = st.text_input("Instagram", value=dados_atuais["insta"])
            
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                salvar_edicao = st.form_submit_button("💾 Gravar", use_container_width=True)
            with col_e2:
                excluir_corr = st.form_submit_button("🗑️ Excluir", use_container_width=True)
                
            if salvar_edicao:
                if edit_nome != selecao_edicao:
                    del st.session_state.corretores_equipa[selecao_edicao]
                st.session_state.corretores_equipa[edit_nome] = {"cargo": edit_cargo, "insta": edit_insta}
                st.success("Alterações gravadas!")
                st.rerun()
                
            if excluir_corr:
                if len(st.session_state.corretores_equipa) > 1:
                    del st.session_state.corretores_equipa[selecao_edicao]
                    st.success("Corretor removido com sucesso!")
                    st.rerun()
                else:
                    st.error("Deve manter pelo menos um corretor.")

    st.divider()
    st.markdown("### 🎯 Corretores nos Stories")
    corretores_ativos = st.multiselect(
        "Selecione quem aparecerá",
        options=list(st.session_state.corretores_equipa.keys()),
        default=list(st.session_state.corretores_equipa.keys())[:1]
    )
    
    if not corretores_ativos:
        corretores_ativos = [list(st.session_state.corretores_equipa.keys())[0]]

lista_atual = st.session_state.dados_noticias
c1, c2, c3, c4 = st.columns(4)
c1.metric("Conteúdos", len(lista_atual))
c2.metric("Rascunhos", sum(1 for i in lista_atual if i.get("status") == "Rascunho"))
c3.metric("Aprovados", sum(1 for i in lista_atual if i.get("status") == "Aprovado"))
c4.metric("Stories gerados", len(st.session_state.historico_stories))

tab1, tab2, tab3 = st.tabs(["📰 Conteúdos", "➕ Novo conteúdo do dia", "📚 Histórico & Métricas"])

with tab1:
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.subheader("Biblioteca de informações")
    with col_t2:
        if st.button("🗑️ Limpar biblioteca", use_container_width=True):
            st.session_state.dados_noticias = []
            st.success("Limpa!")
            st.rerun()
    
    if st.session_state.story_ativo is not None:
        with st.container(border=True):
            st.markdown("### 📱 Story Gerado com Sucesso")
            st.image(st.session_state.story_ativo["bytes"], width=320)
            st.download_button(
                "Baixar PNG (1080x1920)", 
                data=st.session_state.story_ativo["bytes"], 
                file_name=st.session_state.story_ativo["filename"], 
                mime="image/png"
            )
            if st.button("Fechar prévia"):
                st.session_state.story_ativo = None
                st.rerun()
        st.divider()

    filt = st.selectbox("Filtrar", ["Todos", "Rascunho", "Aprovado"])
    shown = [i for i in lista_atual if filt == "Todos" or i.get("status") == filt]
    
    if not shown:
        st.info("Nenhum conteúdo encontrado.")
    else:
        for idx_item, item in enumerate(shown):
            with st.container(border=True):
                left, right = st.columns([3, 2])
                with left:
                    st.markdown(f"**{item.get('destaque', '')}**")
                    st.markdown(f"### {item.get('titulo', '')}")
                    st.write(item.get("resumo", ""))
                    st.caption(f"{item.get('categoria', '')} • {item.get('data', '')}")
                
                with right:
                    corretores_story = st.multiselect(
                        "Corretores para o Story:",
                        options=corretores_ativos,
                        default=corretores_ativos[:1],
                        key=f"corr_{idx_item}"
                    )
                    if not corretores_story:
                        corretores_story = [corretores_ativos[0]]
                    
                    col_b1, col_b2, col_b3 = st.columns(3)
                    with col_b1:
                        if st.button("Gerar Story", key=f"s_{idx_item}", use_container_width=True):
                            img_bytes = make_story(item, corretores_story)
                            fname = f"story_{datetime.now().strftime('%H%M%S')}.png"
                            
                            st.session_state.story_ativo = {
                                "bytes": img_bytes, "titulo": item.get('titulo', ''), "filename": fname
                            }
                            st.session_state.historico_stories.insert(0, {
                                "titulo": item.get('titulo', ''), "destaque": item.get('destaque', ''),
                                "categoria": item.get('categoria', ''), "data_geracao": datetime.now().strftime('%d/%m/%Y'),
                                "bytes": img_bytes, "filename": fname
                            })
                            st.rerun()

                    with col_b2:
                        if item.get("status") != "Aprovado":
                            if st.button("Aprovar", key=f"a_{idx_item}", use_container_width=True):
                                item["status"] = "Aprovado"
                                st.rerun()
                        else:
                            st.success("Aprovado")

                    with col_b3:
                        if st.button("🗑️ Excluir", key=f"d_{idx_item}", use_container_width=True):
                            st.session_state.dados_noticias.remove(item)
                            st.rerun()

with tab2:
    st.subheader("Gerador de Notícias (IA)")
    
    with st.container(border=True):
        if st.button("🚀 Buscar Notícias do Dia", type="primary"):
            qtd = random.randint(15, 20)
            try:
                model = genai.GenerativeModel('gemini-3.8-flash')
                prompt_lote = f"""Gere um array JSON válido com exatamente {qtd} objetos contendo:
                categoria (Juros e financiamento, Bancos e crédito, etc), titulo (max 80 carac), 
                destaque (MAIÚSCULAS max 40), resumo (max 150), fonte. APENAS o JSON."""
                
                resp = model.generate_content(prompt_lote)
                limpo = resp.text.replace("```json", "").replace("```", "").strip()
                bruto = json.loads(limpo)
                
                st.session_state.noticias_descobertas = bruto
                st.success(f"{len(bruto)} notícias geradas!")
            except Exception as e:
                st.error("Erro ao gerar notícias com IA.")

    if st.session_state.noticias_descobertas:
        for idx_n, n_item in enumerate(st.session_state.noticias_descobertas):
            with st.container(border=True):
                st.markdown(f"**[{n_item.get('categoria', '')}]** {n_item.get('titulo', '')}")
                if st.button(f"➕ Adicionar", key=f"add_{idx_n}"):
                    n_item["id"] = st.session_state.proximo_id
                    n_item["status"] = "Rascunho"
                    n_item["data"] = str(date.today())
                    st.session_state.dados_noticias.append(n_item)
                    st.session_state.proximo_id += 1
                    st.success("Adicionado!")
                    st.rerun()

    st.divider()
    st.markdown("#### ✍️ Cadastro Manual:")
    
    lista_categorias = [
        "Juros e financiamento", 
        "Bancos e crédito", 
        "Lançamentos imobiliários",
        "Valorização de bairros", 
        "Mercado regional", 
        "Investimento imobiliário",
        "Economia", 
        "Legislação", 
        "Infraestrutura", 
        "Conteúdo educativo"
    ]
    
    with st.form("new_item", clear_on_submit=False):
        categoria = st.selectbox("Categoria", lista_categorias)
        titulo = st.text_input("Título")
        destaque = st.text_input("Chamada (MAIÚSCULAS)")
        resumo = st.text_area("Resumo")
        fonte = st.text_input("Fonte")
        submitted = st.form_submit_button("Salvar na biblioteca", type="primary")
        
        if submitted and titulo and destaque:
            st.session_state.dados_noticias.append({
                "id": st.session_state.proximo_id, "categoria": categoria, "titulo": titulo,
                "destaque": destaque, "resumo": resumo, "fonte": fonte, "status": "Rascunho", 
                "data": str(date.today())
            })
            st.session_state.proximo_id += 1
            st.success("Salvo!")
            st.rerun()

with tab3:
    col_th1, col_th2 = st.columns([3, 1])
    with col_th1:
        st.subheader("📚 Histórico de Publicações")
    with col_th2:
        if st.session_state.historico_stories:
            if st.button("🗑️ Limpar todo o histórico", use_container_width=True):
                st.session_state.historico_stories = []
                st.success("Histórico limpo!")
                st.rerun()
                
    if not st.session_state.historico_stories:
        st.info("Nenhum Story gerado ainda.")
    else:
        for idx, story_hist in enumerate(st.session_state.historico_stories):
            with st.container(border=True):
                col_info, col_img = st.columns([3, 1])
                with col_info:
                    st.markdown(f"**{story_hist['destaque']}**")
                    st.markdown(f"### {story_hist['titulo']}")
                    st.caption(f"Categoria: {story_hist['categoria']} • Gerado em: {story_hist['data_geracao']}")
                    
                    col_h1, col_h2 = st.columns(2)
                    with col_h1:
                        st.download_button(
                            "📥 Baixar PNG",
                            data=story_hist['bytes'],
                            file_name=story_hist['filename'],
                            mime="image/png",
                            key=f"hist_down_{idx}"
                        )
                    with col_h2:
                        if st.button("🗑️ Apagar Story", key=f"del_hist_{idx}", use_container_width=True):
                            st.session_state.historico_stories.pop(idx)
                            st.success("Story removido do histórico!")
                            st.rerun()
                with col_img:
                    st.image(story_hist['bytes'], width=150)