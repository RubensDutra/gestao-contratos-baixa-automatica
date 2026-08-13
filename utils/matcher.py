from dataclasses import dataclass


@dataclass
class ResultadoMatch:
    item_pdf: object
    candidatos: list
    status: str
    escolhido: object = None


def corresponder_itens(item_pdf, df_itens, limiar=90) -> ResultadoMatch:
    raise NotImplementedError("Etapa 3: implementar fuzzy match por descrição + valor unitário idêntico")