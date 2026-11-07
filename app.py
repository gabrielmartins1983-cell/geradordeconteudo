import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageStat
from io import BytesIO
from datetime import date
import urllib.request
import os

st.set_page_config(page_title="BeSmart News | Painel administrativo", page_icon="🟣", layout="wide")

# Cores Oficiais baseadas no Guia de Marca da BeSmart / InvestSmart
PURPLE = "#9966FF"      # Roxo InvestSmart Oficial (#9966FF)
WHITE = "#FFFFFF"       # Branco Oficial (#FFFFFF)
SILVER = "#F3F3F3"      # Prata Oficial (#F3F3F3)
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
            "titulo": "Como a taxa de juros influencia o financiamento imobiliário?",
            "destaque": "JUROS E CRÉDITO IMOBILIÁRIO",
            "resumo": "As condições de crédito influenciam diretamente o valor das parcelas mensais, o Custo Efetivo Total (CET) e o planejamento estratégico de compra a longo prazo.",
            "fonte": "Banco Central / ABRAINC",
            "url": "https://exemplo.com", "data": str(date.today()), "regiao": "Brasil",
            "status": "Rascunho", "verificado": True
        },
        {
            "id": 2, "categoria": "Mercado regional",
            "titulo": "O que observar antes de investir em um bairro em transformação?",
            "destaque": "MERCADO IMOBILIÁRIO",
            "resumo": "Infraestrutura urbana, novos modais de mobilidade, chegada de serviços e polos comerciais ajudam a entender a dinâmica de valorização de uma região.",
            "fonte": "BeSmart Inteligência de Mercado",
            "url": "https://exemplo.com", "data": str(date.today()), "regiao": "Rio de Janeiro e Niterói",
            "status": "Rascunho", "verificado": True
        }
    ]
if "proximo_id" not in st.session_state:
    st.session_state.proximo_id = 3

if "story_ativo" not in st.session_state:
    st.session_state.story_ativo = None

