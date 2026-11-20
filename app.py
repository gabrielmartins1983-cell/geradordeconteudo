"""BeSmart News - painel administrativo (interface).

Fluxo: Varredura -> escolher matérias -> Biblioteca (editar/validar/aprovar)
        -> gerar Story + Reel + Feed + legendas -> baixar / publicar.
Rodar com:  streamlit run app.py
"""
import os
import time

import streamlit as st

import core

st.set_page_config(page_title="BeSmart News | Painel", page_icon="🟣", layout="wide")

try:  
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ.setdefault("ANTHROPIC_API_KEY", st.secrets["ANTHROPIC_API_KEY"])
except Exception:  
    pass

st.markdown(
    """
<style>
@import url('[https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500;600;700&display=swap](https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500;600;700&display=swap)');
html, body, [class*="css"] { font-family: 'Barlow', sans-serif; }
.stApp { background: #090B12; color: #F4F2F7; }
.block-container { padding-top: 2rem; max-width: 1400px; }
.small-muted { color: #B8B5C1; font-size: .9rem; }
.brand { font-size: 1.7rem; font-weight: 600; letter-spacing: -.04em; }
.brand span { color: #9966FF; }
div[data-testid="stMetric"] { background:#11131D; border:1px solid #282333; padding:14px; border-radius:12px; }
.stButton button, .stDownloadButton button { border-radius: 8px; }
hr { border-color: #332744; }
</style>
""",
    unsafe_allow_html=True,
)

if "db" not in st.session_state:
    st.session_state.db = core.carregar_db()
st.session_state.setdefault("descobertas", [])
st.session_state.setdefault("stats_varredura", None)
st.session_state.setdefault("erros_varredura", [])
st.session_state.setdefault("ultimo_post", None)

db = st.session_state.db
corretores = db["corretores"]
consultas = db["consultas"]
ICONE = {"Rascunho": "📝", "Aprovado": "✅", "Gerado": "🎬"}


def salvar():
    core.salvar_db(db)


def esc(txt) -> str:
    return str(txt or "").replace("$", r"\$")


def cheio(fn, *args, **kw):
    try:
        return fn(*args, width="stretch", **kw)
    except TypeError:
        return fn(*args, use_container_width=True, **kw)


st.markdown(
    '<div class="brand">be.smart <span>news</span></div>'
    '<div class="small-muted">INTELIGÊNCIA IMOBILIÁRIA • PAINEL ADMINISTRATIVO</div>',
    unsafe_allow_html=True,
)
st.write("")

