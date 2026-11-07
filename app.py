with st.expander("✨ Assistente Gemini (Gerar dados automaticamente)", expanded=True):
        input_texto_ia = st.text_area("Cole o link ou o texto da notícia do mercado imobiliário:", placeholder="Ex.: https://exame.com/imoveis/... ou cole a matéria aqui.")
        if st.button("✨ Preencher campos com Gemini", type="primary"):
            if not input_texto_ia:
                st.warning("Insira um link ou texto para a IA analisar.")
            else:
                with st.spinner("A inteligência artificial está a estruturar a pílula de mercado..."):
                    try:
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        prompt = f"""
                        Você é um especialista em marketing imobiliário e inteligência de mercado da Be.Smart Imóveis. 
                        Analise o texto/link abaixo e extraia/crie os seguintes campos formatados rigorosamente em JSON puro:
                        - categoria: escolha entre [Juros e financiamento, Bancos e crédito, Lançamentos imobiliários, Valorização de bairros, Mercado regional, Investimento imobiliário, Economia, Legislação, Infraestrutura, Conteúdo educativo]
                        - titulo: Um título interno claro e profissional (máximo 80 caracteres).
                        - destaque: Uma chamada comercial de impacto em LETRAS MAIÚSCULAS para o Story (máximo 40 caracteres).
                        - resumo: Um resumo objetivo e elegante de 1 ou 2 frases explicativas (máximo 150 caracteres).
                        - gancho: Uma pergunta ou chamada rápida para engajamento.
                        - fonte: Nome da fonte original da notícia.

                        Texto base: {input_texto_ia}
                        
                        Retorne APENAS um objeto JSON válido com as chaves: categoria, titulo, destaque, resumo, gancho, fonte.
                        """
                        response = model.generate_content(prompt)
                        texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                        import json
                        dados_ia = json.loads(texto_limpo)
                        
                        st.session_state.ai_titulo = dados_ia.get("titulo", "")
                        st.session_state.ai_destaque = dados_ia.get("destaque", "")
                        st.session_state.ai_resumo = dados_ia.get("resumo", "")
                        st.session_state.ai_gancho = dados_ia.get("gancho", "")
                        st.session_state.ai_fonte = dados_ia.get("fonte", "")
                        if input_texto_ia.startswith("http"):
                            st.session_state.ai_url = input_texto_ia
                        st.success("Campos preenchidos com sucesso pela IA!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao processar com a IA: {e}")