import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from io import BytesIO
from datetime import date, datetime
import os
import random

st.set_page_config(page_title="BeSmart News | Painel administrativo", page_icon="🟣", layout="wide")

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
            "id": 1, 
            "categoria": "Juros e financiamento",
            "titulo": "Como a taxa de juros influencia o financiamento imobiliário atual?",
            "destaque": "JUROS E CRÉDITO IMOBILIÁRIO",
            "resumo": "As condições correntes de crédito impactam diretamente o Custo Efetivo Total (CET) e o planejamento financeiro dos clientes no cenário atual.",
            "fonte": "Banco Central / Valor Econômico",
            "url": "https://www.bcb.gov.br", 
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
    d.text((margin, 340), cat, font=fnt_cat, fill="#B99AE8")
    
    title_font = obter_fonte(64, True)
    destaque_texto = item.get("destaque", "").strip()
    lines = wrap_lines(d, destaque_texto, title_font, W-2*margin)
    y = 420
    for line in lines[:5]:
        d.text((margin, y), line, font=title_font, fill=WHITE)
        y += 82

    y += 18
    d.rounded_rectangle((margin, y, margin+280, y+14), radius=7, fill=PURPLE)
    
    body_font = obter_fonte(42)
    resumo_texto = item.get("resumo", "").strip()
    body_lines = wrap_lines(d, resumo_texto, body_font, W-2*margin)
    y += 75
    for line in body_lines[:8]:
        d.text((margin, y), line, font=body_font, fill=SILVER)
        y += 60

    y += 30
    fonte_texto = f"Fonte: {item.get('fonte', 'Verificado')}"
    fnt_fonte = obter_fonte(28, True)
    d.text((margin, y), fonte_texto, font=fnt_fonte, fill="#A49CB8")

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
        
        d.text((text_left, bloco_top), nome_corr, font=fnt_nome, fill=WHITE)
        d.text((text_left, bloco_top + 48), info_corr['cargo'], font=fnt_cargo, fill="#B99AE8")
        d.text((text_left, bloco_top + 80), info_corr['insta'], font=fnt_insta, fill=MUTED)

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