def obter_fonte(size, bold=False):
    candidatos = [
        "arialbd.ttf" if bold else "arial.ttf",
        "seguiib.ttf" if bold else "segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
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
            bbox = draw.textbbox((0, 0), test, font=fnt)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(test) * (fnt.size // 2)
        
        if w <= max_width:
            current = test
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    return lines

def carregar_imagem_contexto(item_id, categoria):
    termos_map = {
        "Juros e financiamento": ["skyscraper", "financial", "architecture", "bank"],
        "Mercado regional": ["cityscape", "urban", "street", "neighborhood"],
        "Lançamentos imobiliários": ["modern", "luxury", "property", "apartment"],
        "Valorização de bairros": ["city", "development", "bridge", "aerial"]
    }
    lista_termos = termos_map.get(categoria, ["architecture", "realestate", "building"])
    termo_escolhido = lista_termos[item_id % len(lista_termos)]
    
    seed_val = f"besmart_story_img_{item_id}_{termo_escolhido}"
    url = f"https://picsum.photos/seed/{seed_val}/1080/1920"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            img_data = resp.read()
            return Image.open(BytesIO(img_data)).convert("RGB")
    except Exception:
        base_fallback = Image.new("RGB", (1080, 1920), (20, 18, 30))
        d = ImageDraw.Draw(base_fallback)
        for i in range(0, 1920, 4):
            val = int(20 + (i / 1920) * 15)
            d.line([(0, i), (1080, i)], fill=(val, val, val + 10))
        return base_fallback

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
                
    if logo_img is None:
        for f in os.listdir('.'):
            if f.endswith('.png') and 'Horizontal' in f:
                try:
                    logo_img = Image.open(f).convert("RGBA")
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
        d.text((x, y), "be.smart imóveis", font=obter_fonte(24, True), fill=WHITE)

def make_story(item, nome_corretor, cargo_corretor, insta_corretor):
    W, H = 1080, 1920
    
    # Fundo fotográfico limpo com desfoque elegante
    base_img = carregar_imagem_contexto(item.get("id", 1), item.get("categoria", ""))
    base_img = ImageOps.fit(base_img, (W, H), method=Image.Resampling.LANCZOS)
    base_img = base_img.filter(ImageFilter.GaussianBlur(radius=6))

    # Camada translúcida corporativa para leitura impecável
    overlay = Image.new("RGBA", (W, H), (12, 10, 18, 220))
    im = Image.alpha_composite(base_img.convert("RGBA"), overlay).convert("RGB")
    
    margin = 90
    
    # 1. Topo: Logotipo Oficial da BeSmart com respiro otimizado
    inserir_logotipo_inteligente(im, x=margin, y=110, largura_desejada=420)
    
    d = ImageDraw.Draw(im)
    
    # Linha divisória superior
    d.line((margin, 270, W-margin, 270), fill="#4A3B66", width=2)

    # 2. Categoria em destaque
    cat = item.get("categoria", "").upper()
    d.text((margin, 340), cat[:38], font=obter_fonte(30, True), fill="#B99AE8")
    
    # 3. Título / Chamada principal com espaçamento generoso
    title_font = obter_fonte(72, True)
    lines = wrap_lines(d, item.get("destaque", "").strip(), title_font, W-2*margin)
    y = 430
    for line in lines[:4]:
        d.text((margin, y), line, font=title_font, fill=WHITE)
        y += 92

    # Barra roxa de destaque editorial
    y += 24
    d.rounded_rectangle((margin, y, margin+280, y+14), radius=7, fill=PURPLE)
    
    # 4. Resumo explicativo amplo, arejado e bem espaçado
    body_font = obter_fonte(44)
    body_lines = wrap_lines(d, item.get("resumo", "").strip(), body_font, W-2*margin)
    y += 90
    for line in body_lines[:6]:
        d.text((margin, y), line, font=body_font, fill=SILVER)
        y += 66

    # 5. Fonte Oficial da informação com bom respiro inferior
    y += 40
    fonte_texto = f"Fonte: {item.get('fonte', 'Verificado na fonte oficial')}"
    d.text((margin, y), fonte_texto[:60], font=obter_fonte(28, True), fill="#A49CB8")

    # 6. Bloco do Corretor AMPLIADO (Posicionado com espaço ideal no terço inferior)
    card_corr_top = 1350
    avatar_x = 220
    avatar_y = card_corr_top + 75
    avatar_r = 75  # Raio de 75px (diâmetro de 150px)
    
    # Círculo da foto de perfil grande
    d.ellipse((avatar_x - avatar_r, avatar_y - avatar_r, avatar_x + avatar_r, avatar_y + avatar_r), fill="#9966FF")
    d.text((avatar_x - 30, avatar_y - 32), "GM", font=obter_fonte(48, True), fill=WHITE)

    # Textos do corretor maiores e bem distribuídos ao lado do avatar
    text_left = avatar_x + avatar_r + 35
    d.text((text_left, card_corr_top + 15), nome_corretor[:22], font=obter_fonte(44, True), fill=WHITE)
    d.text((text_left, card_corr_top + 72), cargo_corretor[:28], font=obter_fonte(28, True), fill="#B99AE8")
    d.text((text_left, card_corr_top + 110), insta_corretor[:30], font=obter_fonte(26), fill=MUTED)

    # 7. Rodapé institucional perfeitamente posicionado na base
    footer_y = 1780
    d.line((margin, footer_y - 30, W-margin, footer_y - 30), fill="#4A3B66", width=2)
    d.text((margin, footer_y), f"Fale com a nossa equipe • {insta_corretor}", font=obter_fonte(28, True), fill="#B99AE8")
    d.text((margin, footer_y + 42), "informação que aproxima você do mercado imobiliário", font=obter_fonte(22), fill=MUTED)

    out = BytesIO()
    im.save(out, format="PNG")
    out.seek(0)
    return out

st.markdown('<div class="brand">be.smart <span>news</span></div><div class="small-muted">INTELIGÊNCIA IMOBILIÁRIA • PAINEL ADMINISTRATIVO</div>', unsafe_allow_html=True)
st.write("")

with st.sidebar:
    st.markdown("### ⚙️ Configurações do Corretor")
    st.info("Personalize os dados que aparecerão na arte e no rodapé dos seus Stories.")
    nome_input = st.text_input("Seu Nome", value="Gabriel Martins")
    cargo_input = st.text_input("Seu Cargo / Papel", value="Head Comercial BeSmart")
    insta_input = st.text_input("Seu Instagram", value="@gabrielmartins.corretor")

st.info("Protótipo inicial: os itens de exemplo abaixo são demonstrativos.")

lista_atual = st.session_state.dados_noticias
c1, c2, c3, c4 = st.columns(4)
c1.metric("Conteúdos cadastrados", len(lista_atual))
c2.metric("Aguardando aprovação", sum(1 for i in lista_atual if isinstance(i, dict) and i.get("status") == "Rascunho"))
c3.metric("Aprovados", sum(1 for i in lista_atual if isinstance(i, dict) and i.get("status") == "Aprovado"))
c4.metric("Com fonte verificada", sum(1 for i in lista_atual if isinstance(i, dict) and i.get("verificado")))

tab1, tab2, tab3 = st.tabs(["📰 Conteúdos", "➕ Novo conteúdo", "ℹ️ Próximas etapas"])

with tab1:
    st.subheader("Biblioteca de informações")
    
    if st.session_state.story_ativo is not None:
        with st.container(border=True):
            st.markdown("### 📱 Story Gerado com Sucesso")
            st.image(st.session_state.story_ativo["bytes"], caption=f"Prévia • {st.session_state.story_ativo['titulo']}", width=320)
            st.download_button(
                "Baixar Imagem PNG (1080x1920)", 
                data=st.session_state.story_ativo["bytes"], 
                file_name=st.session_state.story_ativo["filename"], 
                mime="image/png"
            )
            if st.button("Fechar prévia"):
                st.session_state.story_ativo = None
                st.rerun()
        st.divider()

    filt = st.selectbox("Filtrar por situação", ["Todos", "Rascunho", "Aprovado"])
    shown = [i for i in lista_atual if isinstance(i, dict) and (filt == "Todos" or i.get("status") == filt)]
    
    if not shown:
        st.info("Nenhum conteúdo encontrado.")
    else:
        for item in shown:
            with st.container(border=True):
                left, right = st.columns([4,1])
                with left:
                    st.markdown(f"**{item.get('destaque', '')}**")
                    st.markdown(f"### {item.get('titulo', '')}")
                    st.write(item.get("resumo", ""))
                    st.caption(f"{item.get('categoria', '')} • {item.get('regiao', '')} • {item.get('data', '')}")
                    st.caption(f"Fonte: {item.get('fonte', '')}")
                    if item.get("url"):
                        st.markdown(f"[Abrir fonte original]({item.get('url')})")
                    else:
                        st.caption("Link da fonte ainda não informado.")
                    st.caption(f"Status: {item.get('status', '')} | Fonte verificada: {'Sim' if item.get('verificado') else 'Não'}")
                with right:
                    if st.button("Gerar Story", key=f"story_{item.get('id')}", use_container_width=True):
                        img_bytes = make_story(item, nome_input, cargo_input, insta_input)
                        st.session_state.story_ativo = {
                            "bytes": img_bytes,
                            "titulo": item.get('titulo', 'story'),
                            "filename": f"besmart_news_{item.get('id')}.png"
                        }
                        st.rerun()

                    if item.get("status") != "Aprovado":
                        if st.button("Aprovar", key=f"approve_{item.get('id')}", use_container_width=True):
                            item["status"] = "Aprovado"
                            st.rerun()
                    else:
                        st.success("Aprovado")

with tab2:
    st.subheader("Cadastrar informação")
    with st.form("new_item", clear_on_submit=True):
        categoria = st.selectbox(
            "Categoria", 
            [
                "Juros e financiamento", "Bancos e crédito", "Lançamentos imobiliários",
                "Valorização de bairros", "Mercado regional", "Investimento imobiliário",
                "Economia", "Legislação", "Infraestrutura", "Conteúdo educativo"
            ]
        )
        titulo = st.text_input("Título interno", placeholder="Ex.: Mudança nas regras de financiamento")
        destaque = st.text_input("Chamada principal da arte", placeholder="Ex.: O CRÉDITO IMOBILIÁRIO ESTÁ MUDANDO")
        resumo = st.text_area("Resumo curto", placeholder="Explique a informação em uma ou duas frases.")
        gancho = st.text_input("Pergunta ou chamada para despertar interesse", placeholder="Ex.: Quer entender como isso afeta sua compra?")
        regiao = st.selectbox("Abrangência", ["Brasil", "Rio de Janeiro", "Niterói", "Rio de Janeiro e Niterói", "Outro"])
        fonte = st.text_input("Nome da fonte")
        url = st.text_input("Link da fonte original")
        verificado = st.checkbox("Conferi a informação diretamente na fonte original")
        submitted = st.form_submit_button("Salvar conteúdo", type="primary", use_container_width=True)
        
        id_atual = st.session_state.proximo_id
        if submitted:
            if not titulo or not destaque or not resumo or not fonte:
                st.error("Preencha título, chamada, resumo e fonte.")
            elif not url.startswith("http"):
                st.error("Informe o link completo da fonte (começando com http ou https).")
            else:
                st.session_state.dados_noticias.append({
                    "id": id_atual, 
                    "categoria": categoria, 
                    "titulo": titulo,
                    "destaque": destaque, 
                    "resumo": resumo, 
                    "gancho": gancho or "Converse com a equipe BeSmart.",
                    "fonte": fonte, 
                    "url": url, 
                    "data": str(date.today()), 
                    "regiao": regiao,
                    "status": "Rascunho", 
                    "verificado": verificado
                })
                st.session_state.proximo_id += 1
                st.success("Conteúdo cadastrado com sucesso! Disponível na biblioteca.")
                st.rerun()

with tab3:
    st.subheader("Evolução prevista")
    st.markdown("""
    **Versão 1 — protótipo atual**
    - Cadastro manual de informações e fontes.
    - Aprovação editorial.
    - Geração de Story PNG com espaçamento fluido e excelente diagramação vertical.
    """)
    st.warning("Este protótipo ainda não publica automaticamente no Instagram ou WhatsApp.")