from pathlib import Path
from datetime import date, datetime
import re
import time

import pandas as pd
import streamlit as st

import config
from utils.baixa_writer import aplicar_baixas, desfazer_baixas, gravar_no_template
from utils.excel_loader import carregar_planilha, totais_contrato, exportar_bytes, ErroPlanilha
from utils.historico import ler_historico, registrar_baixa
from utils.matcher import (
    corresponder_todos,
    resumo,
    STATUS_APROVADO,
    STATUS_DUPLICIDADE,
    STATUS_NAO_ENCONTRADO,
    STATUS_SALDO_INSUFICIENTE,
    adicionar_sinonimo,
)
from utils.pdf_extractor import extrair_itens_pdf, extrair_numero_of

st.set_page_config(page_title="Gestão de Contratos — Baixa Automática", page_icon="📋", layout="wide")

CSS = Path("assets/style.css").read_text(encoding="utf-8")

LABEL_STATUS = {
    STATUS_APROVADO: "✅ Aprovado",
    STATUS_DUPLICIDADE: "⚠️ Duplicidade",
    STATUS_NAO_ENCONTRADO: "❌ Não encontrado",
    STATUS_SALDO_INSUFICIENTE: "⚠️ Saldo insuficiente",
}

BADGE_STATUS = {
    STATUS_APROVADO: "badge-ok",
    STATUS_DUPLICIDADE: "badge-dup",
    STATUS_NAO_ENCONTRADO: "badge-falha",
    STATUS_SALDO_INSUFICIENTE: "badge-saldo",
}


def fmt_moeda(v) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_saldo(v) -> str:
    if v is None:
        return "?"
    return f"{v:g}"


def normalizar_of(valor) -> str:
    texto = re.sub(r"\s+", " ", str(valor or "")).strip().upper()
    m = re.search(r"OF[-_ ]?\d+", texto)
    return m.group(0).replace(" ", "").replace("_", "-") if m else texto


def of_ja_baixada(dados, numero_of) -> bool:
    ofs_existentes = dados.df_baixas.get("of", pd.Series(dtype=object)).dropna()
    return any(normalizar_of(v) == normalizar_of(numero_of) for v in ofs_existentes)


def injetar_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def iniciar_estado() -> None:
    s = st.session_state
    s.setdefault("dados", None)
    s.setdefault("origem_nome", None)
    s.setdefault("totais_originais", None)
    s.setdefault("saldos_sessao", None)
    s.setdefault("fontes_pdf", [])
    s.setdefault("itens_pdf", [])
    s.setdefault("origens", [])
    s.setdefault("resultados", [])
    s.setdefault("escolhas", {})
    s.setdefault("forcados", {})
    s.setdefault("sinonimos_pendentes", {})
    s.setdefault("baixa_aplicada", False)
    s.setdefault("lancamentos", [])
    s.setdefault("planilha_bytes", None)
    s.setdefault("tema", "escuro")


def resetar_processamento() -> None:
    s = st.session_state
    s["fontes_pdf"] = []
    s["itens_pdf"] = []
    s["origens"] = []
    s["resultados"] = []
    s["escolhas"] = {}
    s["forcados"] = {}
    s["sinonimos_pendentes"] = {}
    s["baixa_aplicada"] = False
    s["lancamentos"] = []
    s["planilha_bytes"] = None
    s["dados"].lancamentos = []


