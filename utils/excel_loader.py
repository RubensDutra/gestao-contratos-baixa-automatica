from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

import config
from utils.text_normalizer import normalizar_texto, normalizar_para_comparacao


class ErroPlanilha(Exception):
    pass


@dataclass
class MapaColunas:
    linha_cabecalho: int
    colunas: dict = field(default_factory=dict)

    def letra(self, alvo: str):
        return self.colunas.get(alvo)


@dataclass
class DadosPlanilha:
    caminho: Path
    wb_template: object
    wb_valores: object
    aba_itens: object
    aba_baixas: object
    aba_resumo: object = None
    mapa_itens: MapaColunas = None
    mapa_baixas: MapaColunas = None
    df_itens: pd.DataFrame = None
    df_baixas: pd.DataFrame = None
    lancamentos: list = field(default_factory=list)


def localizar_aba(wb, nomes_alvo: list):
    abas = {ws.title: ws for ws in wb.worksheets}
    for alvo in nomes_alvo:
        if alvo in abas:
            return abas[alvo]
    alvo_norm = normalizar_para_comparacao(nomes_alvo[0])
    for titulo, ws in abas.items():
        if normalizar_para_comparacao(titulo) == alvo_norm:
            return ws
    for titulo, ws in abas.items():
        if alvo_norm in normalizar_para_comparacao(titulo):
            return ws
    return None


def detectar_linha_cabecalho(ws, colunas_alvo: dict, max_linhas: int = None) -> int:
    max_linhas = max_linhas or config.MAX_LINHAS_VARREDURA_CABECALHO
    melhores = []
    for r in range(1, min(max_linhas, ws.max_row) + 1):
        achados = 0
        textos = [normalizar_texto(ws.cell(row=r, column=c).value)
                  for c in range(1, ws.max_column + 1)]
        for valores in colunas_alvo.values():
            for v in valores:
                vn = normalizar_para_comparacao(v)
                if any(vn and (vn == normalizar_para_comparacao(t) or vn in normalizar_para_comparacao(t)) for t in textos if t):
                    achados += 1
                    break
        melhores.append((achados, r))
    melhor = max(melhores, key=lambda x: x[0])
    if melhor[0] >= 2:
        return melhor[1]
    return 1


def mapear_colunas(ws, linha_cabecalho: int, colunas_alvo: dict) -> MapaColunas:
    mapa = MapaColunas(linha_cabecalho=linha_cabecalho)
    for c in range(1, ws.max_column + 1):
        valor = ws.cell(row=linha_cabecalho, column=c).value
        if not valor:
            continue
        texto = normalizar_texto(valor)
        for alvo, aliases in colunas_alvo.items():
            for alias in aliases:
                alias_norm = normalizar_para_comparacao(alias)
                if alias_norm and (alias_norm == normalizar_para_comparacao(texto) or alias_norm in normalizar_para_comparacao(texto)):
                    mapa.colunas[alvo] = ws.cell(row=linha_cabecalho, column=c).column_letter
                    break
    return mapa


def parsear_valor(valor) -> float:
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    t = str(valor).strip().replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return round(float(t), config.PRECISAO_VALOR)
    except ValueError:
        return 0.0


def _extrair_linhas(ws, mapa: MapaColunas, colunas_alvo: dict) -> list:
    linhas = []
    for r in range(mapa.linha_cabecalho + 1, ws.max_row + 1):
        valores = {}
        vazia = True
        for alvo in colunas_alvo:
            letra = mapa.letra(alvo)
            if letra:
                v = ws[f"{letra}{r}"].value
                valores[alvo] = v
                if v is not None and str(v).strip() != "":
                    vazia = False
        if not vazia:
            valores["linha"] = r
            linhas.append(valores)
    return linhas


def extrair_itens(ws, mapa: MapaColunas) -> pd.DataFrame:
    linhas = _extrair_linhas(ws, mapa, config.COLUNAS_ITENS)
    df = pd.DataFrame(linhas)
    if df.empty:
        return pd.DataFrame(columns=["linha", "codigo_barras", "descricao", "preco_unit", "saldo_disponivel"])
    df["preco_unit"] = df["preco_unit"].apply(parsear_valor)
    df = df.rename(columns={
        "codigo_barras": "codigo_barras",
        "descricao": "descricao",
        "preco_unit": "preco_unit",
        "saldo": "saldo_disponivel",
    })
    return df.reset_index(drop=True)


