import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from io import BytesIO
from datetime import date, datetime
import urllib.request
import urllib.parse
import os
import json
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
            "resumo": "As condições correntes de crédito impactam diretamente o Custo Efetivo Total (CET) e o planejamento estratégico dos compradores.",
            "fonte": "Banco Central / Mercado",
            "url": "https://www.google.com/search?q=financiamento+imobiliario+taxa+juros+hoje", "data": str(date.today()), "regiao": "Brasil",
            "status": "Rascunho", "verificado": True
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

# Estado persistente da Equipe e Corretores na sessão
if "corretores_equipa" not in st.session_state:
    st.session_state.corretores_equipa = {
        "Gabriel Martins": {"cargo": "Head Comercial BeSmart", "insta": "@gabrielmartins.corretor"},
        "Equipe Comercial BeSmart": {"cargo": "Consultoria Imobiliária", "insta": "@besmartimoveis"},
        "Ana Souza": {"cargo": "Corretora Associada", "insta": "@anasouza.besmart"},
        "Carlos Eduardo": {"cargo": "Especialista em Lançamentos", "insta": "@carloseduardo.imoveis"}
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
        fnt_logo = obter_fonte(32, True)
        d.text((x, y), "be.smart imóveis", font=fnt_logo, fill=WHITE)

def make_story(item, corretores_selecionados):
    W, H = 1080, 1920
    
    base_img = carregar_imagem_contexto(item.get("id", 1), item.get("categoria", ""))
    base_img = ImageOps.fit(base_img, (W, H), method=Image.Resampling.LANCZOS)
    base_img = base_img.filter(ImageFilter.GaussianBlur(radius=6))

    overlay = Image.new("RGBA", (W, H), (12, 10, 18, 220))
    im = Image.alpha_composite(base_img.convert("RGBA"), overlay).convert("RGB")
    
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
    fonte_texto = f"Fonte: {item.get('fonte', 'Verificado na fonte oficial')}"
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
    d.text((margin, footer_y), "Fale com a nossa equipe de especialistas • Be.Smart Imóveis", font=fnt_foot1, fill="#B99AE8")

    out = BytesIO()
    im.save(out, format="PNG")
    out.seek(0)
    return out

st.markdown('<div class="brand">be.smart <span>news</span></div><div class="small-muted">INTELIGÊNCIA IMOBILIÁRIA • PAINEL ADMINISTRATIVO</div>', unsafe_allow_html=True)
st.write("")

with st.sidebar:
    st.markdown("### ⚙️ Gestão de Corretores")
    st.info("Edite os campos de nome, cargo e Instagram dos membros da equipa e clique em gravar.")
    
    # Seleção do corretor a editar ou criar novo
    lista_nomes = list(st.session_state.corretores_equipa.keys())
    selecao_edicao = st.selectbox("Selecionar Corretor para Editar", ["➕ Adicionar Novo Corretor"] + lista_nomes)
    
    if selecao_edicao == "➕ Adicionar Novo Corretor":
        with st.form("form_novo_corretor"):
            novo_nome = st.text_input("Nome do Corretor")
            novo_cargo = st.text_input("Cargo", value="Corretor Associado")
            novo_insta = st.text_input("Instagram", value="@besmartimoveis")
            salvar_novo = st.form_submit_button("💾 Salvar Novo Corretor", use_container_width=True)
            
            if salvar_novo:
                if novo_nome:
                    st.session_state.corretores_equipa[novo_nome] = {"cargo": novo_cargo, "insta": novo_insta}
                    st.success(f"Corretor '{novo_nome}' gravado com sucesso!")
                    st.rerun()
                else:
                    st.error("Insira o nome do corretor.")
    else:
        dados_atuais = st.session_state.corretores_equipa[selecao_edicao]
        with st.form("form_edita_corretor"):
            edit_nome = st.text_input("Nome", value=selecao_edicao)
            edit_cargo = st.text_input("Cargo", value=dados_atuais["cargo"])
            edit_insta = st.text_input("Instagram", value=dados_atuais["insta"])
            
            col_fe1, col_fe2 = st.columns(2)
            with col_fe1:
                salvar_edicao = st.form_submit_button("💾 Gravar Alterações", use_container_width=True)
            with col_fe2:
                excluir_corr = st.form_submit_button("🗑️ Excluir", use_container_width=True)
                
            if salvar_edicao:
                if edit_nome != selecao_edicao:
                    del st.session_state.corretores_equipa[selecao_edicao]
                st.session_state.corretores_equipa[edit_nome] = {"cargo": edit_cargo, "insta": edit_insta}
                st.success("Alterações gravadas com sucesso!")
                st.rerun()
                
            if excluir_corr:
                if len(st.session_state.corretores_equipa) > 1:
                    del st.session_state.corretores_equipa[selecao_edicao]
                    st.success("Corretor removido com sucesso!")
                    st.rerun()
                else:
                    st.error("Deve manter pelo menos um corretor registado.")

    st.divider()
    st.markdown("### 🎯 Corretores Ativos para os Stories")
    corretores_ativos = st.multiselect(
        "Selecione quem aparecerá nas pílulas",
        options=list(st.session_state.corretores_equipa.keys()),
        default=list(st.session_state.corretores_equipa.keys())[:1]
    )
    
    if not corretores_ativos:
        corretores_ativos = [list(st.session_state.corretores_equipa.keys())[0]]

st.info("Painel operacional ativo com gestão integrada de corretores e pílulas do dia.")

lista_atual = st.session_state.dados_noticias
c1, c2, c3, c4 = st.columns(4)
c1.metric("Conteúdos cadastrados", len(lista_atual))
c2.metric("Aguardando aprovação", sum(1 for i in lista_atual if isinstance(i, dict) and i.get("status") == "Rascunho"))
c3.metric("Aprovados", sum(1 for i in lista_atual if isinstance(i, dict) and i.get("status") == "Aprovado"))
c4.metric("Stories gerados", len(st.session_state.historico_stories))

tab1, tab2, tab3 = st.tabs(["📰 Conteúdos", "➕ Novo conteúdo do dia", "📚 Histórico & Métricas"])

with tab1:
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.subheader("Biblioteca de informações")
    with col_t2:
        if st.button("🗑️ Limpar toda a biblioteca", use_container_width=True):
            st.session_state.dados_noticias = []
            st.success("Biblioteca limpa com sucesso!")
            st.rerun()
    
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
        st.info("Nenhum conteúdo encontrado na biblioteca.")
    else:
        for idx_item, item in enumerate(shown):
            with st.container(border=True):
                left, right = st.columns([3, 2])
                with left:
                    st.markdown(f"**{item.get('destaque', '')}**")
                    st.markdown(f"### {item.get('titulo', '')}")
                    st.write(item.get("resumo", ""))
                    st.caption(f"{item.get('categoria', '')} • {item.get('regiao', '')} • {item.get('data', '')}")
                    st.caption(f"Fonte: {item.get('fonte', '')}")
                    if item.get("url"):
                        st.markdown(f"🔗 [Acessar link da notícia / Google]({item.get('url')})")
                    else:
                        st.caption("Link da fonte ainda não informado.")
                    st.caption(f"Status: {item.get('status', '')} | Verificado: {'Sim' if item.get('verificado') else 'Não'}")
                
                with right:
                    st.markdown("#### 👥 Assinatura no Story")
                    corretores_story = st.multiselect(
                        "Escolha o(s) corretor(es) para este Story",
                        options=corretores_ativos,
                        default=corretores_ativos[:1],
                        key=f"corr_story_{item.get('id')}_{idx_item}"
                    )
                    
                    if not corretores_story:
                        corretores_story = [corretores_ativos[0]]
                    
                    col_b1, col_b2, col_b3 = st.columns(3)
                    with col_b1:
                        if st.button("Gerar Story", key=f"story_{item.get('id')}_{idx_item}", use_container_width=True):
                            img_bytes = make_story(item, corretores_story)
                            filename_gerado = f"besmart_news_{item.get('id')}_{datetime.now().strftime('%H%M%S')}.png"
                            
                            st.session_state.story_ativo = {
                                "bytes": img_bytes,
                                "titulo": item.get('titulo', 'story'),
                                "filename": filename_gerado
                            }
                            
                            st.session_state.historico_stories.insert(0, {
                                "titulo": item.get('titulo', ''),
                                "destaque": item.get('destaque', ''),
                                "categoria": item.get('categoria', ''),
                                "corretores": ", ".join(corretores_story),
                                "data_geracao": datetime.now().strftime('%d/%m/%Y às %H:%M'),
                                "bytes": img_bytes,
                                "filename": filename_gerado
                            })
                            st.rerun()

                    with col_b2:
                        if item.get("status") != "Aprovado":
                            if st.button("Aprovar", key=f"approve_{item.get('id')}_{idx_item}", use_container_width=True):
                                item["status"] = "Aprovado"
                                st.rerun()
                        else:
                            st.success("Aprovado")

                    with col_b3:
                        if st.button("🗑️ Excluir", key=f"delete_{item.get('id')}_{idx_item}", use_container_width=True):
                            st.session_state.dados_noticias = [x for x in st.session_state.dados_noticias if x.get('id') != item.get('id')]
                            st.success("Conteúdo excluído com sucesso!")
                            st.rerun()

with tab2:
    st.subheader("Gerador de Notícias do Dia com Fallback Inteligente")
    
    with st.container(border=True):
        st.markdown("### 🌐 Buscar Notícias do Dia")
        st.write("Insira um termo para pesquisa. Se a API do Gemini atingir o limite (429), o painel ativará automaticamente a busca direta pelo Google Search.")
        
        termo_pesquisa = st.text_input("Tema de mercado de hoje:", value="mercado imobiliário e juros Brasil")
        
        if st.button("🔎 Buscar Notícias Atualizadas", type="primary"):
            try:
                model = genai.GenerativeModel('gemini-3.8-flash')
                prompt_busca = f"""
                Atue como o Diretor de Inteligência de Mercado da Be.Smart Imóveis no Rio de Janeiro. 
                Com base no tema '{termo_pesquisa}', crie 3 pílulas de notícias recentes e atualizadas do dia sobre o mercado imobiliário.
                Retorne estritamente um array JSON puro (sem markdown) contendo 3 objetos com as chaves:
                - categoria (ex: Juros e financiamento, Mercado regional, Valorização de bairros)
                - titulo (título objetivo)
                - destaque (chamada curta em LETRAS MAIÚSCULAS para Story, máx 35 caracteres)
                - resumo (resumo analítico em 1 ou 2 frases)
                - fonte (veículo de referência)
                """
                resposta = model.generate_content(prompt_busca)
                texto_limpo = resposta.text.replace("```json", "").replace("```", "").strip()
                st.session_state.noticias_descobertas = json.loads(texto_limpo)
                st.success("Notícias do dia obtidas com sucesso via Gemini!")
            except Exception as e:
                st.warning("Limite de cota do Gemini atingido. Acionando busca integrada via Google Search...")
                try:
                    url_busca_google = f"https://www.google.com/search?q={urllib.parse.quote_plus(termo_pesquisa + ' mercado imobiliario noticias hoje')}"
                    st.session_state.noticias_descobertas = [
                        {
                            "categoria": "Mercado regional",
                            "titulo": f"Atualidades de hoje sobre: {termo_pesquisa}",
                            "destaque": "NOTÍCIA DE HOJE",
                            "resumo": "Consulte as principais manchetes atualizadas e em tempo real sobre este tema diretamente nos portais especializados.",
                            "fonte": "Google Search / Web",
                            "url_custom": url_busca_google
                        }
                    ]
                    st.success("Busca integrada ativada com sucesso!")
                except Exception as ex_google:
                    st.error(f"Erro na busca: {ex_google}")

    if st.session_state.noticias_descobertas:
        st.markdown("#### 📋 Resultados Encontrados para Adicionar")
        for idx_n, n_item in enumerate(st.session_state.noticias_descobertas):
            with st.container(border=True):
                st.markdown(f"**[{n_item.get('categoria', 'Mercado')}]** {n_item.get('titulo', '')}")
                st.caption(f"Destaque: {n_item.get('destaque', '')} | Fonte: {n_item.get('fonte', '')}")
                st.write(n_item.get('resumo', ''))
                
                if st.button(f"➕ Adicionar à biblioteca", key=f"add_descoberta_{idx_n}"):
                    if "url_custom" in n_item:
                        link_final = n_item["url_custom"]
                    else:
                        link_final = f"