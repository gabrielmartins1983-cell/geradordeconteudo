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
    # Curadoria de imagens diretas para evitar bloqueios de servidores na nuvem
    curadoria_imagens = {
        "Juros e financiamento": [
            "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=1080&h=1920&fit=crop",
            "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?q=80&w=1080&h=1920&fit=crop"
        ],
        "Bancos e crédito": [
            "https://images.unsplash.com/photo-1501167786227-4cba60f6d58f?q=80&w=1080&h=1920&fit=crop",
            "https://images.unsplash.com/photo-1601597111158-2fceff292cdc?q=80&w=1080&h=1920&fit=crop"
        ],
        "Lançamentos imobiliários": [
            "https://images.unsplash.com/photo-1460317442991-0ec209397118?q=80&w=1080&h=1920&fit=crop",
            "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?q=80&w=1080&h=1920&fit=crop"
        ],
        "Valorização de bairros": [
            "https://images.unsplash.com/photo-1449844908441-8829872d2607?q=80&w=1080&h=1920&fit=crop",
            "https://images.unsplash.com/photo-1519501025264-65ba15a82390?q=80&w=1080&h=1920&fit=crop"
        ],
        "Mercado regional": [
            "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?q=80&w=1080&h=1920&fit=crop",
            "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b?q=80&w=1080&h=1920&fit=crop"
        ],
        "Investimento imobiliário": [
            "https://images.unsplash.com/photo-1560518883-ce09059eeffa?q=80&w=1080&h=1920&fit=crop",
            "https://images.unsplash.com/photo-1558036117-15d82a90b9b1?q=80&w=1080&h=1920&fit=crop"
        ],
        "Economia": [
            "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1080&h=1920&fit=crop",
            "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?q=80&w=1080&h=1920&fit=crop"
        ],
        "Legislação": [
            "https://images.unsplash.com/photo-1589829085413-56de8ae18c73?q=80&w=1080&h=1920&fit=crop",
            "https://images.unsplash.com/photo-1505664159854-232fb110c896?q=80&w=1080&h=1920&fit=crop"
        ],
        "Infraestrutura": [
            "https://images.unsplash.com/photo-1541888086425-d81bb19240f5?q=80&w=1080&h=1920&fit=crop",
            "https://images.unsplash.com/photo-1503387762-592deb58ef4e?q=80&w=1080&h=1920&fit=crop"
        ],
        "Conteúdo educativo": [
            "