def sidebar_planilha() -> None:
    s = st.session_state
    st.sidebar.subheader("📊 Planilha base")
    opcao = st.sidebar.radio("Origem", ["Enviar (.xlsx)", "Pasta data/inputs"], horizontal=True)
    origem = None
    if opcao == "Enviar (.xlsx)":
        up = st.sidebar.file_uploader("CONTROLE_DE_CONTRATO.xlsx", type=["xlsx"])
        if up is not None:
            origem = (up, up.name)
    else:
        padrao = config.PLANILHA_PADRAO
        if padrao.exists():
            st.sidebar.caption(f"Usando: `{padrao.name}`")
            origem = (padrao, padrao.name)
        else:
            st.sidebar.caption("Nenhum arquivo em `data/inputs/`.")
    s["origem_caminho"] = origem[0] if origem is not None and isinstance(origem[0], Path) else None

    if origem is not None and origem[1] != s["origem_nome"]:
        try:
            dados = carregar_planilha(origem[0])
        except ErroPlanilha as e:
            st.sidebar.error(str(e))
            return
        s["dados"] = dados
        s["origem_nome"] = origem[1]
        s["totais_originais"] = totais_contrato(dados)
        s["saldos_sessao"] = {
            "unid": s["totais_originais"]["saldo_total"],
            "valor": s["totais_originais"]["valor_total"],
        }
        resetar_processamento()
        st.sidebar.success(f"Planilha carregada: {len(dados.df_itens)} itens | {origem[1]}")
        ausentes_baixas = [c for c in config.COLUNAS_BAIXAS if c not in dados.mapa_baixas.colunas]
        if ausentes_baixas:
            st.sidebar.warning(
                f"Aba '{dados.aba_baixas.title}': colunas não encontradas — {', '.join(ausentes_baixas)}. "
                "Lançamentos serão gravados apenas nas colunas mapeadas."
            )


def sidebar_pdfs() -> None:
    s = st.session_state
    st.sidebar.subheader("📄 Ordens de Fornecimento (PDF)")
    uploads = st.sidebar.file_uploader("Arquivos PDF da OF", type=["pdf"], accept_multiple_files=True)
    fontes = [(u.name, u) for u in (uploads or [])]

    if config.PDFS_PADRAO.exists():
        with st.sidebar.expander("📁 PDFs em data/inputs"):
            pdfs_pasta = sorted(config.PDFS_PADRAO.glob("*.pdf"))
            if not pdfs_pasta:
                st.caption("Nenhum PDF na pasta.")
            for p in pdfs_pasta:
                if st.checkbox(p.name, key=f"pdf_pasta_{p.name}"):
                    fontes.append((p.name, p))

    chave = "|".join(n for n, _ in fontes)
    if not fontes:
        s["fontes_pdf"] = []
        s["itens_pdf"] = []
        s["origens"] = []
        s["resultados"] = []
        s["escolhas"] = {}
        s["forcados"] = {}
        s["sinonimos_pendentes"] = {}
        s["baixa_aplicada"] = False
        s["lancamentos"] = []
        return

    if chave != s["fontes_pdf"]:
        s["fontes_pdf"] = chave
        itens, origens = [], []
        for nome, fonte in fontes:
            try:
                if hasattr(fonte, "seek"):
                    fonte.seek(0)
                it = extrair_itens_pdf(fonte)
            except Exception as e:
                st.sidebar.error(f"Falha ao ler {nome}: {e}")
                it = []
            itens.extend(it)
            origens.extend([nome] * len(it))
        for idx, it in enumerate(itens):
            it.ordem = idx
        s["itens_pdf"] = itens
        s["origens"] = origens
        if s["dados"] is not None:
            s["resultados"] = corresponder_todos(itens, s["dados"].df_itens)
        s["baixa_aplicada"] = False
        s["lancamentos"] = []
        s["forcados"] = {}
        s["sinonimos_pendentes"] = {}
        st.sidebar.caption(f"{len(itens)} itens lidos dos PDFs")


