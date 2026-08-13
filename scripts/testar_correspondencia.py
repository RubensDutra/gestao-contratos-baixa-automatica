import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.excel_loader import carregar_planilha
from utils.matcher import corresponder_todos, resumo, STATUS_APROVADO, STATUS_SALDO_INSUFICIENTE
from utils.pdf_extractor import extrair_itens_pdf


def main():
    parser = argparse.ArgumentParser(description="Testa o algoritmo de correspondência (Etapa 3).")
    parser.add_argument("planilha", help="Caminho da planilha base")
    parser.add_argument("pdfs", nargs="+", help="PDFs das Ordens de Fornecimento")
    args = parser.parse_args()

    dados = carregar_planilha(args.planilha)
    for pdf in args.pdfs:
        itens = extrair_itens_pdf(pdf)
        print(f"\n=== {Path(pdf).name} ({len(itens)} itens) ===")
        resultados = corresponder_todos(itens, dados.df_itens)
        print(f"Resumo: {resumo(resultados)}")
        for r in resultados:
            ic = r.item_pdf
            if r.status == STATUS_APROVADO:
                e = r.escolhido
                print(f"[OK  ] {ic.descricao[:50]:50s} -> linha {e['linha']} ({e['codigo_barras']}) sim {e['similaridade']}%")
            elif r.status == STATUS_SALDO_INSUFICIENTE:
                e = r.escolhido
                print(f"[SAL ] {ic.descricao[:50]:50s} -> linha {e['linha']} saldo {e['saldo_disponivel']} < qtd {ic.quantidade}")
            elif r.status == "duplicidade":
                print(f"[DUP ] {ic.descricao[:50]:50s} -> {len(r.candidatos)} candidatos:")
                for c in r.candidatos:
                    print(f"         - linha {c['linha']} ({c['codigo_barras']}) saldo {c['saldo_disponivel']} sim {c['similaridade']}%")
            else:
                print(f"[FALHA] {ic.descricao[:50]:50s} -> não encontrado")
                for s in r.sugestoes:
                    print(f"         sugestão: linha {s['linha']} ({s['descricao'][:35]}) sim {s['similaridade']}%")


if __name__ == "__main__":
    main()