with st.sidebar:
    st.markdown("### ⚙️ Corretores")
    sel = st.selectbox("Selecionar corretor", ["➕ Adicionar novo"] + list(corretores))

    if sel == "➕ Adicionar novo":
        with st.form("form_novo_corretor", clear_on_submit=True):
            n_nome = st.text_input("Nome")
            n_cargo = st.text_input("Cargo", value="Corretor Associado")
            n_insta = st.text_input("Instagram", value="@besmartimoveis")
            n_foto = st.file_uploader("Foto (opcional)", type=["png", "jpg", "jpeg"])
            ok = cheio(st.form_submit_button, "💾 Salvar novo corretor")
        if ok:
            n_nome = n_nome.strip()
            if not n_nome:
                st.error("Informe o nome.")
            elif n_nome in corretores:
                st.error("Já existe um corretor com esse nome.")
            else:
                info = {"cargo": n_cargo, "insta": n_insta}
                if n_foto:
                    info["foto"] = core.salvar_foto_corretor(n_nome, n_foto.getvalue())
                corretores[n_nome] = info
                salvar()
                st.rerun()
    else:
        atual = corretores[sel]
        with st.form("form_edita_corretor"):
            e_nome = st.text_input("Nome", value=sel)
            e_cargo = st.text_input("Cargo", value=atual["cargo"])
            e_insta = st.text_input("Instagram", value=atual["insta"])
            e_foto = st.file_uploader("Trocar foto (opcional)", type=["png", "jpg", "jpeg"])
            col_g, col_x = st.columns(2)
            gravar = cheio(col_g.form_submit_button, "💾 Gravar")
            excluir = cheio(col_x.form_submit_button, "🗑️ Excluir")
        if gravar:
            e_nome = e_nome.strip() or sel
            if e_nome != sel and e_nome in corretores:
                st.error("Já existe um corretor com esse nome.")
            else:
                novo = {"cargo": e_cargo, "insta": e_insta, "foto": atual.get("foto", "")}
                if e_foto:
                    novo["foto"] = core.salvar_foto_corretor(e_nome, e_foto.getvalue())
                db["corretores"] = {(e_nome if k == sel else k): (novo if k == sel else v) for k, v in corretores.items()}
                st.session_state.pop("corretores_ativos", None)
                salvar()
                st.rerun()
        if excluir:
            if len(corretores) > 1:
                del corretores[sel]
                st.session_state.pop("corretores_ativos", None)
                salvar()
                st.rerun()
            else:
                st.error("Mantenha pelo menos um corretor.")

    st.divider()
    st.markdown("### 🎯 Corretores nas peças")
    nomes = list(corretores)
    ativos = st.multiselect("Quem aparece (até 3)", nomes, default=nomes[:1], key="corretores_ativos", max_selections=3) or nomes[:1]
    
    st.divider()
    st.markdown("### 🔎 Gerir Assuntos de Busca")
    with st.form("form_novo_assunto", clear_on_submit=True):
        novo_nome = st.text_input("Nome do Assunto", placeholder="Ex: Lançamentos de Luxo")
        novo_termo = st.text_area("Termos de busca do Google", placeholder='Ex: ("imóvel de luxo" OR penthouse) RJ')
        add_assunto = cheio(st.form_submit_button, "➕ Adicionar Assunto")
    if add_assunto:
        novo_nome = novo_nome.strip()
        novo_termo = novo_termo.strip()
        if not novo_nome or not novo_termo:
            st.error("Preencha o nome e os termos de busca.")
        elif novo_nome in consultas:
            st.error("Já existe um assunto com esse nome.")
        else:
            consultas[novo_nome] = novo_termo
            salvar()
            st.success(f"Assunto '{novo_nome}' adicionado!")
            st.rerun()

    if len(consultas) > 1:
        remover_assunto = st.selectbox("Remover assunto", ["Selecione..."] + list(consultas.keys()))
        if remover_assunto != "Selecione..." and st.button("🗑️ Apagar Assunto Selecionado"):
            del consultas[remover_assunto]
            salvar()
            st.rerun()

    st.divider()
    st.caption("✨ IA: " + ("ativa" if core.ia_disponivel() else "desligada (opcional)"))

noticias = db["noticias"]
m1, m2, m3, m4 = st.columns(4)
m1.metric("Na biblioteca", len(noticias))
m2.metric("Rascunhos", sum(1 for n in noticias if n["status"] == "Rascunho"))
m3.metric("Aprovadas", sum(1 for n in noticias if n["status"] == "Aprovado"))
m4.metric("Pacotes gerados", len(db["posts"]))

tab_var, tab_bib, tab_hist = st.tabs(["🔄 Varredura", "📰 Biblioteca", "📚 Publicações"])


