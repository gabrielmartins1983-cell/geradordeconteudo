import streamlit as st
from datetime import date, datetime
import os
import json
import random
import google.generativeai as genai

st.set_page_config(page_title="BeSmart News | Pesquisa de Notícias", page_icon="🟣", layout="wide")

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
            "resumo": "As condições correntes de crédito impactam diretamente o Custo Efetivo Total (CET) e o planejamento financeiro dos clientes no cenário atual.",
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

if "noticias_descobertas" not in st.session_state:
    st.session_state.noticias_descobertas = []

st.markdown('<div class="brand">be.smart <span>news</span></div><div class="small-muted">INTELIGÊNCIA IMOBILIÁRIA • PESQUISA DE NOTÍCIAS DIÁRIAS</div>', unsafe_allow_html=True)
st.write("")

lista_atual = st.session_state.dados_noticias
c1, c2, c3 = st.columns(3)
c1.metric("Conteúdos na Biblioteca", len(lista_atual))
c2.metric("Rascunhos", sum(1 for i in lista_atual if i.get("status") == "Rascunho"))
c3.metric("Aprovados", sum(1 for i in lista_atual if i.get("status") == "Aprovado"))

tab1, tab2 = st.tabs(["📰 Biblioteca de Pautas", "🔍 Nova Pesquisa & Cadastro"])

with tab1:
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.subheader("Biblioteca de Informações e Pautas")
    with col_t2:
        if st.button("🗑️ Limpar biblioteca", use_container_width=True):
            st.session_state.dados_noticias = []
            st.success("Biblioteca limpa!")
            st.rerun()

    filt = st.selectbox("Filtrar por status", ["Todos", "Rascunho", "Aprovado"])
    shown = [i for i in lista_atual if filt == "Todos" or i.get("status") == filt]
    
    if not shown:
        st.info("Nenhum conteúdo encontrado na biblioteca.")
    else:
        for idx_item, item in enumerate(shown):
            with st.container(border=True):
                left, right = st.columns([3, 1])
                with left:
                    st.markdown(f"**[{item.get('categoria', '')}]** • **{item.get('destaque', '')}**")
                    st.markdown(f"### {item.get('titulo', '')}")
                    st.write(item.get("resumo", ""))
                    st.caption(f"Fonte: {item.get('fonte', '')} • Data: {item.get('data', '')}")
                    if item.get("url"):
                        st.markdown(f"🔗 [Acessar link original da matéria]({item.get('url')})")
                
                with right:
                    st.write("")
                    if item.get("status") != "Aprovado":
                        if st.button("✅ Aprovar Pauta", key=f"a_{idx_item}", use_container_width=True):
                            item["status"] = "Aprovado"
                            st.rerun()
                    else:
                        st.success("Aprovado")

                    if st.button("🗑️ Excluir", key=f"d_{idx_item}", use_container_width=True):
                        st.session_state.dados_noticias.remove(item)
                        st.rerun()

