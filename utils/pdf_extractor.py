import re
from dataclasses import dataclass

import pdfplumber

from utils.text_normalizer import normalizar_texto, normalizar_para_comparacao


@dataclass
class ItemOF:
    codigo: str
    descricao: str
    quantidade: float
    unidade: str
    valor_unitario: float
    valor_total: float
    pagina: int = 1
    ordem: int = 0


UNIDADES = (
    "UNIDADE", "UND", "UN", "CX", "CT", "CTO", "PC", "PT", "LT", "L",
    "KG", "GR", "MG", "MT", "M", "M2", "M3", "CM", "CM2", "CM3", "MM",
    "KM", "HM", "DM", "GL", "RL", "PR", "PAR", "JGO", "CJ", "DZ", "MIL",
    "SC", "FR", "TB", "QTD", "AMP", "CV", "W", "V", "A", "ML",
)

_ALT_UNIDADE = "|".join(sorted(UNIDADES, key=len, reverse=True))

RE_CAUDA_QTDE_UND = re.compile(
    r"\s+(?P<quantidade>[\d.,]+)\s+(?P<unidade>" + _ALT_UNIDADE + r")\s+"
    r"(?:R\$\s*)?(?P<valor_unitario>[\d.,]+)\s+(?:R\$\s*)?(?P<valor_total>[\d.,]+)\s*$"
)

RE_CAUDA_UND_QTDE = re.compile(
    r"\s+(?P<unidade>" + _ALT_UNIDADE + r")\s+(?P<quantidade>[\d.,]+)\s+"
    r"(?:R\$\s*)?(?P<valor_unitario>[\d.,]+)\s+(?:R\$\s*)?(?P<valor_total>[\d.,]+)\s*$"
)

PREFIXOS_IGNORAR = (
    "OF-", "ORDEM", "FORNECEDOR", "CONTRATO", "PÁGINA", "PAGINA", "DATA",
    "EMISSÃO", "EMISSAO", "CNPJ", "TOTAL", "RESPONSÁVEL", "RESPONSAVEL",
    "OBSERVA", "PRAZO", "LOCAL", "ENTREGA", "ASSINATURA", "ITEM",
)

CABECALHOS_TABELA = {
    "codigo": ["CÓDIGO", "COD", "CÓDIGO DE BARRAS", "CÓD. ITEM"],
    "descricao": ["DESCRIÇÃO", "DESCRICAO", "PRODUTO", "ESPECIFICAÇÃO", "ITEM"],
    "quantidade": ["QUANTIDADE", "QTDE", "QTD"],
    "unidade": ["UND", "UNIDADE", "UN", "UM"],
    "valor_unitario": ["VALOR UNITÁRIO", "VALOR UNIT", "PREÇO UNIT", "PRECO UNIT", "VALOR UND", "VLR. UNIT."],
    "valor_total": ["VALOR TOTAL", "TOTAL", "VALOR", "VLR. TOTAL"],
}


def parsear_numero(texto) -> float:
    if texto is None:
        return 0.0
    t = re.sub(r"[^\d.,-]", "", str(texto))
    if not t:
        return 0.0
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "").replace(".", "")
    elif "," in t:
        t = t.replace(",", ".")
    elif "." in t:
        partes = t.split(".")
        if len(partes) != 2 or len(partes[1]) != 2:
            t = t.replace(".", "")
    try:
        return round(float(t), 2)
    except ValueError:
        return 0.0


def _primeiro_token_invalido(linha: str) -> bool:
    if not linha:
        return True
    token = linha.split(maxsplit=1)[0]
    if not any(ch.isdigit() for ch in token):
        return True
    return any(token.startswith(p) for p in PREFIXOS_IGNORAR)


