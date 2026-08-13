import re
import unicodedata

SUBSTITUICOES = {
    "¾": "3/4", "½": "1/2", "¼": "1/4", "⅓": "1/3", "⅔": "2/3",
    "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8", "⅕": "1/5",
    "⅖": "2/5", "⅗": "3/5", "⅘": "4/5", "⅙": "1/6", "⅚": "5/6",
    "×": "X", "•": " ", "–": "-", "—": "-", "’": "'", "“": '"', "”": '"',
}


def normalizar_texto(texto) -> str:
    if texto is None:
        return ""
    t = str(texto).upper().strip()
    for origem, destino in SUBSTITUICOES.items():
        t = t.replace(origem, destino)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def normalizar_para_comparacao(texto) -> str:
    t = normalizar_texto(texto)
    return re.sub(r"[^A-Z0-9/]", "", t)