def painel_pacote(post: dict, chave: str):
    base = core.slug(post["titulo"])[:40]
    story, feed = core.ler_arquivo(post, "story"), core.ler_arquivo(post, "feed")
    reel, capa = core.ler_arquivo(post, "reel"), core.ler_arquivo(post, "capa")
    if post.get("aviso"):
        st.warning(post["aviso"])
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("📱 Story • 1080×1920")
        if story:
            st.image(story)
            cheio(st.download_button, "📥 Baixar Story", story, file_name=f"story_{base}.png", mime="image/png", key=f"dl_s_{chave}")
    with c2:
        st.caption("🖼️ Feed • 1080×1350 (4:5)")
        if feed:
            st.image(feed)
            cheio(st.download_button, "📥 Baixar Feed", feed, file_name=f"feed_{base}.png", mime="image/png", key=f"dl_f_{chave}")
    with c3:
        st.caption("🎬 Reel • vídeo 1080×1920")
        if reel:
            st.video(reel)
            cheio(st.download_button, "📥 Baixar Reel (MP4)", reel, file_name=f"reel_{base}.mp4", mime="video/mp4", key=f"dl_r_{chave}")
        elif capa:
            st.image(capa)
    with st.expander("📝 Legendas e hashtags (copie e cole no Instagram)"):
        t1, t2, t3 = st.tabs(["Feed", "Reel", "Story"])
        for aba, nome in ((t1, "feed"), (t2, "reel"), (t3, "story")):
            with aba:
                st.text_area("Legenda", post["legendas"][nome], height=230, key=f"leg_{nome}_{chave}", label_visibility="collapsed")
    cheio(st.download_button, "📦 Baixar tudo (.zip)", core.zip_post(post), file_name=f"{base}.zip", mime="application/zip", key=f"dl_z_{chave}")


def gerar(item: dict, escolhidos: list[str]):
    barra = st.progress(0.0, text="Iniciando e criando imagem por IA…")
    try:
        pacote = core.gerar_midias(
            item, {n: corretores[n] for n in escolhidos},
            progresso=lambda f, t: barra.progress(f, text=t),
        )
    except Exception as e:
        barra.empty()
        st.error(f"Não foi possível gerar as mídias: {e}")
        return
    barra.empty()
    core.registrar_post(db, pacote)
    item["status"] = "Gerado"
    salvar()
    st.session_state.ultimo_post = pacote["id"]
    st.rerun()


