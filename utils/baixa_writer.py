from dataclasses import dataclass
from datetime import date


@dataclass
class Lancamento:
    data: str
    of: str
    codigo: str
    descricao: str
    quantidade: float
    preco_unit: float
    valor_total: float
    linha: int = 0


def aplicar_baixas(dados, escolhas, numero_of="OF"):
    lancamentos = []
    for esc in escolhas:
        linha = esc["linha"]
        qtd = float(esc["quantidade"])
        idx = dados.df_itens.index[dados.df_itens["linha"] == linha]
        if len(idx) != 1:
            continue
        i = idx[0]
        saldo_atual = float(dados.df_itens.at[i, "saldo_disponivel"])
        if saldo_atual <= 0 or qtd > saldo_atual:
            continue
        dados.df_itens.at[i, "saldo_disponivel"] = saldo_atual - qtd
        preco = float(dados.df_itens.at[i, "preco_unit"] or 0.0)
        lancamentos.append(Lancamento(
            data=date.today().strftime("%d/%m/%Y"),
            of=numero_of,
            codigo=str(dados.df_itens.at[i, "codigo_barras"] or ""),
            descricao=str(dados.df_itens.at[i, "descricao"] or ""),
            quantidade=qtd,
            preco_unit=preco,
            valor_total=round(qtd * preco, 2),
            linha=linha,
        ))
    dados.lancamentos.extend(lancamentos)
    return lancamentos


def desfazer_baixas(dados, lancamentos):
    for lanc in lancamentos:
        idx = dados.df_itens.index[dados.df_itens["linha"] == lanc.linha]
        if len(idx) == 1:
            i = idx[0]
            dados.df_itens.at[i, "saldo_disponivel"] = (
                float(dados.df_itens.at[i, "saldo_disponivel"]) + lanc.quantidade
            )
    dados.lancamentos = [l for l in dados.lancamentos if l not in lancamentos]