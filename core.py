"""BeSmart News - motor do projeto (não depende do Streamlit, então é testável).

Contém: persistência completa, coleta, decodificação de matérias, redação jornalística sênior
e motor de direção de arte com gerador gráfico interno de fundo 100% liso e livre de paletas fixas.
"""
from __future__ import annotations

import base64
import difflib
import hashlib
import html
import importlib.util
import io
import json
import os
import random
import re
import shutil
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
OUT_DIR = BASE / "output"
ASSETS = BASE / "assets"
FUNDOS_DIR = DATA_DIR / "fundos"
DB_FILE = DATA_DIR / "db.json"
_ULTIMO_AVISO_FUNDO: str | None = None


def _carregar_env_local() -> None:
    for nome_env in (".env", ".env.txt"):
        env_path = BASE / nome_env
        if not env_path.exists():
            continue
        try:
            for linha in env_path.read_text(encoding="utf-8-sig").splitlines():
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                chave, valor = linha.split("=", 1)
                chave = chave.strip()
                valor = valor.strip().strip('"').strip("'")
                if chave and valor and chave not in os.environ:
                    os.environ[chave] = valor
        except OSError:
            pass


_carregar_env_local()

PURPLE, WHITE, SILVER, MUTED = "#9966FF", "#FFFFFF", "#F3F3F3", "#B8B5C1"
LILAC, LINE = "#B99AE8", "#4A3B66"
MARCA = "Be.Smart Imóveis"

CATEGORIAS = [
    "Juros e financiamento", "Bancos e crédito", "Lançamentos imobiliários",
    "Valorização de bairros", "Mercado regional", "Investimento imobiliário",
    "Economia", "Legislação", "Infraestrutura", "Conteúdo educativo",
]

CORRETORES_PADRAO = {
    "Gabriel Martins": {"cargo": "Head Comercial BeSmart", "insta": "@gabrielmartins.corretor"},
    "Equipe Comercial BeSmart": {"cargo": "Consultoria Imobiliária", "insta": "@besmartimoveis"},
}

MAPA_CONSULTAS_PADRAO = {
    "Mercado Niterói e RJ": '("mercado imobiliário" OR imóveis OR lançamentos) (Niterói OR "Rio de Janeiro" OR RJ)',
    "Mercado SP (Zonas Nobres)": '("mercado imobiliário" OR imóveis OR lançamentos) ("Vila Olímpia" OR Moema OR "Itaim Bibi" OR "Vila Nova Conceição" OR Pinheiros OR Jardins)',
    "Crédito e Financiamento": '("financiamento imobiliário" OR "crédito imobiliário" OR "Caixa" habitação OR Selic imóveis)',
    "Construção e Incorporação": '(incorporadora OR construtora OR "construção civil" OR "Minha Casa Minha Vida")',
}


def norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(texto)).strip("-") or "sem-titulo"


