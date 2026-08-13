from dataclasses import dataclass


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


def extrair_itens_pdf(caminho_pdf: str) -> list:
    raise NotImplementedError("Etapa 2: implementar extração com pdfplumber/pypdf")


def extrair_texto_pdf(caminho_pdf: str) -> str:
    raise NotImplementedError("Etapa 2: implementar extração de texto bruto")