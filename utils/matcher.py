from dataclasses import dataclass, field

from thefuzz import fuzz

import config
from utils.text_normalizer import normalizar_para_comparacao

STATUS_APROVADO = "aprovado"
STATUS_DUPLICIDADE = "duplicidade"
STATUS_NAO_ENCONTRADO = "nao_encontrado"
STATUS_SALDO_INSUFICIENTE = "saldo_insuficiente"


@dataclass
class ResultadoMatch:
    item_pdf: object
    status: str
    escolhido: dict = None
    candidatos: list = field(default_factory=list)
    sugestoes: list = field(default_factory=list)


def similaridade(a: str, b: str) -> int:
    na, nb = normalizar_para_comparacao(a), normalizar_para_comparacao(b)
    if not na or not nb:
        return 0
    if na == nb:
        return 100
    return max(
        fuzz.ratio(na, nb),
        fuzz.token_set_ratio(na, nb),
        fuzz.partial_ratio(na, nb),
    )


def _candidato(serie) -> dict:
    return {
        "linha": int(serie.get("linha", 0)),
        "codigo_barras": str(serie.get("codigo_barras", "") or ""),
        "descricao": str(serie.get("descricao", "") or ""),
        "preco_unit": round(float(serie.get("preco_unit", 0.0) or 0.0), config.PRECISAO_VALOR),
        "saldo_disponivel": float(serie.get("saldo_disponivel", 0.0) or 0.0),
        "similaridade": 0,
    }


def _sugestoes(item_pdf, df_itens, preco_pdf, top=3) -> list:
    sugestoes = []
    for _, serie in df_itens.iterrows():
        sim = similaridade(item_pdf.descricao, serie.get("descricao", ""))
        if sim >= 60:
            cand = _candidato(serie)
            cand["similaridade"] = sim
            cand["preco_diverge"] = cand["preco_unit"] != preco_pdf
            sugestoes.append(cand)
    sugestoes.sort(key=lambda c: c["similaridade"], reverse=True)
    return sugestoes[:top]


def corresponder_itens(item_pdf, df_itens, limiar=None) -> ResultadoMatch:
    limiar = limiar if limiar is not None else config.FUZZY_LIMIAR_DESCRICAO
    preco_pdf = round(float(item_pdf.valor_unitario or 0.0), config.PRECISAO_VALOR)

    candidatos = []
    for _, serie in df_itens.iterrows():
        preco_plan = round(float(serie.get("preco_unit", 0.0) or 0.0), config.PRECISAO_VALOR)
        if preco_plan != preco_pdf:
            continue
        sim = similaridade(item_pdf.descricao, serie.get("descricao", ""))
        if sim >= limiar:
            cand = _candidato(serie)
            cand["similaridade"] = sim
            candidatos.append(cand)
    candidatos.sort(key=lambda c: c["similaridade"], reverse=True)

    if not candidatos:
        sugestoes = _sugestoes(item_pdf, df_itens, preco_pdf)
        return ResultadoMatch(item_pdf=item_pdf, status=STATUS_NAO_ENCONTRADO, sugestoes=sugestoes)

    if len(candidatos) == 1:
        escolhido = candidatos[0]
        status = STATUS_APROVADO
        if item_pdf.quantidade > escolhido["saldo_disponivel"]:
            status = STATUS_SALDO_INSUFICIENTE
        return ResultadoMatch(
            item_pdf=item_pdf, status=status, escolhido=escolhido, candidatos=candidatos
        )

    return ResultadoMatch(
        item_pdf=item_pdf, status=STATUS_DUPLICIDADE, candidatos=candidatos[:10]
    )


def corresponder_todos(itens_pdf, df_itens) -> list:
    return [corresponder_itens(it, df_itens) for it in itens_pdf]


def resumo(resultados) -> dict:
    contagem = {}
    for r in resultados:
        contagem[r.status] = contagem.get(r.status, 0) + 1
    return contagem