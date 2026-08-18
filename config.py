from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "inputs"
EXPORT_DIR = DATA_DIR / "export"

PLANILHA_PADRAO = INPUT_DIR / "CONTROLE_DE_CONTRATO.xlsx"
PDFS_PADRAO = INPUT_DIR
SINONIMOS_PATH = BASE_DIR / "sinonimos.txt"

ABAS = {
    "itens": "Itens do Contrato",
    "baixas": "Baixas (Lançamentos)",
    "resumo": "Resumo",
}

COLUNAS_ITENS = {
    "codigo_barras": ["CÓDIGO DE BARRAS", "CÓDIGO DE BARRA", "EAN", "CÓDIGO"],
    "descricao": ["DESCRIÇÃO", "DESCRIÇÃO DO ITEM", "DESCRICAO", "PRODUTO", "ITEM"],
    "preco_unit": ["PREÇO UNIT. (R$)", "PREÇO UNIT", "PRECO UNIT", "VALOR UNITÁRIO", "VALOR UNIT", "PRECO UNITARIO"],
    "saldo": ["SALDO DISPONÍVEL (ATUAL)", "SALDO DISPONÍVEL", "SALDO ATUAL", "SALDO", "QTDE DISPONÍVEL"],
    "grupo": ["GRUPO"],
    "num_item": ["Nº ITEM", "NUM ITEM", "Nº ITEM (AUTO)", "NUM ITEM (AUTO)"],
}

COLUNAS_BAIXAS = {
    "data": ["DATA", "DATA DA BAIXA", "DATA LANÇAMENTO", "DATA LANCAMENTO"],
    "of": ["OF", "Nº OF", "NUM OF", "ORDEM DE FORNECIMENTO", "NÚMERO OF", "NRO OF", "Nº PEDIDO / NF / OF"],
    "codigo": ["CÓDIGO", "CODIGO", "CÓDIGO DE BARRAS", "CÓDIGO INTERNO"],
    "descricao": ["DESCRIÇÃO", "DESCRICAO", "ITEM", "PRODUTO", "DESCRIÇÃO (AUTO)"],
    "quantidade": ["QTDE", "QTD", "QUANTIDADE", "QUANTIDADE BAIXADA", "QTD BAIXADA", "QTD. BAIXADA"],
    "preco_unit": ["PREÇO UNIT", "PRECO UNIT", "VALOR UNITÁRIO", "VALOR UNIT"],
    "valor_total": ["VALOR TOTAL", "TOTAL", "VALOR", "VALOR (R$)"],
    "grupo": ["GRUPO", "GRUPO (AUTO)"],
    "num_item": ["Nº ITEM", "NUM ITEM", "Nº ITEM (AUTO)", "NUM ITEM (AUTO)"],
}

MAX_LINHAS_VARREDURA_CABECALHO = 10

FUZZY_LIMIAR_DESCRICAO = 90
FUZZY_LIMIAR_PRECO_IGUAL = 70
PRECISAO_VALOR = 2