def _montar_item(linha_norm: str) -> ItemOF:
    for regex in (RE_CAUDA_QTDE_UND, RE_CAUDA_UND_QTDE):
        m = regex.search(linha_norm)
        if not m:
            continue
        prefixo = linha_norm[: m.start()].strip()
        if not prefixo or _primeiro_token_invalido(prefixo):
            continue
        partes = prefixo.split(maxsplit=1)
        codigo, descricao = partes[0], (partes[1] if len(partes) > 1 else "")
        if not descricao:
            continue
        return ItemOF(
            codigo=codigo,
            descricao=descricao,
            quantidade=parsear_numero(m.group("quantidade")),
            unidade=m.group("unidade"),
            valor_unitario=parsear_numero(m.group("valor_unitario")),
            valor_total=parsear_numero(m.group("valor_total")),
        )
    return None


def _parsear_linhas(texto: str) -> list:
    itens = []
    buffer = []
    ordem = 0
    for linha_bruta in texto.splitlines():
        linha = normalizar_texto(linha_bruta)
        if not linha or _primeiro_token_invalido(linha):
            continue
        buffer.append(linha)
        tentativa = " ".join(buffer)
        item = _montar_item(tentativa)
        if item:
            item.ordem = ordem
            ordem += 1
            itens.append(item)
            buffer = []
        elif len(buffer) > 12:
            buffer.pop(0)
    return itens


def _alias_casa(an: str, t: str) -> bool:
    return bool(an) and (an == t or (len(an) >= 5 and an in t))


def _extrair_tabela_pagina(pagina) -> list:
    try:
        tabela = pagina.extract_table()
    except Exception:
        return None
    if not tabela:
        return None

    melhor = -1
    linha_cab = None
    for i, linha in enumerate(tabela[:10]):
        achados = 0
        for cell in linha:
            if not cell:
                continue
            t = normalizar_para_comparacao(cell)
            for aliases in CABECALHOS_TABELA.values():
                if any(_alias_casa(normalizar_para_comparacao(a), t) for a in aliases):
                    achados += 1
                    break
        if achados > melhor:
            melhor = achados
            linha_cab = i
    if melhor < 2 or linha_cab is None:
        return None

    mapa_col = {}
    for j, cell in enumerate(tabela[linha_cab]):
        if not cell:
            continue
        t = normalizar_para_comparacao(cell)
        for alvo, aliases in CABECALHOS_TABELA.items():
            if any(_alias_casa(normalizar_para_comparacao(a), t) for a in aliases):
                mapa_col[alvo] = j
                break
    if "codigo" not in mapa_col and "descricao" not in mapa_col:
        return None

    itens = []
    for linha in tabela[linha_cab + 1:]:
        def cel(alvo):
            j = mapa_col.get(alvo)
            if j is None or j >= len(linha):
                return ""
            return (linha[j] or "").strip()

        codigo = normalizar_texto(cel("codigo"))
        descricao = normalizar_texto(cel("descricao"))
        if not codigo and descricao and itens:
            itens[-1]["descricao"] += " " + descricao
            continue
        if not descricao:
            continue
        itens.append({
            "codigo": codigo,
            "descricao": descricao,
            "quantidade": parsear_numero(cel("quantidade")),
            "unidade": normalizar_texto(cel("unidade")),
            "valor_unitario": parsear_numero(cel("valor_unitario")),
            "valor_total": parsear_numero(cel("valor_total")),
        })
    return itens


def extrair_numero_of(nome_arquivo: str) -> str:
    m = re.search(r"OF[-_ ]?\d+[_-]?\d*", str(nome_arquivo).upper())
    return m.group(0) if m else "OF"


def extrair_texto_pdf(caminho_pdf: str) -> str:
    partes = []
    with pdfplumber.open(caminho_pdf) as pdf:
        for i, pagina in enumerate(pdf.pages, start=1):
            partes.append(f"--- PÁGINA {i} ---\n" + (pagina.extract_text() or ""))
    return "\n".join(partes)


def extrair_itens_pdf(caminho_pdf: str) -> list:
    itens = []
    with pdfplumber.open(caminho_pdf) as pdf:
        for num, pagina in enumerate(pdf.pages, start=1):
            tabela = _extrair_tabela_pagina(pagina)
            if tabela:
                for raw in tabela:
                    raw["pagina"] = num
                    itens.append(ItemOF(**raw))
            else:
                texto = pagina.extract_text() or ""
                for item in _parsear_linhas(texto):
                    item.pagina = num
                    itens.append(item)
    return itens