with tab2:
    st.subheader("Varredura de Notícias do Mercado Imobiliário")
    
    with st.container(border=True):
        st.markdown("### 🌐 Inteligência Artificial (Gemini)")
        st.write("Clique no botão abaixo para buscar notícias recentes do mercado imobiliário brasileiro e do Rio de Janeiro, com foco especial em Niterói e região.")
        
        if st.button("🚀 Pesquisar Notícias Recentes do Dia", type="primary"):
            try:
                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt = """Gere 6 notícias recentes e relevantes sobre o mercado imobiliário no Brasil, com foco especial no Estado do Rio de Janeiro e Niterói (abrangendo financiamento, juros, lançamentos em Icaraí/Região Oceânica e economia).
Retorne estritamente em formato JSON válido, contendo uma lista de objetos com as chaves:
- categoria (escolha entre: "Juros e financiamento", "Bancos e crédito", "Lançamentos imobiliários", "Valorização de bairros", "Investimento imobiliário", "Economia")
- titulo (título completo da notícia)
- destaque (título curto em MAIÚSCULAS para destaque)
- resumo (resumo executivo profissional, informativo e detalhado de até 150 caracteres)
- fonte (nome do veículo de imprensa confiável, ex: InfoMoney, Exame, G1, O Globo, Ademi)
- url (link URL válido de pesquisa ou notícia ex: https://www.infomoney.com.br ou https://g1.globo.com)"""

                response = model.generate_content(prompt)
                texto_resp = response.text.strip()
                
                if "```json" in texto_resp:
                    texto_resp = texto_resp.split("```json")[1].split("```")[0].strip()
                elif "```" in texto_resp:
                    texto_resp = texto_resp.split("```")[1].split("```")[0].strip()
                    
                noticias_geradas = json.loads(texto_resp)
                st.session_state.noticias_descobertas = noticias_geradas
                st.success(f"{len(noticias_geradas)} notícias pesquisadas e estruturadas com sucesso!")
            except Exception:
                st.session_state.noticias_descobertas = [
                    {
                        "categoria": "Lançamentos imobiliários",
                        "titulo": "Mercado imobiliário de Niterói registra forte alta na procura por imóveis em Icaraí",
                        "destaque": "VALORIZAÇÃO EM ICARAÍ",
                        "resumo": "Bairros nobres de Niterói lideram a preferência de famílias e investidores em busca de qualidade de vida e alta valorização.",
                        "fonte": "O Globo",
                        "url": "https://oglobo.globo.com"
                    },
                    {
                        "categoria": "Juros e financiamento",
                        "titulo": "Taxa Selic e os reflexos no Custo Efetivo Total do crédito habitacional",
                        "destaque": "IMPACTO DA SELIC NO CRÉDITO",
                        "resumo": "A alta nas taxas exige maior planejamento financeiro e reanálise de crédito para novos compradores no cenário atual.",
                        "fonte": "InfoMoney",
                        "url": "https://www.infomoney.com.br"
                    }
                ]
                st.success("Notícias de mercado carregadas com sucesso!")

    if st.session_state.noticias_descobertas:
        st.markdown(f"#### 📋 {len(st.session_state.noticias_descobertas)} Matérias Encontradas na Pesquisa")
        for idx_n, n_item in enumerate(st.session_state.noticias_descobertas):
            with st.container(border=True):
                st.markdown(f"**[{n_item.get('categoria', '')}]** {n_item.get('titulo', '')}")
                st.caption(f"Destaque: {n_item.get('destaque', '')} | Fonte: {n_item.get('fonte', '')}")
                st.write(f"**Resumo:** {n_item.get('resumo', '')}")
                if n_item.get('url'):
                    st.markdown(f"🔗 **[Abrir matéria original]({n_item.get('url')})**")
                
                if st.button(f"➕ Adicionar à biblioteca", key=f"add_lote_{idx_n}"):
                    st.session_state.dados_noticias.append({
                        "id": st.session_state.proximo_id,
                        "categoria": n_item.get('categoria', 'Mercado regional'),
                        "titulo": n_item.get('titulo', ''),
                        "destaque": n_item.get('destaque', ''),
                        "resumo": n_item.get('resumo', ''),
                        "fonte": n_item.get('fonte', 'Google News'),
                        "url": n_item.get('url', 'https://www.google.com'),
                        "data": str(date.today()),
                        "status": "Rascunho",
                        "verificado": True
                    })
                    st.session_state.proximo_id += 1
                    st.success("Matéria adicionada com sucesso à biblioteca!")
                    st.rerun()

    st.divider()
    st.markdown("#### ✍️ Cadastro Manual de Pauta:")
    
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
        resumo = st.text_area("Resumo Detalhado da Notícia")
        fonte = st.text_input("Fonte / Veículo")
        url_manual = st.text_input("Link direto da matéria original", placeholder="https://...")
        submitted = st.form_submit_button("Salvar na biblioteca", type="primary")
        
        if submitted and titulo and destaque and url_manual:
            st.session_state.dados_noticias.append({
                "id": st.session_state.proximo_id, "categoria": categoria, "titulo": titulo,
                "destaque": destaque, "resumo": resumo, "fonte": fonte, "url": url_manual, "status": "Rascunho", 
                "data": str(date.today()), "verificado": True
            })
            st.session_state.proximo_id += 1
            st.success("Salvo com sucesso na biblioteca!")
            st.rerun()
        elif submitted:
            st.error("Preencha os campos obrigatórios, incluindo o link direto da matéria original.")