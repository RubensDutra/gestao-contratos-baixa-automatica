import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.pdf_extractor import extrair_texto_pdf, extrair_itens_pdf


def main():
    parser = argparse.ArgumentParser(description="Inspeciona a extração de itens de um PDF de OF (Etapa 2).")
    parser.add_argument("arquivo", help="Caminho do PDF da Ordem de Fornecimento")
    parser.add_argument("--texto", action="store_true", help="Mostra o texto bruto extraído do PDF")
    args = parser.parse_args()

    if args.texto:
        print(extrair_texto_pdf(args.arquivo))

    itens = extrair_itens_pdf(args.arquivo)
    print(f"\nItens extraídos: {len(itens)}")
    for it in itens:
        print(f"[{it.codigo}] {it.descricao} | {it.quantidade:g} {it.unidade} | "
              f"R$ {it.valor_unitario:.2f} | R$ {it.valor_total:.2f} | pág. {it.pagina}")


if __name__ == "__main__":
    main()