def editor(item: dict):
    iid, v = item["id"], item.get("v", 0)
    with st.expander("✏️ Editar texto, pontos do Reel e legendas da matéria"):
        key_res = f"res_val_{iid}"
        if key_res not in st.session_state:
            st.session_state[key_res] = item["resumo"]

        st.markdown("**Formatação rápida do Resumo (Story / Feed / Reel):**")
        c_op1, c_op2, _ = st.columns([1.2, 1.2, 3])
        if c_op1.button("📋 Formatar em Tópicos", key=f"btn_top_{iid}"):
            txt_atual = st.session_state[key_res]
            import re
            
            # Divide explicitamente por blocos iniciados por número (ex: 1 -, 2 -, etc.)
            itens_brutos = re.split(r'(?=\b\d+\s*[-–—)]\s*)', txt_atual)
            linhas = []
            for item_b in itens_brutos:
                item_limpo = item_b.strip()
                if item_limpo:
                    item_limpo = re.sub(r'^\d+\s*[-–—)]\s*', '', item_limpo).strip()
                    if item_limpo:
                        linhas.append(item_limpo)
            
            if len(linhas) <= 1:
                partes = [p.strip() for p in txt_atual.replace(';', '.').split('.') if p.strip()]
                linhas = [re.sub(r'^\d+\s*[-–—)]\s*', '', p).strip() for p in partes if p.strip()]

            if not linhas:
                linhas = [txt_atual]

            topicos_fmt = []
            for idx_t, l in enumerate(linhas, 1):
                l_limpa = l.rstrip('.')
                if l_limpa:
                    topicos_fmt.append(f"{idx_t} - {l_limpa}.")
            
            st.session_state[key_res] = "\n".join(topicos_fmt)
            item["resumo"] = st.session_state[key_res]
            salvar()
            st.rerun()
            
        if c_op2.button("📄 Texto Corrido", key=f"btn_corr_{iid}"):
            txt_atual = st.session_state[key_res]
            linhas_limpas = []
            for l in txt_atual.splitlines():
                limpo = l.lstrip("123456789.-) ").strip()
                if limpo:
                    linhas_limpas.append(limpo)
            st.session_state[key_res] = " ".join(linhas_limpas)
            item["resumo"] = st.session_state[key_res]
            salvar()
            st.rerun()

        with st.form(f"form_ed_{iid}_{v}"):
            idx = core.CATEGORIAS.index(item["categoria"]) if item["categoria"] in core.CATEGORIAS else 0
            categoria = st.selectbox("Categoria", core.CATEGORIAS, index=idx)
            destaque = st.text_input("Chamada em destaque (grande na arte)", item["destaque"])
            
            st.markdown("**Resumo (aparece no Story, no Feed e na Cena 2 do Reel)**")
            resumo = st.text_area("Resumo editável", value=st.session_state[key_res], height=160, key=f"txt_area_res_{iid}", label_visibility="collapsed")
            st.session_state[key_res] = resumo

            pontos = st.text_area("Pontos do Reel — um por linha, até 3 (vazio = usa as frases do resumo)", "\n".join(item.get("pontos", [])), height=100)
            cta_reel = st.text_input("CTA do Reel (frase de chamada final no vídeo)", item.get("cta_reel", ""))
            fonte = st.text_input("Fonte (veículo)", item["fonte"])
            leg_feed = st.text_area("Legenda do Feed (vazio = automática)", item.get("legenda_feed", ""), height=130)
            leg_reel = st.text_area("Legenda do Reel (vazio = automática)", item.get("legenda_reel", ""), height=90)
            ok = st.form_submit_button("💾 Salvar alterações", type="primary")
        if ok:
            item.update(
                categoria=categoria, 
                destaque=destaque.strip().upper(), 
                resumo=resumo.strip(), 
                cta_reel=cta_reel.strip(),
                fonte=fonte.strip() or "Imprensa",
                pontos=[p.strip() for p in pontos.splitlines() if p.strip()][:3],
                legenda_feed=leg_feed.strip(), 
                legenda_reel=leg_reel.strip(),
            )
            item["v"] = v + 1
            salvar()
            st.rerun()

        st.markdown("---")
        col_img1, col_img2 = st.columns([2, 1])
        with col_img1:
            st.markdown("**🎨 Imagem de Fundo (Gerada por IA)**")
            st.caption("A IA cria uma imagem de alta resolução com iluminação profissional baseada no contexto desta notícia.")
        with col_img2:
            if st.button("🔄 Solicitar nova imagem", key=f"nova_img_{iid}", type="secondary"):
                item["foto_seed"] = int(time.time())
                item["v"] = v + 1
                salvar()
                st.success("Nova imagem gerada com sucesso! Gere as mídias novamente para aplicar.")
                st.rerun()

        st.markdown("**✨ Sugestão com IA (opcional)**")
        url_ia = st.text_input("URL da matéria (opcional — a IA lê o link se informado)", value=item.get("url", ""), key=f"url_ia_{iid}")
        texto = st.text_area("Ou cole o texto da matéria para a IA resumir com fidelidade", key=f"txt_{iid}", height=110)
        if not core.ia_disponivel():
            st.caption("Para ativar: configure a chave de IA nas variáveis de ambiente.")
        if st.button("✨ Sugerir chamada, resumo, pontos e legendas", key=f"ia_{iid}", disabled=not core.ia_disponivel()):
            with st.spinner("Lendo matéria e consultando a IA…"):
                try:
                    texto_para_ia = texto
                    if url_ia.strip() and not texto.strip():
                        texto_para_ia = core.extrair_texto_url(url_ia.strip())
                    
                    sug = core.ia_sugerir({**item, "url": url_ia.strip() or item.get("url", "")}, texto_para_ia)
                except Exception as e:
                    st.error(f"A IA não respondeu: {e}")
                else:
                    item.update({k: val for k, val in sug.items() if val})
                    if url_ia.strip():
                        item["url"] = url_ia.strip()
                    item["v"] = v + 1
                    salvar()
                    st.rerun()


