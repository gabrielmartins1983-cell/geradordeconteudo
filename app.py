import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from io import BytesIO
from datetime import date, datetime
import os
import random
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

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
            "titulo": "Painel de Inteligência Imobiliária BeSmart - Inicie a varredura diária",
            "destaque": "BEM-VINDO AO PAINEL DIÁRIO",
            "resumo": "Utilize a aba de varredura para capturar as notícias mais recentes da imprensa de forma dinâmica em tempo real.",
            "fonte": "Sistema BeSmart",
            "url": "https://www.google.com", 
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
    for line