import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from utils.excel_loader import carregar_planilha, totais_contrato, ErroPlanilha


def main():
    parser = argparse.ArgumentParser(description="Inspeciona a planilha base do contrato (Etapa 1).")
    parser.add_argument("arquivo", nargs="?", default=str(config.PLANILHA_PADRAO),
                        help="Caminho da planilha (padrão: data/inputs/CONTROLE_DE_CONTRATO.xlsx)")
    args = parser.parse_args()

    try:
        dados = carregar_planilha(args.arquivo)
    except ErroPlanilha as e:
        print(f"[ERRO] {e}")
        sys.exit(1)

    print(f"Arquivo: {dados.caminho}")
    print(f"Abas detectadas: {[ws.title for ws in dados.wb_template.worksheets]}")
    print(f"\nAba '{dados.aba_itens.title}' (cabeçalho na linha {dados.mapa_itens.linha_cabecalho}):")
    print(f"  Colunas mapeadas: {dados.mapa_itens.colunas}")
    print(f"  Itens lidos: {len(dados.df_itens)}")
    totais = totais_contrato(dados)
    print(f"  Valor total do contrato: R$ {totais['valor_total']:,.2f}")
    print(f"  Saldo total disponível: {totais['saldo_total']:,.2f}")
    print(f"\nAba '{dados.aba_baixas.title}' (cabeçalho na linha {dados.mapa_baixas.linha_cabecalho}):")
    print(f"  Colunas mapeadas: {dados.mapa_baixas.colunas}")
    print(f"  Lançamentos existentes: {len(dados.df_baixas)}")

    if not dados.df_itens.empty:
        print("\nPrimeiros 5 itens:")
        colunas = ["codigo_barras", "descricao", "preco_unit", "saldo_disponivel"]
        print(dados.df_itens[colunas].head(5).to_string(index=False))


if __name__ == "__main__":
    main()