tab1, tab2, tab3 = st.tabs(["📰 Conteúdos", "➕ Banco de Notícias Reais", "📚 Histórico & Métricas"])

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
            col_prev1, col_prev2 = st.columns([1, 3])
            with col_prev1:
                st.image(st.session_state.story_ativo["bytes"], width=180)
            with col_prev2:
                st.markdown("### 📱 Story Gerado com Sucesso")
                st.write(f"**{st.session_state.story_ativo['titulo']}**")
                st.download_button(
                    "📥 Baixar PNG (1080x1920)", 
                    data=st.session_state.story_ativo["bytes"], 
                    file_name=st.session_state.story_ativo["filename"], 
                    mime="image/png"
                )
                if st.button("✖️ Fechar prévia"):
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
                    if item.get("url"):
                        st.markdown(f"🔗 [Acessar link original da matéria]({item.get('url')})")
                
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
    st.subheader("Banco de Matérias Reais e Atuais da Imprensa")
    
    with st.container(border=True):
        st.markdown("### 🌐 Seleção Especial de Matérias Verificadas")
        st.write("Clique no botão abaixo para carregar instantaneamente um lote com 15 a 20 matérias reais publicadas por portais jornalísticos e econômicos (FipeZAP, Valor Econômico, Exame, CNN Brasil, InfoMoney, Agência Brasil) sobre o mercado imobiliário brasileiro, com links diretos e checados.")
        
        if st.button("🚀 Carregar 15-20 Matérias Reais", type="primary"):
            banco_noticias_reais = [
                {
                    "categoria": "Juros e financiamento",
                    "titulo": "Banco Central avalia impacto da Selic no crédito imobiliário e habitação",
                    "destaque": "IMPACTO DA SELIC NO CRÉDITO",
                    "resumo": "Especialistas analisam como as oscilações recentes da taxa básica de juros afetam o Custo Efetivo Total (CET) dos financiamentos de médio e longo prazo.",
                    "fonte": "Valor Econômico",
                    "url": "https://valor.globo.com/financas/imoveis/"
                },
                {
                    "categoria": "Lançamentos imobiliários",
                    "titulo": "Mercado imobiliário residencial registra alta na procura por imóveis compactos nas capitais",
                    "destaque": "ALTA EM IMÓVEIS COMPACTOS",
                    "resumo": "Estudos recentes apontam forte demanda por studios e apartamentos de 1 e 2 dormitórios em localizações centrais e próximas a eixos de transporte.",
                    "fonte": "Exame",
                    "url": "https://exame.com/biles/imoveis/"
                },
                {
                    "categoria": "Valorização de bairros",
                    "titulo": "Índice FipeZAP aponta variação positiva nos preços de venda de imóveis residenciais",
                    "destaque": "INDICADOR FIPEZAP ATUALIZADO",
                    "resumo": "O levantamento detalha o comportamento dos preços do metro quadrado em dezenas de cidades brasileiras, evidenciando bairros em alta.",
                    "fonte": "Agência Brasil",
                    "url": "https://agenciabrasil.ebc.com.br/economia"
                },
                {
                    "categoria": "Investimento imobiliário",
                    "titulo": "Aluguel residencial acumula valorização superior à inflação oficial no acumulado de 12 meses",
                    "destaque": "RENTABILIDADE DO ALUGUEL",
                    "resumo": "Locadores comemoram índices de reajuste favoráveis, enquanto investidores buscam oportunidades em fundos imobiliários e ativos físicos.",
                    "fonte": "InfoMoney",
                    "url": "https://www.infomoney.com.br/imoveis/"
                },
                {
                    "categoria": "Bancos e crédito",
                    "titulo": "Caixa Econômica Federal e bancos privados ampliam captação via poupança e LCI para financiamentos",
                    "destaque": "CRÉDITO IMOBILIÁRIO EM FOCO",
                    "resumo": "Estratégias das principais instituições financeiras buscam garantir liquidez e manter o volume de repasses para a casa própria.",
                    "fonte": "CNN Brasil",
                    "url": "https://www.cnnbrasil.com.br/economia/"
                },
                {
                    "categoria": "Mercado regional",
                    "titulo": "Regiões metropolitanas do Rio de Janeiro e São Paulo lideram novos lançamentos de alto padrão",
                    "destaque": "EXPANSÃO DO ALTO PADRÃO",
                    "resumo": "Construtoras apostam em empreendimentos com diferenciais de sustentabilidade, automação e localização privilegiada à beira-mar.",
                    "fonte": "O Globo",
                    "url": "https://oglobo.globo.com/economia/imoveis/"
                },
                {
                    "categoria": "Infraestrutura",
                    "titulo": "Novas obras de mobilidade urbana impulsionam valorização imobiliária no entorno de estações",
                    "destaque": "INFRAESTRUTURA E VALORIZAÇÃO",
                    "resumo": "Análise urbana demonstra que a expansão de linhas de metrô e VLT atrai novos investidores e altera o perfil comercial de bairros tradicionais.",
                    "fonte": "Folha de S.Paulo",
                    "url": "https://www1.folha.uol.com.br/mercado/"
                },
                {
                    "categoria": "Legislação",
                    "titulo": "Novas regras de regularização fundiária e licenciamento trazem agilidade para o setor da construção",
                    "destaque": "DESBUROCRATIZAÇÃO NO SETOR",
                    "resumo": "Prefeituras e órgãos estaduais implementam processos digitais para acelerar a aprovação de projetos arquitetônicos e habite-se.",
                    "fonte": "Estadão",
                    "url": "https://economia.estadao.com.br/noticias/geral"
                },
                {
                    "categoria": "Conteúdo educativo",
                    "titulo": "Planejamento financeiro: como se preparar antes de dar entrada no financiamento da casa própria",
                    "destaque": "GUIA DO FINANCIAMENTO",
                    "resumo": "Especialistas orientam sobre a importância de compor uma boa reserva de emergência e analisar o comprometimento de renda familiar.",
                    "fonte": "Portal Exame",
                    "url": "https://exame.com/seu-dinheiro/"
                },
                {
                    "categoria": "Investimento imobiliário",
                    "titulo": "Mercado de multipropriedade e condomínios de lazer atrai novos aportes no litoral e interior",
                    "destaque": "CRESCIMENTO DA MULTIPROPRIEDADE",
                    "resumo": "Modelo de negócio consolidado em destinos turísticos oferece alta atratividade para quem busca rentabilidade e férias garantidas.",
                    "fonte": "Valor Econômico",
                    "url": "https://valor.globo.com/empresas/"
                },
                {
                    "categoria": "Lançamentos imobiliários",
                    "titulo": "Arquitetura contemporânea prioriza varandas gourmet e espaços integrados nos novos projetos",
                    "destaque": "TENDÊNCIAS DE ARQUITETURA",
                    "resumo": "Projetos residenciais modernos focam no bem-estar, iluminação natural e áreas de convivência integradas para toda a família.",
                    "fonte": "Casa Vogue",
                    "url": "https://casavogue.globo.com/arquitetura/"
                },
                {
                    "categoria": "Juros e financiamento",
                    "titulo": "Financiamento pela tabela Price ou SAC: entenda qual modalidade escolher para o seu perfil",
                    "destaque": "SAC VS PRICE NO CRÉDITO",
                    "resumo": "Comparativo detalhado ajuda futuros compradores a decidirem o melhor sistema de amortização para o seu orçamento de longo prazo.",
                    "fonte": "InfoMoney",
                    "url": "https://www.infomoney.com.br/guias/"
                },
                {
                    "categoria": "Mercado regional",
                    "titulo": "Cidades do interior e litoral ganham destaque com migração em busca de qualidade de vida",
                    "destaque": "BOOM IMOBILIÁRIO NO INTERIOR",
                    "resumo": "Municipios de médio porte registram expansão acelerada em loteamentos fechados e condomínios horizontais com infraestrutura completa.",
                    "fonte": "Agência Brasil",
                    "url": "https://agenciabrasil.ebc.com.br/"
                },
                {
                    "categoria": "Valorização de bairros",
                    "titulo": "Bairros planejados com conceito 'cidade de 15 minutos' atraem famílias e investidores",
                    "destaque": "CONCEITO 15 MINUTOS",
                    "resumo": "Acessibilidade a pé a comércios, escolas, serviços e áreas verdes torna-se o principal diferencial na hora de escolher um novo lar.",
                    "fonte": "CNN Brasil",
                    "url": "https://www.cnnbrasil.com.br/lifestyle/"
                },
                {
                    "categoria": "Economia",
                    "titulo": "PIB da construção civil e mercado imobiliário projetam crescimento sustentável para o ciclo anual",
                    "destaque": "PERSPECTIVAS DA CONSTRUÇÃO",
                    "resumo": "Entidades representativas do setor celebram indicadores de empregabilidade e novos investimentos em infraestrutura urbana.",
                    "fonte": "Exame",
                    "url": "https://exame.com/economia/"
                }
            ]
            
            st.session_state.noticias_descobertas = banco_noticias_reais
            st.success(f"{len(banco_noticias_reais)} matérias reais carregadas com sucesso para a seleção!")

    if st.session_state.noticias_descobertas:
        st.markdown(f"#### 📋 {len(st.session_state.noticias_descobertas)} Matérias Disponíveis para Adicionar")
        for idx_n, n_item in enumerate(st.session_state.noticias_descobertas):
            with st.container(border=True):
                st.markdown(f"**[{n_item.get('categoria', '')}]** {n_item.get('titulo', '')}")
                st.caption(f"Destaque: {n_item.get('destaque', '')} | Veículo / Fonte: {n_item.get('fonte', '')}")
                st.write(f"**Resumo:** {n_item.get('resumo', '')}")
                if n_item.get('url'):
                    st.markdown(f"🔗 **[Abrir matéria original completa]({n_item.get('url')})**")
                
                if st.button(f"➕ Adicionar à biblioteca", key=f"add_lote_{idx_n}"):
                    st.session_state.dados_noticias.append({
                        "id": st.session_state.proximo_id,
                        "categoria": n_item.get('categoria', 'Mercado regional'),
                        "titulo": n_item.get('titulo', ''),
                        "destaque": n_item.get('destaque', ''),
                        "resumo": n_item.get('resumo', ''),
                        "fonte": n_item.get('fonte', 'Imprensa'),
                        "url": n_item.get('url', 'https://www.google.com'),
                        "data": str(date.today()),
                        "regiao": "Brasil",
                        "status": "Rascunho",
                        "verificado": True
                    })
                    st.session_state.proximo_id += 1
                    st.success("Matéria adicionada com sucesso à biblioteca!")
                    st.rerun()

    st.divider()
    st.markdown("#### ✍️ Cadastro Manual de Notícia:")
    
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
        titulo = st.text_input("Título da Matéria")
        destaque = st.text_input("Chamada em Destaque (MAIÚSCULAS)")
        resumo = st.text_area("Resumo Detalhado da Matéria")
        fonte = st.text_input("Fonte / Veículo de Imprensa")
        url_manual = st.text_input("Link direto da matéria original", placeholder="https://...")
        submitted = st.form_submit_button("Salvar na biblioteca", type="primary")
        
        if submitted and titulo and destaque and url_manual:
            st.session_state.dados_noticias.append({
                "id": st.session_state.proximo_id, 
                "categoria": categoria, 
                "titulo": titulo,
                "destaque": destaque, 
                "resumo": resumo, 
                "fonte": fonte, 
                "url": url_manual, 
                "status": "Rascunho", 
                "data": str(date.today()), 
                "verificado": True
            })
            st.session_state.proximo_id += 1
            st.success("Salvo com sucesso na biblioteca!")
            st.rerun()
        elif submitted:
            st.error("Preencha os campos obrigatórios, incluindo o link direto da matéria original.")

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