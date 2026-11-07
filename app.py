import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from io import BytesIO
from datetime import date, datetime
import urllib.request
import os
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

if "historico_stories" not in st.session_state:
    st.session_state.historico_stories = []

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
            if f.endswith('.png') and '