def card_item(item: dict):
    iid = item["id"]
    with st.container(border=True):
        esq, dir_ = st.columns([3, 2])
        with esq:
            st.caption(f"{ICONE.get(item['status'], '')} {item['status']} • {item['categoria']} • {core.fmt_data(item['data'])}")
            st.markdown(f"**{esc(item['destaque'])}**")
            st.markdown(f"### {esc(item['titulo'])}")
            if item["resumo"]:
                st.write(esc(item["resumo"]))
            else:
                st.warning("Sem resumo. Abra “Editar” e preencha antes de aprovar.")
            if item.get("url"):
                st.markdown(f"🔗 [Abrir matéria original]({item['url']}) • {esc(item['fonte'])}")
        with dir_:
            chave = f"corr_{iid}"
            default_vals = [c for c in ativos if c in corretores]
            if chave in st.session_state:
                val_atual = [c for c in st.session_state[chave] if c in corretores]
                if not val_atual:
                    val_atual = default_vals
            else:
                val_atual = default_vals
            escolhidos = st.multiselect("Corretores nas peças", list(corretores), default=val_atual, key=chave, max_selections=3) or default_vals

            b1, b2, b3 = st.columns(3)
            with b1:
                if item["status"] == "Rascunho":
                    pronto = bool(item["destaque"] and item["resumo"])
                    if cheio(st.button, "✅ Aprovar", key=f"ap_{iid}", disabled=not pronto) and pronto:
                        item["status"] = "Aprovado"
                        salvar()
                        st.rerun()
                elif cheio(st.button, "↩️ Reabrir", key=f"re_{iid}"):
                    item["status"] = "Rascunho"
                    salvar()
                    st.rerun()
            with b2:
                rotulo = "🔁 Gerar de novo" if item["status"] == "Gerado" else "🎬 Gerar 3 mídias"
                livre = item["status"] != "Rascunho"
                if cheio(st.button, rotulo, key=f"gen_{iid}", disabled=not livre) and livre:
                    gerar(item, escolhidos)
            with b3:
                if cheio(st.button, "🗑️ Excluir", key=f"del_{iid}"):
                    db["noticias"] = [n for n in db["noticias"] if n["id"] != iid]
                    salvar()
                    st.rerun()
        editor(item)


