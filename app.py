import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from io import BytesIO
from datetime import date, datetime
import urllib.request
import urllib.parse
import os
import json
import random
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
        d.text((text_left, bloco_top + 80), info_corr['insta'][:34], font=fnt_insta, fill=