def render_cards(totais_originais: dict, of_total: float | None) -> None:
    s = st.session_state
    tema = "tema-escuro" if s["tema"] == "escuro" else "tema-claro"
    of_valor = of_total if of_total is not None else 0.0
    of_sub = "—" if of_total is None else f"{len(s['itens_pdf'])} itens na OF"
    saldo_sessao = s.get("saldos_sessao") or {"unid": 0.0, "valor": 0.0}
    valor_contratado = totais_originais.get("valor_contratado", totais_originais.get("valor_total", 0.0))
    baixado_unid = totais_originais["saldo_total"] - saldo_sessao["unid"]
    baixa_sub = (
        "nenhuma baixa nesta sessão"
        if baixado_unid <= 0
        else f"{baixado_unid:,.0f} unid baixadas nesta sessão"
    )
    html = f"""
    <div class="cards {tema}">
      <div class="card card-total">
        <div class="card-label">Valor Total do Contrato</div>
        <div class="card-value">{fmt_moeda(valor_contratado)}</div>
        <div class="card-sub">valor fixo do contrato · saldo inicial: {totais_originais["saldo_total"]:,.0f} unid</div>
      </div>
      <div class="card card-saldo">
        <div class="card-label">Saldo Disponível</div>
        <div class="card-value">{fmt_moeda(saldo_sessao["valor"])}</div>
        <div class="card-sub">{baixa_sub}</div>
      </div>
      <div class="card card-of">
        <div class="card-label">Valor Total da OF Atual</div>
        <div class="card-value">{fmt_moeda(of_valor)}</div>
        <div class="card-sub">{of_sub}</div>
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_badges() -> None:
    s = st.session_state
    if not s["resultados"]:
        return
    contagem = resumo(s["resultados"])
    html = '<div class="status-badges">'
    ordem = [STATUS_APROVADO, STATUS_DUPLICIDADE, STATUS_SALDO_INSUFICIENTE, STATUS_NAO_ENCONTRADO]
    for status in ordem:
        if contagem.get(status, 0) > 0:
            html += f'<span class="badge {BADGE_STATUS[status]}">{LABEL_STATUS[status]}: {contagem[status]}</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _linha_tabela(r, nome_of: str) -> dict:
    it = r.item_pdf
    e = r.escolhido
    linha_mostrada = str((e or {}).get("linha", "—"))
    if r.status == STATUS_DUPLICIDADE:
        escolhas = st.session_state["escolhas"].get(it.ordem, [])
        e = next((c for c in r.candidatos if c["linha"] in escolhas), None) if escolhas else None
        if escolhas:
            linha_mostrada = ", ".join(str(l) for l in escolhas)
    elif r.status == STATUS_NAO_ENCONTRADO:
        forcado = st.session_state["forcados"].get(it.ordem)
        if forcado:
            e = next((c for c in r.sugestoes if c["linha"] == forcado), None)
            linha_mostrada = str(forcado)
    return {
        "OF": nome_of,
        "PDF - Código": it.codigo,
        "PDF - Descrição": it.descricao,
        "PDF - Qtd": f"{it.quantidade:g} {it.unidade}",
        "PDF - Valor Unitário": fmt_moeda(it.valor_unitario),
        "PDF - Total": fmt_moeda(it.valor_total),
        "Planilha - Linha": linha_mostrada,
        "Planilha - Código": (e or {}).get("codigo_barras", "—"),
        "Planilha - Descrição": (e or {}).get("descricao", "—"),
        "Planilha - Saldo": fmt_saldo((e or {}).get("saldo_disponivel")),
        "Similaridade": f"{(e or {}).get('similaridade', 0)}%" if e else "—",
        "Situação": LABEL_STATUS[r.status],
    }


def render_tabela() -> None:
    s = st.session_state
    if not s["resultados"]:
        return
    st.subheader("🔎 Conferência: PDF da OF × Planilha")
    linhas = [_linha_tabela(r, s["origens"][r.item_pdf.ordem]) for r in s["resultados"]]
    df = pd.DataFrame(linhas)
    cores = {
        "✅ Aprovado": "#4caf50",
        "⚠️ Duplicidade": "#ff9800",
        "❌ Não encontrado": "#f44336",
        "⚠️ Saldo insuficiente": "#ff9800",
    }

    def estilo_status(v):
        cor = cores.get(v, "#888")
        return f"color: {cor}; font-weight: 600;"

    estilizado = df.style.map(estilo_status, subset=["Situação"])
    st.dataframe(
        estilizado,
        width="stretch",
        hide_index=True,
        column_config={
            "PDF - Descrição": st.column_config.TextColumn(width="large"),
            "Planilha - Descrição": st.column_config.TextColumn(width="large"),
        },
    )


def render_detalhes() -> None:
    s = st.session_state
    for r in s["resultados"]:
        it = r.item_pdf
        if r.status == STATUS_DUPLICIDADE:
            with st.expander(
                f"⚠️ Duplicidade — marque os grupos/itens para: {it.descricao[:70]}",
                expanded=True,
            ):
                opcoes = {
                    f"Linha {c['linha']} · código {c['codigo_barras']} · saldo {fmt_saldo(c['saldo_disponivel'])} · valor unit. {fmt_moeda(c['preco_unit'])} · sim {c['similaridade']}%"
                    : c["linha"]
                    for c in r.candidatos
                }
                selecionadas = st.multiselect(
                    "Quais grupos/itens descontar? (pode marcar várias)",
                    list(opcoes),
                    key=f"dup_{it.ordem}",
                )
                s["escolhas"][it.ordem] = [opcoes[o] for o in selecionadas]
                st.caption(
                    f"Quantidade do OF aplicada a cada opção marcada: {it.quantidade:g} {it.unidade} — "
                    "gera um lançamento por opção selecionada."
                )
        elif r.status == STATUS_NAO_ENCONTRADO:
            st.error(
                f"Item não encontrado na planilha: **{it.descricao}** "
                f"({it.quantidade:g} {it.unidade} · {fmt_moeda(it.valor_unitario)})"
            )
            if r.sugestoes:
                with st.expander("Possíveis itens próximos (descrição similar, valor divergente)"):
                    st.dataframe(
                        pd.DataFrame(r.sugestoes)[
                            ["linha", "codigo_barras", "descricao", "preco_unit", "saldo_disponivel", "similaridade"]
                        ],
                        width="stretch",
                        hide_index=True,
                    )
                opcoes = [("(não usar — deixar de fora)", None)] + [
                    (
                        f"Linha {sg['linha']} · {sg['descricao'][:45]} · {fmt_moeda(sg['preco_unit'])} "
                        f"· saldo {fmt_saldo(sg['saldo_disponivel'])} · sim {sg['similaridade']}%",
                        sg["linha"],
                    )
                    for sg in r.sugestoes
                ]
                rotulos = [o[0] for o in opcoes]
                escolha = st.selectbox("Corrigir manualmente — usar item da planilha?", rotulos, key=f"forc_{it.ordem}")
                if escolha.startswith("(não usar"):
                    s["forcados"].pop(it.ordem, None)
                    s["sinonimos_pendentes"].pop(it.ordem, None)
                else:
                    linha_escolhida = next(v for r_, v in opcoes if r_ == escolha)
                    s["forcados"][it.ordem] = linha_escolhida
                    sg = next((c for c in r.sugestoes if c["linha"] == linha_escolhida), None)
                    if sg and sg.get("descricao"):
                        salvar = st.checkbox(
                            f"💡 Salvar sinônimo: “{it.descricao[:55]}” = “{sg['descricao'][:55]}”",
                            value=True,
                            key=f"sin_{it.ordem}",
                        )
                        if salvar:
                            s["sinonimos_pendentes"][it.ordem] = (it.descricao, sg["descricao"])
                        else:
                            s["sinonimos_pendentes"].pop(it.ordem, None)
        elif r.status == STATUS_SALDO_INSUFICIENTE:
            e = r.escolhido
            st.warning(
                f"Saldo insuficiente: **{it.descricao}** — OF pede {it.quantidade:g} "
                f"e o saldo na planilha é {e['saldo_disponivel']:g} (linha {e['linha']})."
            )


def sidebar_historico() -> None:
    registros = ler_historico()
    if not registros:
        return
    st.sidebar.divider()
    with st.sidebar.expander("📜 Histórico de baixas"):
        for reg in reversed(registros[-10:]):
            data_hora = reg.get("data_hora", "")[:16].replace("T", " ")
            total = fmt_moeda(reg.get("total_valor", 0.0))
            st.markdown(
                f"**{reg.get('numero_of', 'OF')}** · {reg.get('total_itens', 0)} itens · {total}\n\n"
                f"<small>{data_hora} — {reg.get('arquivo_origem', '')}</small>",
                unsafe_allow_html=True,
            )
            st.divider()


def render_confirmar() -> None:
    s = st.session_state
    if s["baixa_aplicada"]:
        st.success(f"✅ Baixa aplicada: {len(s['lancamentos'])} lançamentos gerados.")
        if s.get("sinonimos_salvos"):
            st.success(f"💡 {s['sinonimos_salvos']} sinônimo(s) adicionado(s) ao sinonimos.txt")
        if s["lancamentos"]:
            df = pd.DataFrame([l.__dict__ for l in s["lancamentos"]])
            st.dataframe(
                df[["data", "of", "codigo", "descricao", "quantidade", "preco_unit", "valor_total", "linha"]],
                width="stretch",
                hide_index=True,
            )
        if s["planilha_bytes"]:
            st.download_button(
                "📥 Salvar planilha atualizada (.xlsx)",
                data=s["planilha_bytes"],
                file_name=f"CONTROLE_DE_CONTRATO_ATUALIZADO_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
            if st.button("💾 Salvar cópia em data/export", width="stretch"):
                destino = config.EXPORT_DIR / f"CONTROLE_DE_CONTRATO_ATUALIZADO_{date.today().isoformat()}.xlsx"
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(s["planilha_bytes"])
                st.success(f"Salvo em: `{destino}`")
            if s.get("origem_caminho"):
                if st.button("💾 Atualizar CONTROLE_DE_CONTRATO.xlsx (com backup)", width="stretch"):
                    origem = s["origem_caminho"]
                    backup_dir = config.DATA_DIR / "backup"
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    backup = backup_dir / f"CONTROLE_DE_CONTRATO_BACKUP_{date.today().isoformat()}_{datetime.now().strftime('%H%M%S')}.xlsx"
                    backup.write_bytes(origem.read_bytes())
                    erro = None
                    for _ in range(3):
                        try:
                            origem.write_bytes(s["planilha_bytes"])
                            erro = None
                            break
                        except PermissionError as e:
                            erro = e
                            time.sleep(1)
                    if erro:
                        st.error(
                            "Não foi possível gravar: o CONTROLE_DE_CONTRATO.xlsx está **aberto no Excel** "
                            "ou sendo sincronizado pelo OneDrive. Feche o arquivo, aguarde a sincronização "
                            "e clique em Atualizar novamente (o backup já foi salvo)."
                        )
                    else:
                        st.success(f"Original atualizado (backup em `{backup}`)")
                        ofs_dir = getattr(config, "OFS_DIR", None) or (config.DATA_DIR / "ofs")
                        ofs_dir.mkdir(parents=True, exist_ok=True)
                        copiadas = []
                        for nome in s.get("origens", []):
                            fonte = config.INPUT_DIR / nome
                            if not fonte.exists():
                                continue
                            destino = ofs_dir / fonte.name
                            cont = 2
                            while destino.exists():
                                destino = ofs_dir / f"{fonte.stem}_{cont}{fonte.suffix}"
                                cont += 1
                            destino.write_bytes(fonte.read_bytes())
                            copiadas.append(destino.name)
                        if copiadas:
                            st.success(f"📄 PDF(s) arquivado(s) em `data/ofs/`: {', '.join(copiadas)}")
        else:
            if st.button("⬇️ Preparar planilha atualizada (preserva layout)", type="primary", width="stretch"):
                gravar_no_template(s["dados"], s["lancamentos"])
                s["planilha_bytes"] = exportar_bytes(s["dados"])
                st.rerun()
        st.caption(
            "O arquivo é o próprio Excel original editado em memória (openpyxl): cores, estilos, "
            "mesclagens, larguras e fórmulas (SUMIFS, IFERROR...) são preservados. "
            "Fórmulas recalculam ao abrir no Excel."
        )
        if st.button("↩️ Desfazer baixa", width="stretch"):
            desfazer_baixas(s["dados"], s["lancamentos"])
            s["saldos_sessao"]["unid"] += sum(l.quantidade for l in s["lancamentos"])
            s["saldos_sessao"]["valor"] += round(sum(l.valor_total for l in s["lancamentos"]), 2)
            s["lancamentos"] = []
            s["baixa_aplicada"] = False
            s["planilha_bytes"] = None
            st.rerun()
        return

    baixaveis = [
        r for r in s["resultados"]
        if r.status == STATUS_APROVADO
        or (r.status == STATUS_DUPLICIDADE and s["escolhas"].get(r.item_pdf.ordem))
        or (r.status == STATUS_NAO_ENCONTRADO and r.item_pdf.ordem in s["forcados"])
    ]
    if not baixaveis:
        st.caption("Nenhum item pronto para baixa — resolva duplicidades e itens não encontrados.")
        return
    total_valor = sum(
        r.item_pdf.quantidade * r.item_pdf.valor_unitario
        * (len(s["escolhas"].get(r.item_pdf.ordem, [1])) if r.status == STATUS_DUPLICIDADE else 1)
        for r in baixaveis
    )
    if st.button(
        f"✅ Confirmar e Dar Baixa ({len(baixaveis)} itens · {fmt_moeda(total_valor)})",
        type="primary",
        width="stretch",
    ):
        escolhas = []
        for r in baixaveis:
            if r.status == STATUS_APROVADO:
                escolhas.append({"linha": r.escolhido["linha"], "quantidade": r.item_pdf.quantidade})
            elif r.status == STATUS_NAO_ENCONTRADO:
                escolhas.append({"linha": s["forcados"][r.item_pdf.ordem], "quantidade": r.item_pdf.quantidade})
            else:
                for linha in s["escolhas"][r.item_pdf.ordem]:
                    escolhas.append({"linha": linha, "quantidade": r.item_pdf.quantidade})
        pendentes_sin = list(s.get("sinonimos_pendentes", {}).values())
        if pendentes_sin:
            adicionados = [adicionar_sinonimo(pdf, plan) for pdf, plan in pendentes_sin]
            s["sinonimos_pendentes"] = {}
            s["sinonimos_salvos"] = sum(adicionados)
        else:
            s["sinonimos_salvos"] = 0
        numero_of = extrair_numero_of(s["origens"][0]) if s["origens"] else "OF"
        if of_ja_baixada(s["dados"], numero_of):
            st.error(
                f"⛔ A OF **{normalizar_of(numero_of)}** já possui baixa registrada na planilha "
                "(aba 'Baixas (Lançamentos)', coluna 'Nº Pedido/NF/OF'). "
                "Para evitar lançamentos duplicados, a baixa foi **cancelada**. "
                "Verifique se o arquivo PDF já foi processado antes."
            )
            return
        s["lancamentos"] = aplicar_baixas(s["dados"], escolhas, numero_of)
        s["saldos_sessao"]["unid"] -= sum(l.quantidade for l in s["lancamentos"])
        s["saldos_sessao"]["valor"] -= round(sum(l.valor_total for l in s["lancamentos"]), 2)
        registrar_baixa(numero_of, s["lancamentos"], s.get("origem_caminho"))
        s["baixa_aplicada"] = True
        st.rerun()


def valor_total_of(itens) -> float:
    total = 0.0
    for it in itens:
        vt = it.valor_total or 0.0
        if vt <= 0:
            vt = (it.quantidade or 0.0) * (it.valor_unitario or 0.0)
        total += vt
    return round(total, 2)


def main() -> None:
    injetar_css()
    iniciar_estado()
    s = st.session_state

    st.sidebar.title("📋 Gestão de Contratos")
    s["tema"] = "escuro" if st.sidebar.toggle("🌙 Tema escuro", value=s["tema"] == "escuro") else "claro"
    st.sidebar.divider()
    sidebar_planilha()
    sidebar_pdfs()
    sidebar_historico()
    st.sidebar.divider()
    if st.sidebar.button("🗑️ Reiniciar sessão", width="stretch"):
        for k in list(s.keys()):
            del s[k]
        st.rerun()

    if s["dados"] is None:
        st.info("👈 Carregue a planilha base (CONTROLE_DE_CONTRATO.xlsx) no menu lateral para começar.")
        return

    st.title("📋 Controle e Baixa Automatizada de Contrato")
    st.caption(f"Planilha: `{s['origem_nome']}`")

    of_total = valor_total_of(s["itens_pdf"]) if s["itens_pdf"] else None
    render_cards(s["totais_originais"], of_total)

    if not s["itens_pdf"]:
        st.info("👈 Carregue o(s) PDF(s) da Ordem de Fornecimento no menu lateral.")
        return

    render_badges()
    render_tabela()
    render_detalhes()
    st.divider()
    render_confirmar()


if __name__ == "__main__":
    main()