with tab_var:
    st.subheader("Varredura de notícias do mercado imobiliário")
    with st.container(border=True):
        cA, cB = st.columns([1, 2])
        janela = cA.selectbox("Período", list(core.JANELAS), index=0)
        assuntos_selecionados = cB.multiselect("Assuntos", list(consultas.keys()), default=list(consultas.keys()))
        if st.button("🔄 Executar varredura", type="primary", disabled=not assuntos_selecionados):
            with st.spinner("Buscando e filtrando matérias…"):
                res, erros, stats = core.varrer(assuntos_selecionados, consultas, core.JANELAS[janela], ignorar=db["vistas"])
            st.session_state.descobertas, st.session_state.erros_varredura, st.session_state.stats_varredura = res, erros, stats

    for e in st.session_state.erros_varredura:
        st.warning(f"Falha ao consultar: {e}")
    s = st.session_state.stats_varredura
    if s:
        st.caption(f"{s['coletadas']} coletadas → {s['relevantes']} do setor imobiliário → {s['exibidas']} exibidas")
    if s and not st.session_state.descobertas:
        st.info("Nada novo neste período. Tente ampliar o período ou use o cadastro manual abaixo.")

    for n in list(st.session_state.descobertas):
        with st.container(border=True):
            st.markdown(f"**[{n['categoria']}]** {esc(n['titulo'])}")
            st.caption(f"{esc(n['fonte'])} • {core.fmt_data(n['data'])} ({core.idade(n['data'])})")
            if n["resumo"]:
                st.write(esc(n["resumo"]))
            st.markdown(f"🔗 [Abrir matéria original]({n['url']})")
            b1, b2, _ = st.columns([1, 1, 3])
            if b1.button("➕ Adicionar", key=f"add_{n['uid']}"):
                core.nova_noticia(db, n)
                salvar()
                st.session_state.descobertas = [x for x in st.session_state.descobertas if x["uid"] != n["uid"]]
                st.rerun()
            if b2.button("🚫 Descartar", key=f"dsc_{n['uid']}"):
                core.marcar_vista(db, n["uid"])
                salvar()
                st.session_state.descobertas = [x for x in st.session_state.descobertas if x["uid"] != n["uid"]]
                st.rerun()

    with st.expander("✍️ Cadastro manual de matéria"):
        with st.form("form_manual", clear_on_submit=True):
            m_cat = st.selectbox("Categoria", core.CATEGORIAS)
            m_tit = st.text_input("Título")
            m_des = st.text_input("Chamada em destaque (vazio = usa o título)")
            m_res = st.text_area("Resumo")
            m_fon = st.text_input("Fonte (veículo)")
            m_url = st.text_input("Link da matéria original", placeholder="https://...")
            enviado = st.form_submit_button("Salvar na biblioteca", type="primary")
        if enviado:
            if m_tit.strip() and m_url.strip():
                core.nova_noticia(db, {
                    "categoria": m_cat, "titulo": m_tit, "destaque": m_des.strip().upper(),
                    "resumo": m_res, "fonte": m_fon, "url": m_url.strip(),
                })
                salvar()
                st.rerun()
            else:
                st.error("Título e link da matéria original são obrigatórios.")


with tab_bib:
    cT1, cT2 = st.columns([3, 1])
    cT1.subheader("Biblioteca de matérias")
    with cT2:
        with st.popover("🗑️ Limpar biblioteca"):
            st.warning("Remove todas as matérias. As mídias já geradas continuam em Publicações.")
            if st.button("Confirmar limpeza", key="conf_limpar"):
                db["noticias"] = []
                salvar()
                st.rerun()

    post_ativo = core.obter_post(db, st.session_state.ultimo_post) if st.session_state.ultimo_post else None
    if post_ativo:
        with st.container(border=True):
            st.markdown(f"### ✅ Pacote pronto: {esc(post_ativo['titulo'])}")
            painel_pacote(post_ativo, "ult")
            if st.button("✖️ Fechar pacote", key="fechar_ult"):
                st.session_state.ultimo_post = None
                st.rerun()
        st.divider()

    filtro = st.selectbox("Filtrar por status", ["Todos", "Rascunho", "Aprovado", "Gerado"])
    exibir = [n for n in reversed(noticias) if filtro == "Todos" or n["status"] == filtro]
    if not exibir:
        st.info("Nenhuma matéria aqui. Use a aba **Varredura** para buscar notícias ou faça um cadastro manual.")
    for item in exibir:
        card_item(item)


with tab_hist:
    st.subheader("📚 Pacotes gerados")
    if not db["posts"]:
        st.info("Nenhum pacote gerado ainda.")
    for p in db["posts"][:30]:
        with st.container(border=True):
            cI, cB = st.columns([4, 1])
            with cI:
                st.markdown(f"**{esc(p['destaque'] or p['titulo'])}**")
                st.caption(f"{p['categoria']} • gerado em {core.fmt_data(p['data_geracao'])} • pasta: `{p['pasta']}`")
                if st.checkbox("👁️ Ver pacote completo", key=f"ver_{p['id']}"):
                    painel_pacote(p, f"h{p['id']}")
            with cB:
                if st.button("🗑️ Apagar pacote", key=f"apg_{p['id']}"):
                    core.apagar_post(db, p["id"])
                    if st.session_state.ultimo_post == p["id"]:
                        st.session_state.ultimo_post = None
                    salvar()
                    st.rerun()