def limpar_html(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_RUIDO_WEB = (
    "cookie", "privacidade", "assine", "cadastre-se", "faca login", "faça login",
    "todos os direitos reservados", "compartilhe", "leia mais", "veja tambem",
    "publicidade", "anuncio", "newsletter", "whatsapp", "telegram",
    "google noticias", "google news", "consent.google",
    "cobertura jornalistica abrangente", "agregada de fontes do mundo inteiro",
    "enable javascript", "antes de prosseguir para o google", "before you continue to google",
)

_PALAVRAS_FINAIS_INVALIDAS = {
    "de", "do", "da", "dos", "das", "no", "na", "nos", "nas", "num", "numa",
    "pelo", "pela", "pelos", "pelas", "para", "por", "com", "em", "a", "o",
    "as", "os", "ao", "aos", "à", "às", "e", "ou", "mas", "que", "como",
    "entre", "sobre", "após", "até", "sem", "sob", "um", "uma", "uns", "umas",
}


def _eh_boilerplate(texto: str) -> bool:
    tn = norm(texto)
    if not tn:
        return True
    return any(r in tn for r in _RUIDO_WEB)


def _limpar_ruido_texto(txt: str) -> str:
    t = re.sub(r"\s*(?:[-|•]\s*)?Google\s+Not[íi]cias\.?\s*$", "", txt or "", flags=re.IGNORECASE)
    t = re.sub(r"\s*(?:[-|•]\s*)?Google\s+News\.?\s*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    if _eh_boilerplate(t):
        return ""
    return t


def _frase_valida_pt(frase: str, titulo: str = "") -> bool:
    f = (frase or "").strip()
    if len(f) < 25 or _eh_boilerplate(f):
        return False
    if titulo and norm(f) == norm(titulo):
        return False
    sem_pont = re.sub(r"[.!?;:,…]+$", "", f).strip()
    palavras = sem_pont.split()
    if len(palavras) < 4:
        return False
    ultima = norm(re.sub(r"[^a-zA-ZÀ-ÿ]", "", palavras[-1]))
    if ultima in _PALAVRAS_FINAIS_INVALIDAS:
        return False
    return True


def _normalizar_frase_pt(frase: str, ponto_final: bool = True) -> str:
    f = re.sub(r"\s+", " ", (frase or "").strip())
    if not f:
        return ""
    f = f[0].upper() + f[1:]
    if ponto_final and not f.endswith((".", "!", "?")):
        f = f.rstrip(",;:") + "."
    elif not ponto_final:
        f = f.rstrip(".")
    return f


def _cortar_em_frase_completa(texto: str, max_chars: int = 360) -> str:
    t = re.sub(r"\s+", " ", (texto or "").strip())
    if len(t) <= max_chars:
        return _normalizar_frase_pt(t, ponto_final=True)
    recorte = t[:max_chars]
    ultimo_ponto = max(recorte.rfind(". "), recorte.rfind("! "), recorte.rfind("? "))
    if ultimo_ponto >= int(max_chars * 0.45):
        return _normalizar_frase_pt(recorte[: ultimo_ponto + 1], ponto_final=True)
    return _normalizar_frase_pt(recorte.rsplit(" ", 1)[0].rstrip(",;:") + ".", ponto_final=True)


def _resolver_url_google_news(url: str) -> str:
    if not url or "news.google.com" not in url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
        partes = [p for p in parsed.path.split("/") if p]
        if "articles" not in partes:
            return url
        idx = partes.index("articles")
        token = partes[idx + 1] if idx + 1 < len(partes) else ""
        if not token:
            return url
        b64 = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(b64).decode("latin1", errors="ignore")
        m_url = re.search(r"https?://[^\s<>\"']+", raw)
        if m_url and "news.google.com" not in m_url.group(0):
            return m_url.group(0)

        artigo_url = f"https://news.google.com/articles/{token}"
        req_page = urllib.request.Request(
            artigo_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "pt-BR,pt;q=0.9",
            },
        )
        with urllib.request.urlopen(req_page, timeout=6) as resp:
            final_url = resp.geturl()
            if final_url and "news.google.com" not in final_url:
                return final_url
            page_html = resp.read().decode("utf-8", errors="ignore")

        m_sg = re.search(r'data-n-a-sg=["\']([^"\']+)["\']', page_html)
        m_ts = re.search(r'data-n-a-ts=["\']([^"\']+)["\']', page_html)
        if m_sg and m_ts:
            sg, ts = m_sg.group(1), m_ts.group(1)
            inner = json.dumps([
                "garturlreq",
                [["X", "X", ["X", "X"], None, None, 1, 1, "PT:pt-BR", None, 1, None, None, None, None, None, 0, 1],
                 "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                token,
                int(ts),
                sg,
            ])
            payload = urllib.parse.urlencode({"f.req": json.dumps([[["Fbv4je", inner, None, "generic"]]])}).encode("utf-8")
            req_api = urllib.request.Request(
                "https://news.google.com/_/DotsSplashUi/data/batchexecute",
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                },
            )
            with urllib.request.urlopen(req_api, timeout=6) as r_api:
                resp_txt = r_api.read().decode("utf-8", errors="ignore")
            m_res = re.search(r'garturlres\?",\?"(https?://[^\"]+)', resp_txt)
            if m_res:
                destino = m_res.group(1).replace("\u003d", "=").replace("\u0026", "&")
                if "news.google.com" not in destino:
                    return destino
    except Exception:
        pass
    return url


def extrair_texto_url(url: str) -> str:
    if not url:
        return ""
    url_real = _resolver_url_google_news(url)
    if "news.google.com" in url_real:
        return ""
    try:
        dados = baixar(url_real, ttl=86400, timeout=10)
        html_str = dados.decode("utf-8", errors="ignore")
        html_str = re.sub(r"(?is)<(script|style|nav|header|footer|aside|form|noscript).*?>.*?</ >", "", html_str)

        partes: list[str] = []
        meta_pat = r'(?is)<meta[^>]+(?:property|name)=["\'](?:og:description|description|twitter:description)["\'][^>]+content=["\'](.*?)["\']'
        m = re.search(meta_pat, html_str)
        if m:
            desc = _limpar_ruido_texto(limpar_html(m.group(1)))
            if len(desc) >= 50 and _frase_valida_pt(desc):
                partes.append(desc)

        paragrafos = re.findall(r"(?is)<p [^>]*>(.*?)</p>", html_str)
        for p in paragrafos:
            txt = _limpar_ruido_texto(limpar_html(p))
            if len(txt) >= 50 and _frase_valida_pt(txt):
                if not any(difflib.SequenceMatcher(None, norm(txt), norm(x)).ratio() > 0.72 for x in partes):
                    partes.append(txt)
        if partes:
            return "\n\n".join(partes)[:6500]
        return ""
    except Exception:
        return ""


def fmt_data(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso or ""


def idade(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        diff = datetime.now(dt.tzinfo) - dt
        segundos = int(diff.total_seconds())
        if segundos < 60:
            return "agora mesmo"
        minutos = segundos // 60
        if minutos < 60:
            return f"há {minutos} min" if minutos > 1 else "há 1 min"
        horas = minutos // 60
        if horas < 24:
            return f"há {horas}h" if horas > 1 else "há 1h"
        dias = horas // 24
        if dias == 1:
            return "ontem"
        if dias < 7:
            return f"há {dias} dias"
        return dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return ""


def _db_padrao() -> dict:
    return {
        "noticias": [], "proximo_id": 1, "vistas": [], "posts": [],
        "corretores": json.loads(json.dumps(CORRETORES_PADRAO)),
        "consultas": json.loads(json.dumps(MAPA_CONSULTAS_PADRAO)),
    }


def carregar_db() -> dict:
    db = _db_padrao()
    if DB_FILE.exists():
        try:
            dados = json.loads(DB_FILE.read_text(encoding="utf-8"))
            db.update(dados)
            if "consultas" not in db:
                db["consultas"] = json.loads(json.dumps(MAPA_CONSULTAS_PADRAO))
        except (json.JSONDecodeError, OSError):
            shutil.copy(DB_FILE, DB_FILE.with_suffix(".corrompido.json"))
    return db


def salvar_db(db: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db["vistas"] = db["vistas"][-3000:]
    tmp = DB_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(DB_FILE)


def registrar_post(db: dict, post: dict) -> None:
    db["posts"].insert(0, post)


def obter_post(db: dict, post_id: str):
    return next((p for p in db["posts"] if p["id"] == post_id), None)


def ler_arquivo(post: dict, chave: str) -> bytes | None:
    nome = post["arquivos"].get(chave)
    arq = BASE / post["pasta"] / nome if nome else None
    return arq.read_bytes() if arq and arq.exists() else None


def zip_post(post: dict) -> bytes:
    pasta = (BASE / post["pasta"]).resolve()
    if OUT_DIR.resolve() not in pasta.parents:
        raise ValueError("pasta fora de output/")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(pasta.iterdir()):
            if f.is_file():
                z.write(f, f.name)
    return buf.getvalue()


def apagar_post(db: dict, post_id: str) -> None:
    post = obter_post(db, post_id)
    if not post:
        return
    pasta = (BASE / post["pasta"]).resolve()
    if OUT_DIR.resolve() in pasta.parents:
        shutil.rmtree(pasta, ignore_errors=True)
    db["posts"] = [p for p in db["posts"] if p["id"] != post_id]


def textwrap_paragrafos(texto: str) -> list[str]:
    return [p.strip() for p in (texto or "").split("\n\n") if p.strip()]


def _extrair_pontos_naturais(texto: str, titulo: str = "", limite: int = 4) -> list[str]:
    texto_limpo = _limpar_ruido_texto(texto)
    if not texto_limpo:
        return []
    titulo_norm = norm(titulo)
    frases_brutas = [
        _limpar_ruido_texto(f)
        for f in re.split(r"(?<=[.!?])\s+", texto_limpo)
        if norm(_limpar_ruido_texto(f)) != titulo_norm
    ]
    unicas: list[str] = []
    for f in frases_brutas:
        if not _frase_valida_pt(f, titulo):
            continue
        f_norm = _normalizar_frase_pt(f, ponto_final=True)
        fn = norm(f_norm)
        if any(difflib.SequenceMatcher(None, fn, norm(u)).ratio() > 0.70 or fn in norm(u) or norm(u) in fn for u in unicas):
            continue
        unicas.append(f_norm)
        if len(unicas) >= limite:
            break
    return unicas[:limite]


def _redacao_jornalistica_fallback(titulo: str, fonte: str, categoria: str, texto_materia: str, resumo_rss: str) -> dict:
    titulo_norm = norm(titulo)
    base_real = ""
    for cand in (texto_materia, resumo_rss):
        limpo = _limpar_ruido_texto(cand)
        if limpo and len(limpo) >= 40 and norm(limpo) != titulo_norm:
            base_real = limpo
            break

    pontos = _extrair_pontos_naturais(base_real, titulo, limite=4) if base_real else []

    if not pontos and base_real:
        pontos = _extrair_pontos_naturais(base_real, titulo, limite=3)
    if not pontos:
        pontos = [
            _normalizar_frase_pt(f"Detalhe extraído diretamente da matéria original de {fonte}."),
            _normalizar_frase_pt("Informação apurada e documentada no corpo do texto da notícia."),
        ]

    destaque = _normalizar_frase_pt(titulo, ponto_final=False).upper()
    resumo_gerado = _cortar_em_frase_completa(base_real or titulo, max_chars=360)
    
    legenda_feed = (
        f"{titulo}\n\n"
        f"{resumo_gerado}\n\n"
        f"Fonte: {fonte}\n\n"
        "💬 Quer avaliar como esse movimento impacta o seu próximo passo imobiliário? Converse com a nossa equipe."
    )
    legenda_reel = (
        f"{titulo}\n\n"
        f"{pontos[0]}\n\n"
        "💬 Fale com os especialistas da Be.Smart Imóveis."
    )
    return {
        "destaque": destaque,
        "resumo": resumo_gerado,
        "pontos": pontos,
        "cta_reel": "Quer entender como essa notícia impacta os seus planos imobiliários?",
        "legenda_feed": legenda_feed,
        "legenda_reel": legenda_reel,
    }


def nova_noticia(db: dict, dados: dict) -> dict:
    titulo = dados.get("titulo", "").strip()
    titulo_norm = norm(titulo)
    url_orig = dados.get("url", "").strip()
    url_resolvida = _resolver_url_google_news(url_orig) if url_orig else ""
    resumo_rss = _limpar_ruido_texto(dados.get("resumo", "").strip())
    
    destaque = _normalizar_frase_pt(titulo, ponto_final=False).upper()

    pontos = [p for p in (dados.get("pontos") or []) if _frase_valida_pt(p, titulo)]
    legenda_feed = dados.get("legenda_feed", "").strip()
    legenda_reel = dados.get("legenda_reel", "").strip()
    cta_reel = dados.get("cta_reel", "").strip()
    fonte = dados.get("fonte", "Imprensa").strip()
    categoria = dados.get("categoria", "Mercado regional")

    texto_materia = extrair_texto_url(url_resolvida or url_orig) if (url_resolvida or url_orig) else ""
    resumo_base = resumo_rss if resumo_rss and norm(resumo_rss) != titulo_norm else ""

    if ia_disponivel():
        try:
            sug = ia_sugerir(
                {
                    "titulo": titulo,
                    "categoria": categoria,
                    "resumo": resumo_rss,
                    "fonte": fonte,
                    "url": url_resolvida or url_orig,
                },
                texto_materia=texto_materia or resumo_rss,
            )
            if sug:
                resumo_base = sug.get("resumo", "") or resumo_base
                pontos = sug.get("pontos", []) or pontos
                legenda_feed = sug.get("legenda_feed", "") or legenda_feed
                legenda_reel = sug.get("legenda_reel", "") or legenda_reel
                cta_reel = sug.get("cta_reel", "") or cta_reel
        except Exception:
            pass

    if not resumo_base or _eh_boilerplate(resumo_base) or norm(resumo_base) == titulo_norm:
        fb = _redacao_jornalistica_fallback(titulo, fonte, categoria, texto_materia, resumo_rss)
        resumo_base = fb["resumo"]
        pontos = pontos or fb["pontos"]
        cta_reel = cta_reel or fb["cta_reel"]
        legenda_feed = legenda_feed or fb["legenda_feed"]
        legenda_reel = legenda_reel or fb["legenda_reel"]
    else:
        resumo_base = _normalizar_frase_pt(resumo_base, ponto_final=True)
        if not pontos:
            pontos = _extrair_pontos_naturais(texto_materia or resumo_base, titulo, limite=4)
        if not legenda_feed:
            legenda_feed = f"{titulo}\n\n{resumo_base}\n\n💬 Quer entender como isso afeta os seus planos? Fale com a nossa equipe."
        if not legenda_reel:
            legenda_reel = f"{titulo}\n\n💬 Fale com a nossa equipe da Be.Smart Imóveis."

    item = {
        "id": db["proximo_id"],
        "categoria": categoria,
        "titulo": titulo,
        "destaque": destaque.strip(),
        "resumo": resumo_base.strip(),
        "conteudo": texto_materia[:5000],
        "pontos": pontos,
        "fonte": fonte,
        "url": url_resolvida or url_orig,
        "data": dados.get("data") or datetime.now().isoformat(timespec="seconds"),
        "status": "Rascunho",
        "legenda_feed": legenda_feed,
        "legenda_reel": legenda_reel,
        "cta_reel": cta_reel,
        "hashtags": [],
        "foto_seed": random.randint(1, 100000),
        "uid": dados.get("uid") or hashlib.md5(url_orig.encode()).hexdigest()[:12],
    }
    db["proximo_id"] += 1
    db["noticias"].append(item)
    if item["uid"] not in db["vistas"]:
        db["vistas"].append(item["uid"])
    return item


def marcar_vista(db: dict, uid: str) -> None:
    if uid not in db["vistas"]:
        db["vistas"].append(uid)


def salvar_foto_corretor(nome: str, dados: bytes) -> str:
    pasta = DATA_DIR / "corretores"
    pasta.mkdir(parents=True, exist_ok=True)
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(dados))).convert("RGB")
    img = ImageOps.fit(img, (400, 400), Image.Resampling.LANCZOS)
    arq = f"{slug(nome)}.png"
    img.save(pasta / arq)
    return arq


_HTTP_CACHE: dict[str, tuple[float, bytes]] = {}
_HTTP_FALHAS: dict[str, float] = {}


def baixar(url: str, ttl: int = 900, timeout: int = 15, extra_headers: dict | None = None) -> bytes:
    agora = time.time()
    c = _HTTP_CACHE.get(url)
    if c and agora - c[0] < ttl:
        return c[1]

    if agora - _HTTP_FALHAS.get(url, 0) < 5:
        raise OSError("falha recente neste endereço")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if extra_headers:
        headers.update(extra_headers)

    tentativas = 3
    dados = None
    for tentativa in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                dados = r.read()
            break
        except Exception as e:
            err_str = str(e)
            if "429" in err_str and tentativa < tentativas - 1:
                time.sleep(2.0 * (tentativa + 1))
                continue
            if tentativa == tentativas - 1:
                _HTTP_FALHAS[url] = agora
                raise RuntimeError(f"Erro ao acessar a fonte: {err_str}")

    _HTTP_CACHE[url] = (agora, dados)
    return dados


JANELAS = {"Últimas 24 horas": "1d", "Últimos 3 dias": "3d", "Últimos 7 dias": "7d"}

_CAT_REGEX = {
    "Juros e financiamento": ["juros", "selic", "financiamento", "taxa", "copom", "credito imobiliario"],
    "Bancos e crédito": ["banco", "caixa", "bradesco", "itau", "santander", "poupanca", "fgts"],
    "Lançamentos imobiliários": ["lancamento", "incorporador", "construtora", "empreendimento", "cyrela", "mrv", "direcional", "tenda"],
    "Valorização de bairros": ["valorizacao", "bairro", "m2", "metro quadrado", "preco medio", "fipezap", "niteroi", "icarai", "vila olimpia", "moema", "itaim bibi", "pinheiros", "jardins"],
    "Investimento imobiliário": ["investimento", "imovel comercial", "imovel residencial"],
    "Economia": ["inflacao", "pib", "economia", "ipca", "dolar"],
    "Legislação": [r"lei\b", "stf", "stj", "projeto de lei", "regulament", "tribut", "itbi", "reforma"],
    "Infraestrutura": ["obra", "infraestrutura", "metro", "saneamento", "rodovia", "mobilidade"],
    "Mercado regional": ["rio de janeiro", "niteroi", "regiao metropolitana", "rj", "sao paulo", "sp", "vila olimpia", "moema", "itaim bibi", "pinheiros", "jardins"],
    "Conteúdo educativo": [r"como\b", "dicas", "guia", "entenda", "saiba"],
}

_NEGATIVAS = [
    "incendio", "policia", "preso", "assalto", "crime", "vitima", "acidente",
    "bombeiro", "chuva", "desabamento", "trafico", "tiroteio", "morte",
    "assassinato", "roubo", "furto", "golpe", "borracharia", "vitimas", "prisao",
    "homicidio", "sequestro", "operacao policial", "delegacia", "ifix", "fii", "mcc11",
    "naval", "estaleiro", "navio", "marinha", "aeronautica", "automotivo", "veiculos",
    "futebol", "politica", "eleicoes", "criptomoeda", "bitcoin"
]

_TERMOS_OBRIGATORIOS = [
    "imovel", "imoveis", "imobiliari", "habitacao", "aluguel", "condominio",
    "construtora", "incorporadora", "financiamento", "lancamento", "metro quadrado", "fipezap"
]


def eh_imobiliario(titulo: str, resumo: str = "", consultas_ativas: list[str] = None) -> bool:
    t = norm(f"{titulo} {resumo}")
    if any(neg in t for neg in _NEGATIVAS):
        return False
    if "construtora" in t or "construcao" in t:
        if any(naval in t for naval in ["naval", "estaleiro", "navio", "marinha"]):
            return False
    if any(termo in t for termo in _TERMOS_OBRIGATORIOS):
        return True
    return False


def classificar(titulo: str, resumo: str = "") -> str:
    t = norm(f"{titulo} {resumo}")
    melhor, pontos = "Mercado regional", 0
    for cat, kws in _CAT_REGEX.items():
        n = sum(1 for k in kws if re.search(r"\b" + k, t))
        if n > pontos:
            melhor, pontos = cat, n
    return melhor


def url_feed(consulta: str, janela: str) -> str:
    q = urllib.parse.quote_plus(f"{consulta} when:{janela}")
    return f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def _tx(item, tag: str) -> str:
    n = item.find(tag)
    return (n.text or "").strip() if n is not None and n.text else ""


def parse_feed(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    saida = []
    for it in root.iter("item"):
        titulo, link = _tx(it, "title"), _tx(it, "link")
        if not titulo or not link:
            continue
        src = it.find("source")
        fonte = (src.text or "").strip() if src is not None and src.text else ""
        if fonte and titulo.endswith(f" - {fonte}"):
            titulo = titulo[: -len(fonte) - 3].strip()
        elif " - " in titulo:
            titulo, f2 = titulo.rsplit(" - ", 1)
            fonte = fonte or f2.strip()
        desc = _limpar_ruido_texto(limpar_html(_tx(it, "description")))
        resumo = ""
        if len(desc) >= 40 and not (norm(titulo) in norm(desc) and len(desc) < len(titulo) + len(fonte) + 25):
            resumo = desc
        try:
            data = parsedate_to_datetime(_tx(it, "pubDate")).astimezone().isoformat(timespec="seconds")
        except (TypeError, ValueError):
            data = ""
        saida.append({"titulo": titulo, "fonte": fonte or "Imprensa", "url": link, "resumo": resumo, "data": data})
    return saida


def deduplicar(lista: list[dict]) -> list[dict]:
    saida, normas = [], []
    for n in lista:
        tn = norm(n["titulo"])
        if any(difflib.SequenceMatcher(None, tn, o).ratio() > 0.82 for o in normas):
            continue
        normas.append(tn)
        saida.append(n)
    return saida


def varrer(consultas_selecionadas: list[str], mapa_consultas: dict, janela: str = "1d", ignorar=(), limite: int = 40):
    selecionadas = [c for c in consultas_selecionadas if c in mapa_consultas]
    if not selecionadas:
        selecionadas = list(mapa_consultas.keys())

    pedidos = [(nome, url_feed(mapa_consultas[nome], janela)) for nome in selecionadas]

    brutos, erros = [], []
    for nome, url in pedidos:
        try:
            time.sleep(1.8)
            itens = parse_feed(baixar(url))
            brutos += itens
        except Exception as e:
            erros.append(f"[{nome}] {e}")

    vistos_urls, unicos = set(), []
    for n in brutos:
        uid = n.get("uid") or hashlib.md5(n["url"].encode()).hexdigest()[:12]
        n["uid"] = uid
        if uid not in vistos_urls:
            vistos_urls.add(uid)
            unicos.append(n)

    relevantes = [n for n in unicos if eh_imobiliario(n["titulo"], n["resumo"], selecionadas)]
    relevantes.sort(key=lambda n: n["data"], reverse=True)
    finais = deduplicar(relevantes)[:limite]

    for n in finais:
        n["categoria"] = classificar(n["titulo"], n.get("resumo", ""))

    vistas_count = sum(1 for n in finais if n["uid"] in set(ignorar))
    stats = {"coletadas": len(unicos), "relevantes": len(relevantes), "ja_vistas": vistas_count, "exibidas": len(finais)}
    return finais, erros, stats


_BOILERPLATE_PONTOS = (
    "fatos apurados diretamente por",
    "repercussao estrategica para o mercado imobiliario",
    "cobertura jornalistica abrangente",
    "agregada de fontes do mundo inteiro",
    "analise veiculada pelo",
)


def pontos_do_item(item: dict) -> list[str]:
    titulo_norm = norm(item.get("titulo", ""))
    pts = [
        _normalizar_frase_pt(_limpar_ruido_texto(p), ponto_final=True)
        for p in item.get("pontos") or []
        if _frase_valida_pt(p, item.get("titulo", ""))
        and norm(p) != titulo_norm
        and not any(b in norm(p) for b in _BOILERPLATE_PONTOS)
    ]
    if len(pts) >= 3:
        return pts[:4]
    texto_extra = _limpar_ruido_texto(item.get("conteudo") or "")
    if not texto_extra and item.get("url"):
        texto_extra = extrair_texto_url(item["url"])
    combinado = " ".join(x for x in (_limpar_ruido_texto(item.get("resumo", "")), texto_extra) if x)
    naturais = _extrair_pontos_naturais(combinado, item.get("titulo", ""), limite=4)
    for n in naturais:
        if norm(n) != titulo_norm and not any(difflib.SequenceMatcher(None, norm(n), norm(p)).ratio() > 0.70 for p in pts):
            pts.append(n)
        if len(pts) >= 4:
            break
    return pts[:4]


def _fatos_materia(item: dict) -> tuple[str, list[str]]:
    titulo = item.get("titulo", "")
    titulo_norm = norm(titulo)
    resumo = _limpar_ruido_texto(item.get("resumo") or "")
    conteudo = _limpar_ruido_texto(item.get("conteudo") or "")
    if not conteudo and item.get("url"):
        conteudo = extrair_texto_url(item["url"])

    pts = pontos_do_item({**item, "conteudo": conteudo})
    sintese = ""
    if resumo and norm(resumo) != titulo_norm:
        sintese = resumo
    elif conteudo:
        for p in textwrap_paragrafos(conteudo):
            if norm(p) != titulo_norm and len(p) >= 40:
                sintese = p
                break
    if not sintese:
        paragrafos_unicos = [p for p in textwrap_paragrafos(conteudo) if norm(p) != titulo_norm and len(p) >= 30]
        sintese = paragrafos_unicos[0] if paragrafos_unicos else f"Novas perspectivas e análises estratégicas movimentam o setor de acordo com {item.get('fonte', 'o mercado')}."

    fatos_distintos: list[str] = []
    for p in pts:
        limpo = _limpar_ruido_texto(p)
        if not _frase_valida_pt(limpo, titulo) or norm(limpo) == titulo_norm or any(b in norm(limpo) for b in _BOILERPLATE_PONTOS):
            continue
        limpo_norm = _normalizar_frase_pt(limpo, ponto_final=True)
        if any(difflib.SequenceMatcher(None, norm(limpo_norm), norm(f)).ratio() > 0.70 for f in fatos_distintos):
            continue
        fatos_distintos.append(limpo_norm)
        if len(fatos_distintos) >= 4:
            break

    if not fatos_distintos:
        fatos_distintos = [
            _normalizar_frase_pt(f"Detalhe extraído diretamente da matéria original de {item.get('fonte', 'Imprensa')}."),
            _normalizar_frase_pt("Informação apurada e documentada no corpo do texto da notícia."),
        ]
    return _normalizar_frase_pt(sintese, ponto_final=True), fatos_distintos


_HASH_BASE = ["#mercadoimobiliario", "#imoveis", "#investimentoimobiliario", "#corretordeimoveis", "#besmartimoveis"]
_HASH_CAT = {
    "Juros e financiamento": ["#financiamentoimobiliario", "#selic", "#creditoimobiliario"],
    "Bancos e crédito": ["#creditoimobiliario", "#financiamentoimobiliario", "#fgts"],
    "Lançamentos imobiliários": ["#lancamentosimobiliarios", "#construcaocivil", "#imoveisnaplanta"],
    "Valorização de bairros": ["#valorizacaoimobiliaria", "#imoveisrj", "#bairros"],
    "Mercado regional": ["#imoveisrj", "#imoveisniteroi", "#mercadoregional"],
    "Investimento imobiliário": ["#fiis", "#investimentos", "#rendapassiva"],
    "Economia": ["#economia", "#investimentos", "#financaspessoais"],
    "Legislação": ["#direitoimobiliario", "#legislacao", "#itbi"],
    "Infraestrutura": ["#infraestrutura", "#urbanismo", "#mobilidadeurbana"],
    "Conteúdo educativo": ["#dicasimobiliarias", "#comprarimovel", "#primeiroimovel"],
}


def hashtags_padrao(item: dict) -> list[str]:
    if item.get("hashtags"):
        return item["hashtags"]
    return list(dict.fromkeys(_HASH_BASE + _HASH_CAT.get(item.get("categoria", ""), [])))[:10]


def legendas(item: dict, corretores: list[tuple[str, dict]]) -> dict:
    handles = [i["insta"] for _, i in corretores if i.get("insta")] or ["@besmartimoveis"]
    insta = handles[0] if len(handles) == 1 else ", ".join(handles[:-1]) + " e " + handles[-1]
    tags = " ".join(hashtags_padrao(item))
    cta = f"💬 Quer entender como isso afeta os seus planos? Fale com {insta}."
    feed = item.get("legenda_feed") or "\n\n".join(
        x for x in (item["titulo"], item.get("resumo", ""), f"Fonte: {item.get('fonte', '')}", cta) if x
    )
    reel = item.get("legenda_reel") or f"{item['titulo']}\n\n{cta}"
    story = f"Link da matéria para o sticker: {item.get('url', '')}"
    return {"feed": f"{feed}\n\n{tags}", "reel": f"{reel}\n\n{tags}", "story": story}


MODELO_IA = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
_SYS_IA = (
    "Você é um Jornalista Sênior e Editor-Chefe com 20 anos de experiência em grande imprensa impressa e digital, "
    "especializado em economia, negócios e mercado imobiliário brasileiro e internacional (fluente em português e inglês). "
    "Sua missão é ler o texto completo da matéria fornecida, absorver os fatos reais, dados, valores e contextos, "
    "e redigir um LIDE (resumo editorial) cirúrgico, elegante e analítico focado estritamente no conteúdo específico do artigo "
    "(com os fatos, números e acontecimentos singulares daquela notícia), sem NUNCA citar a empresa de imprensa que publicou "
    "e sem NUNCA repetir ou reescrever o título da notícia. "
    "Responda APENAS com um objeto JSON válido, sem markdown."
)


def ia_disponivel() -> bool:
    _carregar_env_local()
    return (bool(os.getenv("ANTHROPIC_API_KEY")) and importlib.util.find_spec("anthropic") is not None) or \
           (bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) and importlib.util.find_spec("google.genai") is not None)


def _extrair_json(txt: str) -> dict:
    txt = re.sub(r"```(?:json)?", "", txt)
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("a IA não devolveu JSON")
    return json.loads(txt[i : j + 1])


def ia_sugerir(item: dict, texto_materia: str = "") -> dict:
    _carregar_env_local()
    texto_limpo = _limpar_ruido_texto(texto_materia)
    if (not texto_limpo or len(texto_limpo) < 120) and item.get("url"):
        texto_limpo = extrair_texto_url(item["url"])

    resumo_limpo = _limpar_ruido_texto(item.get("resumo", ""))
    corpo_referencia = texto_limpo or resumo_limpo

    if not ia_disponivel():
        fb = _redacao_jornalistica_fallback(
            item.get("titulo", ""),
            item.get("fonte", "Imprensa"),
            item.get("categoria", "Mercado regional"),
            texto_limpo,
            resumo_limpo,
        )
        fb["hashtags"] = hashtags_padrao(item)
        return fb

    pedido = (
        f"Título original: {item['titulo']}\n"
        f"Veículo: {item.get('fonte', '')}\n"
        f"Editoria: {item.get('categoria', '')}\n"
        f"TEXTO COMPLETO DA MATÉRIA DE REFERÊNCIA (LEIA E RESUMA DAQUI):\n{corpo_referencia[:6500] or '(conteúdo indisponível)'}\n\n"
        "Com base estritamente na leitura analítica do corpo da matéria, redija o material editorial em JSON com estas chaves exatas:\n"
        '1. "destaque": deixe vazio (o sistema usará o título da matéria);\n'
        '2. "resumo": lide jornalístico sênior em 2 a 3 frases densas e informativas (220 a 380 caracteres) focadas exclusivamente nos fatos singulares e dados deste artigo. É TERMINANTEMENTE PROIBIDO repetir o título, citar o veículo de imprensa ou usar resumos genéricos aplicáveis a outras matérias;\n'
        '3. "pontos": lista com 3 ou 4 tópicos jornalísticos (55 a 105 caracteres cada) para os cards do Reels, detalhando informações técnicas extraídas exclusivamente do corpo da matéria;\n'
        '4. "cta_reel": frase de encerramento consultiva e elegante (50 a 85 caracteres) conectando o tema da matéria a uma decisão prática de compra, financiamento ou investimento imobiliário;\n'
        '5. "legenda_feed": legenda jornalística completa e detalhada para Instagram Feed estruturada em 3 blocos separados por linha em branco: '
        '(a) gancho editorial baseado no texto; (b) fatos e dados reais extraídos da matéria; '
        '(c) convite consultivo para falar com a equipe da Be.Smart Imóveis. Não inclua hashtags nesta chave;\n'
        '6. "legenda_reel": legenda curta e fiel à matéria para Instagram Reels (2 parágrafos curtos + chamada para ação), sem hashtags;\n'
        '7. "hashtags": lista de 8 hashtags relevantes em minúsculas, sem acentos, começando com #.'
    )

    txt = ""
    erro_ultimo = None

    if bool(os.getenv("ANTHROPIC_API_KEY")) and importlib.util.find_spec("anthropic") is not None:
        try:
            import anthropic
            msg = anthropic.Anthropic().messages.create(
                model=MODELO_IA, max_tokens=1600, system=_SYS_IA,
                messages=[{"role": "user", "content": pedido}],
            )
            txt = "".join(b.text for b in msg.content if b.type == "text")
        except Exception as e:
            erro_ultimo = e

    if not txt and bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) and importlib.util.find_spec("google.genai") is not None:
        try:
            from google import genai
            client = genai.Client()
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=f"{_SYS_IA}\n\n{pedido}",
            )
            txt = response.text or ""
        except Exception as e:
            erro_ultimo = e

    if not txt:
        if erro_ultimo:
            raise RuntimeError(f"Falha na redação por IA: {erro_ultimo}")
        fb = _redacao_jornalistica_fallback(
            item.get("titulo", ""),
            item.get("fonte", "Imprensa"),
            item.get("categoria", "Mercado regional"),
            texto_limpo,
            resumo_limpo,
        )
        fb["hashtags"] = hashtags_padrao(item)
        return fb

    dados = _extrair_json(txt)
    titulo_norm = norm(item.get("titulo", ""))
    pontos_brutos = [str(p).strip() for p in dados.get("pontos", []) if str(p).strip()]
    pontos_validos = [
        _normalizar_frase_pt(p, ponto_final=True)
        for p in pontos_brutos
        if _frase_valida_pt(p, item.get("titulo", "")) and norm(p) != titulo_norm and not any(b in norm(p) for b in _BOILERPLATE_PONTOS)
    ][:4]
    if not pontos_validos:
        _, pontos_validos = _fatos_materia({**item, "conteudo": corpo_referencia})

    resumo_ia = _normalizar_frase_pt(str(dados.get("resumo", "")).strip(), ponto_final=True)
    if not _frase_valida_pt(resumo_ia, item.get("titulo", "")) or norm(resumo_ia) == titulo_norm:
        paragrafos_unicos = [p for p in textwrap_paragrafos(corpo_referencia) if norm(p) != titulo_norm and len(p) >= 40]
        resumo_ia = _normalizar_frase_pt(paragrafos_unicos[0] if paragrafos_unicos else (resumo_limpo if resumo_limpo and norm(resumo_limpo) != titulo_norm else f"Movimentações recentes no setor imobiliário trazem novos horizontes para operadores do mercado de acordo com {item.get('fonte', 'Imprensa')}."), ponto_final=True)

    cta_ia = _normalizar_frase_pt(str(dados.get("cta_reel", "")).strip(), ponto_final=False)[:95]
    tags = [("#" + str(h).lstrip("#").strip().lower()) for h in dados.get("hashtags", []) if str(h).strip()][:10]

    return {
        "destaque": _normalizar_frase_pt(item.get("titulo", ""), ponto_final=False).upper(),
        "resumo": resumo_ia,
        "pontos": pontos_validos,
        "cta_reel": cta_ia,
        "legenda_feed": str(dados.get("legenda_feed", "")).strip(),
        "legenda_reel": str(dados.get("legenda_reel", "")).strip(),
        "hashtags": tags or hashtags_padrao(item),
    }