def extrair_baixas(ws, mapa: MapaColunas) -> pd.DataFrame:
    linhas = _extrair_linhas(ws, mapa, config.COLUNAS_BAIXAS)
    df = pd.DataFrame(linhas)
    if df.empty:
        return pd.DataFrame(columns=["linha", "data", "of", "codigo", "descricao", "quantidade", "preco_unit", "valor_total"])
    df["preco_unit"] = df["preco_unit"].apply(parsear_valor)
    df["valor_total"] = df["valor_total"].apply(parsear_valor)
    df = df.rename(columns={
        "data": "data", "of": "of", "codigo": "codigo",
        "descricao": "descricao", "quantidade": "quantidade",
        "preco_unit": "preco_unit", "valor_total": "valor_total",
    })
    return df.reset_index(drop=True)


def carregar_planilha(origem) -> DadosPlanilha:
    if isinstance(origem, (str, Path)):
        caminho = Path(origem)
        if not caminho.exists():
            raise ErroPlanilha(f"Arquivo não encontrado: {caminho}")
        nome = caminho.name
        wb_template = load_workbook(caminho, data_only=False)
        wb_valores = load_workbook(caminho, data_only=True)
    else:
        origem.seek(0)
        wb_template = load_workbook(origem, data_only=False)
        origem.seek(0)
        wb_valores = load_workbook(origem, data_only=True)
        nome = getattr(origem, "name", "planilha.xlsx")
        caminho = Path(nome)

    aba_itens = localizar_aba(wb_template, [config.ABAS["itens"]])
    aba_baixas = localizar_aba(wb_template, [config.ABAS["baixas"]])
    aba_resumo = localizar_aba(wb_template, [config.ABAS["resumo"]])

    if aba_itens is None:
        raise ErroPlanilha(
            f"Aba '{config.ABAS['itens']}' não encontrada. Abas disponíveis: "
            f"{[ws.title for ws in wb_template.worksheets]}"
        )
    if aba_baixas is None:
        aba_baixas = wb_template.active

    linha_cab = detectar_linha_cabecalho(aba_itens, config.COLUNAS_ITENS)
    mapa_itens = mapear_colunas(aba_itens, linha_cab, config.COLUNAS_ITENS)

    linha_cab_b = detectar_linha_cabecalho(aba_baixas, config.COLUNAS_BAIXAS)
    mapa_baixas = mapear_colunas(aba_baixas, linha_cab_b, config.COLUNAS_BAIXAS)

    obrigatorias = ["descricao", "saldo"]
    ausentes = [c for c in obrigatorias if mapa_itens.letra(c) is None]
    if ausentes:
        raise ErroPlanilha(
            f"Colunas obrigatórias não encontradas na aba '{aba_itens.title}': {ausentes}. "
            f"Colunas detectadas: {mapa_itens.colunas}"
        )

    df_itens = extrair_itens(aba_itens, mapa_itens)
    df_baixas = extrair_baixas(aba_baixas, mapa_baixas)

    return DadosPlanilha(
        caminho=caminho,
        wb_template=wb_template,
        wb_valores=wb_valores,
        aba_itens=aba_itens,
        aba_baixas=aba_baixas,
        aba_resumo=aba_resumo,
        mapa_itens=mapa_itens,
        mapa_baixas=mapa_baixas,
        df_itens=df_itens,
        df_baixas=df_baixas,
    )


def totais_contrato(dados: DadosPlanilha) -> dict:
    df = dados.df_itens
    if df.empty:
        return {"valor_total": 0.0, "saldo_total": 0.0}
    valor_total = float((df["preco_unit"].fillna(0) * df["saldo_disponivel"].fillna(0)).sum())
    saldo_total = float(df["saldo_disponivel"].fillna(0).sum())
    return {"valor_total": round(valor_total, 2), "saldo_total": round(saldo_total, 2)}


def salvar_template(dados: DadosPlanilha, destino) -> None:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    dados.wb_template.save(destino)


def exportar_bytes(dados: DadosPlanilha) -> bytes:
    from io import BytesIO

    buf = BytesIO()
    dados.wb_template.save(buf)
    return buf.getvalue()