def _gerar_fundo_vetorial_garantido(item: dict, W: int = 1080, H: int = 1920) -> Image.Image:
    seed_val = abs(int(item.get("id", 1)) * 1331 + int(item.get("foto_seed", random.randint(1, 999999))) * 97) % 999999
    rng = np.random.default_rng(seed_val)

    # Cor lisa sólida completamente aleatória (paleta totalmente livre, sem gradiente e sem esfumaçado)
    r = int(rng.integers(10, 220))
    g = int(rng.integers(10, 220))
    b = int(rng.integers(10, 220))

    img = Image.new("RGB", (W, H), (r, g, b))
    d = ImageDraw.Draw(img, "RGBA")

    # Adição opcional de formas geométricas perfeitamente lisas (sem desfoque)
    tipo_forma = rng.integers(0, 3)
    for _ in range(rng.integers(4, 12)):
        cx = rng.integers(-100, W + 100)
        cy = rng.integers(-100, H + 100)
        raio = rng.integers(100, 500)
        alpha_forma = rng.integers(15, 75)
        cr, cg, cb = int(rng.integers(0, 255)), int(rng.integers(0, 255)), int(rng.integers(0, 255))
        
        if tipo_forma == 0:
            d.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill=(cr, cg, cb, alpha_forma))
        elif tipo_forma == 1:
            coords = [
                (cx, cy),
                (cx + rng.integers(150, 400), cy - rng.integers(100, 250)),
                (cx + rng.integers(200, 500), cy + rng.integers(200, 500)),
                (cx - rng.integers(100, 250), cy + rng.integers(150, 350))
            ]
            d.polygon(coords, fill=(cr, cg, cb, alpha_forma))
        else:
            x1 = rng.integers(-300, W + 300)
            x2 = x1 + rng.integers(300, 900)
            d.line([(x1, 0), (x2, H)], fill=(cr, cg, cb, alpha_forma), width=rng.integers(8, 30))

    return img


def obter_imagem_mestre(item: dict) -> Image.Image:
    global _ULTIMO_AVISO_FUNDO
    FUNDOS_DIR.mkdir(parents=True, exist_ok=True)
    nid = item.get("id", 0)
    seed_tag = item.get("foto_seed", 1)
    chave_cache = hashlib.md5(f"{nid}:{seed_tag}:{item.get('titulo', '')}".encode()).hexdigest()[:14]
    arq_cache = FUNDOS_DIR / f"bg_liso_v1_{nid}_{chave_cache}.jpg"

    if arq_cache.exists():
        try:
            return Image.open(arq_cache).convert("RGB")
        except OSError:
            pass

    img_gerada = _gerar_fundo_vetorial_garantido(item, 1080, 1920)
    try:
        img_gerada.save(arq_cache, format="JPEG", quality=92)
    except OSError:
        pass
    _ULTIMO_AVISO_FUNDO = None
    return img_gerada


def fundo(W: int, H: int, item: dict) -> Image.Image:
    base = obter_imagem_mestre(item)
    return ImageOps.fit(base, (W, H), Image.Resampling.LANCZOS)


@lru_cache(maxsize=64)
def fonte(tam: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    nomes = ["Barlow-Bold.ttf", "Barlow-SemiBold.ttf"] if bold else ["Barlow-Regular.ttf", "Barlow-Medium.ttf"]
    cands = [str(ASSETS / "fonts" / n) for n in nomes] + [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for c in cands:
        try:
            return ImageFont.truetype(c, tam)
        except OSError:
            continue
    return ImageFont.load_default(tam)


def quebrar(draw, texto: str, fnt, largura: int) -> list[str]:
    paragrafos = texto.split("\n")
    todas_as_linhas = []
    for par in paragrafos:
        if not par.strip():
            todas_as_linhas.append("")
            continue
        linhas, atual = [], ""
        for palavra in par.split():
            teste = f"{atual} {palavra}".strip()
            if draw.textlength(teste, font=fnt) <= largura:
                atual = teste
            else:
                if atual:
                    linhas.append(atual)
                atual = palavra
        if atual:
            linhas.append(atual)
        todas_as_linhas.extend(linhas)
    return todas_as_linhas


def ajustar(draw, texto: str, bold: bool, largura: int, altura_max: int, tam_max: int, tam_min: int, entrelinha: float = 1.22):
    tam = tam_max
    while True:
        f = fonte(tam, bold)
        linhas = quebrar(draw, texto, f, largura)
        lh = int(tam * entrelinha)
        if len(linhas) * lh <= altura_max or tam <= tam_min:
            break
        tam -= 2
    max_l = max(1, altura_max // lh)
    if len(linhas) > max_l:
        linhas = linhas[:max_l]
        ultima = linhas[-1].split()
        while ultima and draw.textlength(" ".join(ultima) + "…", font=f) > largura:
            ultima.pop()
        linhas[-1] = " ".join(ultima).rstrip(" ,.;:") + "…"
    return f, linhas, lh


def _cortar(draw, texto: str, fnt, max_w: int) -> str:
    while texto and draw.textlength(texto, font=fnt) > max_w:
        texto = texto[:-2].rstrip() + "…" if not texto.endswith("…") else texto[:-2] + "…"
    return texto


@lru_cache(maxsize=1)
def _logo():
    nomes = [
        "logo.png", "BS - Imóveis Horizontal - Branco - BG Preto.png",
        "BS - Imóveis Horizontal - RGB - BG Branco.png", "logo_oficial.png",
    ]
    for pasta in (ASSETS, BASE):
        for nome in nomes:
            p = pasta / nome
            if not p.exists():
                continue
            try:
                img = Image.open(p).convert("RGBA")
            except OSError:
                continue
            a = np.asarray(img.getchannel("A"))
            selo = False
            if a.min() >= 250:
                rgb = np.asarray(img.convert("RGB")).astype(np.float32)
                cantos = np.array([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]]).mean()
                if cantos < 60:
                    mx = rgb.max(axis=2)
                    alfa = np.clip((mx - 10) * 255 / 245, 0, 255)
                    cor = np.clip(rgb * 255 / np.maximum(mx, 1)[..., None], 0, 255)
                    img = Image.fromarray(np.dstack([cor, alfa]).astype(np.uint8), "RGBA")
                else:
                    selo = True
            if selo:
                dif = ImageChops.difference(img.convert("RGB"), Image.new("RGB", img.size, (255, 255, 255)))
                bbox = dif.convert("L").point(lambda v: 255 if v > 12 else 0).getbbox()
            else:
                bbox = img.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
            return (img.crop(bbox) if bbox else img), selo
    return None, False


def _colar(im: Image.Image, sobre: Image.Image, pos: tuple[int, int]) -> None:
    if im.mode == "RGBA":
        im.alpha_composite(sobre, pos)
    else:
        im.paste(sobre, pos, sobre)


def desenhar_logo(im: Image.Image, posicao: str, largura_desejada: int, y_topo: int | None = None, margem_lat: int = 65) -> int:
    W, H = im.width, im.height
    y = y_topo if y_topo is not None else (200 if H > 1500 else 150)
    logo, selo = _logo()
    if logo is None:
        d = ImageDraw.Draw(im)
        w_txt = d.textlength("be.smart imóveis", font=fonte(40, True))
        x = int((W - w_txt) // 2) if posicao == "centro_alto" else (int(W - w_txt - margem_lat) if posicao == "direita_alto" else margem_lat)
        d.text((x, y), "be.smart imóveis", font=fonte(40, True), fill=WHITE)
        return 60

    h = int(logo.height * largura_desejada / logo.width)
    logo = logo.resize((largura_desejada, h), Image.Resampling.LANCZOS)
    x = (W - largura_desejada) // 2 if posicao == "centro_alto" else (W - largura_desejada - margem_lat if posicao == "direita_alto" else margem_lat)

    if selo:
        pad = 18
        cartao = Image.new("RGBA", (largura_desejada + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(cartao).rounded_rectangle((0, 0, cartao.width - 1, cartao.height - 1), radius=18, fill=WHITE)
        _colar(im, cartao, (x - pad, y - pad))
        _colar(im, logo, (x, y))
        return h + 36
    _colar(im, logo, (x, y))
    return h


def _avatar(nome: str, info: dict, d: int) -> Image.Image:
    S = 4
    mascara = Image.new("L", (d * S, d * S), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, d * S - 1, d * S - 1), fill=255)
    mascara = mascara.resize((d, d), Image.Resampling.LANCZOS)
    foto = DATA_DIR / "corretores" / info.get("foto", "") if info.get("foto") else None
    if foto and foto.exists():
        img = ImageOps.fit(Image.open(foto).convert("RGB"), (d, d), Image.Resampling.LANCZOS)
    else:
        img = Image.new("RGB", (d, d), PURPLE)
        ini = "".join(p[0] for p in nome.split()[:2]).upper()
        ImageDraw.Draw(img).text((d / 2, d / 2), ini, font=fonte(int(d * 0.38), True), fill=WHITE, anchor="mm")
    out = img.convert("RGB").convert("RGBA")
    out.putalpha(mascara)
    return out


def desenhar_corretores_pos(im, corretores, posicao: str, largura: int, y_custom: int | None = None, margem_inferior: int = 150, margem_lat: int = 65) -> tuple[int, int, str, int]:
    d = ImageDraw.Draw(im)
    W, H = im.width, im.height
    linha_h = 104 if H > 1500 else 88
    av = int(linha_h * 0.76)
    f_nome, f_cargo, f_insta = fonte(34, True), fonte(24, True), fonte(21)

    altura_total = len(corretores) * linha_h
    y = y_custom if y_custom is not None else (H - altura_total - margem_inferior)

    tw_max = max(120, largura - av - 22)
    max_txt_w = 0
    for nome, info in corretores:
        w1 = d.textlength(_cortar(d, nome, f_nome, tw_max), font=f_nome)
        w2 = d.textlength(_cortar(d, info.get("cargo", ""), f_cargo, tw_max), font=f_cargo)
        w3 = d.textlength(_cortar(d, info.get("insta", ""), f_insta, tw_max), font=f_insta)
        max_txt_w = max(max_txt_w, int(max(w1, w2, w3)))
    bloco_w = av + 22 + max_txt_w

    x = margem_lat if posicao == "rodape_esquerda" else (W - margem_lat - bloco_w if posicao == "rodape_direita" else (W - bloco_w) // 2)

    for i, (nome, info) in enumerate(corretores):
        top = y + i * linha_h
        _colar(im, _avatar(nome, info, av), (x, top + (linha_h - av) // 2))
        tx = x + av + 22
        ty = top + (linha_h - 88) // 2
        d.text((tx, ty), _cortar(d, nome, f_nome, tw_max), font=f_nome, fill=WHITE)
        d.text((tx, ty + 39), _cortar(d, info.get("cargo", ""), f_cargo, tw_max), font=f_cargo, fill=LILAC)
        d.text((tx, ty + 68), _cortar(d, info.get("insta", ""), f_insta, tw_max), font=f_insta, fill=MUTED)

    return y, y - 28, posicao, x


def compor_post(item, corretores, W, H, topo, base, tam_titulo, tam_corpo, margem=65) -> Image.Image:
    rng = random.SystemRandom()
    dir_arte = {
        "logo": rng.choice(["esquerda_alto", "centro_alto", "direita_alto"]),
        "rodape": rng.choice(["rodape_esquerda", "centro_baixo", "rodape_direita"]),
    }
    lista_corretores = list(corretores.items()) if isinstance(corretores, dict) else list(corretores)

    im = fundo(W, H, item)
    d = ImageDraw.Draw(im)
    x0, largura = margem, W - 2 * margem
    is_story = H > 1500

    h_logo = desenhar_logo(im, dir_arte["logo"], 340 if is_story else 290, y_topo=topo, margem_lat=margem)
    y_corretores_topo, y_fonte_linha, pos_rodape, x_corretor = desenhar_corretores_pos(im, lista_corretores, dir_arte["rodape"], largura, margem_inferior=base, margem_lat=margem)

    y_inicio = topo + h_logo + (50 if is_story else 40)
    y_fim_util = y_fonte_linha - 25
    altura_disponivel = y_fim_util - y_inicio

    destaque = (item.get("destaque") or item["titulo"]).strip()
    f_t, l_t, lh_t = ajustar(d, destaque, True, largura, altura_disponivel, tam_titulo + (18 if is_story else 10), 42 if is_story else 38, 1.20)
    
    bloco_titulo_h = len(l_t) * lh_t
    y = y_inicio + max(0, (altura_disponivel - bloco_titulo_h) // 2)

    for lin in l_t:
        d.text((x0, y), lin, font=f_t, fill=WHITE)
        y += lh_t

    f_fonte = fonte(24 if is_story else 22, True)
    txt_fonte = _cortar(d, f"Fonte: {item.get('fonte', '')}", f_fonte, largura)
    d.text((x_corretor, y_fonte_linha), txt_fonte, font=f_fonte, fill="#A49CB8", anchor="la")
    return im


FPS = 24
REEL_W, REEL_H = 1080, 1920
REEL_LOGO_TOPO = 190
REEL_MARGEM = 75
REEL_FIM = 1580

_ROTULOS_GANCHO = ["NOTÍCIA DO DIA", "RADAR IMOBILIÁRIO", "GIRO DE MERCADO", "ATUALIZAÇÃO DO SETOR", "DESTAQUE IMOBILIÁRIO"]
_CTAS_GERAIS = [
    "Quer transformar essas movimentações do mercado em boas decisões?",
    "Buscando o momento certo para comprar, vender ou investir em imóveis?",
    "Conte com uma assessoria estratégica para os seus próximos passos.",
]
_KICKERS_CTA = ["PRÓXIMO PASSO", "ASSESSORIA BESMART", "ESTRATÉGIA IMOBILIÁRIA", "FALE COM ESPECIALISTAS"]
_SUBTITULOS_CTA = [f"Atendimento personalizado • {MARCA}", f"Consultoria especializada • {MARCA}", f"Sua decisão imobiliária com segurança • {MARCA}"]


def _camada() -> Image.Image:
    return Image.new("RGBA", (REEL_W, REEL_H), (255, 255, 255, 0))


def _cena_gancho(item, reel_topo: int, rng: random.Random) -> Image.Image:
    im = _camada()
    d = ImageDraw.Draw(im)
    x0, larg = REEL_MARGEM, REEL_W - 2 * REEL_MARGEM
    
    y_topo_bloco = reel_topo + 45
    y_fim_bloco = REEL_FIM - 80
    
    rot = rng.choice(_ROTULOS_GANCHO)
    f_rot = fonte(26, True)
    
    f_teste, linhas_teste, lh_teste = ajustar(d, (item.get("destaque") or item["titulo"]).strip(), True, larg, 900, 92, 52, 1.16)
    bloco_altura_total = 52 + 32 + 48 + (len(linhas_teste) * lh_teste) + 30 + 35
    
    y = max(y_topo_bloco, y_topo_bloco + (y_fim_bloco - y_topo_bloco - bloco_altura_total) // 2)

    d.rounded_rectangle((x0, y, x0 + d.textlength(rot, font=f_rot) + 48, y + 52), radius=26, fill=PURPLE)
    d.text((x0 + 24, y + 11), rot, font=f_rot, fill=WHITE)
    y += 76
    d.text((x0, y), item["categoria"].upper(), font=fonte(28, True), fill=LILAC)
    y += 48
    
    for lin in linhas_teste:
        d.text((x0, y), lin, font=f_teste, fill=WHITE)
        y += lh_teste
        
    y += 20
    d.rounded_rectangle((x0, y, x0 + 260, y + 8), radius=4, fill=PURPLE)
    d.text((x0, y + 22), f"{item.get('fonte', '')} • {fmt_data(item.get('data', ''))}", font=fonte(26, True), fill="#A49CB8")
    return im


def _cena_resumo_cta(item, corretores, reel_topo: int, rng: random.Random) -> Image.Image:
    im = _camada()
    d = ImageDraw.Draw(im)
    x0, larg = REEL_MARGEM, REEL_W - 2 * REEL_MARGEM
    lista_c = list(corretores.items()) if isinstance(corretores, dict) else list(corretores)

    resumo_texto = (item.get("resumo") or "").strip()
    frase_cta = (item.get("cta_reel") or "").strip() or rng.choice(_CTAS_GERAIS)
    kicker = rng.choice(_KICKERS_CTA)
    subtitulo = rng.choice(_SUBTITULOS_CTA)

    linha_h = 104
    y_corretores = REEL_FIM - len(lista_c) * linha_h - 15
    y_fonte = y_corretores - 28

    y_topo_bloco = reel_topo + 45
    y_fim_bloco = y_fonte - 25

    f_k = fonte(24, True)
    f_resumo = fonte(35, False)
    
    largura_caixa_texto = larg - 60
    f_cta, linhas_cta, lh_cta = ajustar(d, frase_cta, True, larg - 40, 400, 52, 34, 1.18)
    f_sub = fonte(23, True)

    linhas_resumo = quebrar(d, resumo_texto, f_resumo, largura_caixa_texto)
    bloco_resumo_h = (len(linhas_resumo) * 42) + 36
    bloco_total_h = 46 + 25 + bloco_resumo_h + 30 + (len(linhas_cta) * lh_cta) + 20 + 32
    
    y = max(y_topo_bloco, y_topo_bloco + (y_fim_bloco - y_topo_bloco - bloco_total_h) // 2)

    pill_w = int(d.textlength(kicker, font=f_k)) + 48
    d.rounded_rectangle((x0, y, x0 + pill_w, y + 46), radius=23, fill=(153, 102, 255, 110))
    d.text((x0 + 24, y + 11), kicker, font=f_k, fill=WHITE)
    y += 66

    d.rounded_rectangle((x0, y, x0 + larg, y + bloco_resumo_h), radius=20, fill=(20, 15, 35, 185), outline=(185, 154, 232, 100), width=1)
    
    ty = y + 18
    for lin in linhas_resumo:
        d.text((x0 + 30, ty), lin, font=f_resumo, fill=WHITE)
        ty += 42
    y += bloco_resumo_h + 28

    for lin in linhas_cta:
        d.text((x0, y), lin, font=f_cta, fill=LILAC)
        y += lh_cta
    y += 12
    d.text((x0, y), _cortar(d, subtitulo, f_sub, larg), font=f_sub, fill=MUTED)

    _, _, _, x_corretor_reel = desenhar_corretores_pos(im, lista_c, "rodape_esquerda", larg, y_custom=y_corretores, margem_lat=REEL_MARGEM)
    d.text((x_corretor_reel, y_fonte), f"Fonte da notícia: {item.get('fonte', '')}", font=fonte(24, True), fill="#A49CB8", anchor="la")
    return im


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which("ffmpeg")
        if not exe:
            raise RuntimeError("ffmpeg não encontrado") from None
        return exe


def _dividir(camada: Image.Image):
    return camada.convert("RGB"), camada.getchannel("A")


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def gerar_reel(item, corretores, destino: Path, destino_capa: Path, progresso=None) -> None:
    W, H = REEL_W, REEL_H
    duracoes = [4.5, 6.5]
    marcos = [0.0, duracoes[0], sum(duracoes)]
    total = marcos[-1]

    rng = random.SystemRandom()
    big = fundo(int(W * 1.12), int(H * 1.12), item)
    fixo = _camada()
    h_logo = desenhar_logo(fixo, "centro_alto", 320, y_topo=REEL_LOGO_TOPO, margem_lat=REEL_MARGEM)
    reel_topo = REEL_LOGO_TOPO + h_logo
    fixo_rgb, fixo_a = _dividir(fixo)
    
    cenas = [
        _dividir(c)
        for c in (
            _cena_gancho(item, reel_topo, rng),
            _cena_resumo_cta(item, corretores, reel_topo, rng),
        )
    ]

    cmd = [
        ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-shortest",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-c:a", "aac", "-b:a", "96k", str(destino),
    ]
    def render(i: int) -> Image.Image:
        t = i / FPS
        z = 1.0 + 0.12 * (t / total)
        vw, vh = big.width / z, big.height / z
        x0, y0 = (big.width - vw) / 2, (big.height - vh) / 2
        frame = big.resize((W, H), Image.Resampling.BILINEAR, box=(x0, y0, x0 + vw, y0 + vh))
        frame.paste(fixo_rgb, (0, 0), fixo_a)
        for k, (rgb, a) in enumerate(cenas):
            ini, fim = marcos[k], marcos[k + 1]
            if not (ini <= t < fim):
                continue
            entra = 1.0 if k == 0 else _ease((t - ini) / 0.45)
            sai = 1.0 if k == len(cenas) - 1 else max(0.0, min(1.0, (fim - t) / 0.3))
            mascara = a.point([int(v * entra * sai + 0.5) for v in range(256)])
            frame.paste(rgb, (0, int((1 - entra) * 50)), mascara)
        return frame

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    n_frames = int(total * FPS)
    capa_salva = False
    try:
        with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2)) as ex:
            for ini in range(0, n_frames, 48):
                for i, frame in zip(range(ini, min(n_frames, ini + 48)), ex.map(render, range(ini, min(n_frames, ini + 48)))):
                    if not capa_salva and i / FPS >= 1.0:
                        frame.save(destino_capa)
                        capa_salva = True
                    proc.stdin.write(frame.tobytes())
                if progresso:
                    progresso(min(ini + 48, n_frames) / n_frames)
        proc.stdin.close()
        erro = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg falhou: {erro[-300:]}")
    except (BrokenPipeError, OSError) as e:
        proc.kill()
        raise RuntimeError(f"ffmpeg interrompido: {e}") from e
    finally:
        if proc.poll() is None:
            proc.kill()
    if progresso:
        progresso(1.0)


def gerar_midias(item: dict, corretores: dict | list, progresso=None) -> dict:
    global _ULTIMO_AVISO_FUNDO
    _ULTIMO_AVISO_FUNDO = None

    def p(f, t):
        if progresso:
            progresso(min(f, 1.0), t)

    lista = list(corretores.items()) if isinstance(corretores, dict) else list(corretores)
    agora = datetime.now()
    pasta = OUT_DIR / agora.strftime("%Y-%m-%d") / f"{item['id']:04d}-{slug(item['titulo'])[:40]}-{agora.strftime('%H%M%S')}"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivos, aviso = {}, None

    p(0.01, "Gerando imagem mestre unificada...")
    img_mestre = obter_imagem_mestre(item)
    img_mestre.save(pasta / "imagem_mestre.jpg", quality=92)
    arquivos["imagem_mestre"] = "imagem_mestre.jpg"

    p(0.05, "Montando o Story...")
    compor_post(item, lista, 1080, 1920, topo=200, base=120, tam_titulo=74, tam_corpo=40, margem=65).save(pasta / "story.png", optimize=True)
    arquivos["story"] = "story.png"

    p(0.10, "Montando o Feed...")
    compor_post(item, lista, 1080, 1350, topo=150, base=100, tam_titulo=78, tam_corpo=42, margem=120).save(pasta / "feed.png", optimize=True)
    arquivos["feed"] = "feed.png"

    p(0.15, "Renderizando o Reel (vídeo)...")
    try:
        gerar_reel(item, lista, pasta / "reel.mp4", pasta / "reel_capa.png", lambda f: p(0.15 + 0.82 * f, "Renderizando o Reel (vídeo)..."))
        arquivos["reel"], arquivos["capa"] = "reel.mp4", "reel_capa.png"
    except Exception as e:
        aviso = f"Story e Feed gerados, mas o Reel falhou: {e}"

    if not aviso and _ULTIMO_AVISO_FUNDO:
        aviso = _ULTIMO_AVISO_FUNDO

    leg = legendas(item, lista)
    (pasta / "legendas.txt").write_text(
        f"=== FEED ===\n{leg['feed']}\n\n=== REEL ===\n{leg['reel']}\n\n=== STORY ===\n{leg['story']}\n\n"
        f"=== MATÉRIA ORIGINAL ===\n{item['titulo']}\n{item.get('fonte', '')}\n{item.get('url', '')}\n",
        encoding="utf-8",
    )
    arquivos["legendas"] = "legendas.txt"
    p(1.0, "Pronto!")

    agora_res = agora.isoformat(timespec="seconds")
    return {
        "id": f"{item['id']}-{agora.strftime('%Y%m%d%H%M%S')}", "noticia_id": item["id"], "titulo": item["titulo"],
        "destaque": item.get("destaque", ""), "categoria": item["categoria"],
        "data_geracao": agora_res, "pasta": str(pasta.relative_to(BASE)),
        "arquivos": arquivos, "legendas": leg, "aviso": aviso,
    }