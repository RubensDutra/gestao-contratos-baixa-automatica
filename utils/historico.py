from datetime import datetime
import json
from pathlib import Path

DEFAULT_CAMINHO = Path(__file__).resolve().parent.parent / "data" / "historico_baixas.json"


def ler_historico(caminho=None) -> list:
    p = caminho or DEFAULT_CAMINHO
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def registrar_baixa(numero_of, lancamentos, arquivo_origem=None, caminho=None, max_entradas=50) -> None:
    p = caminho or DEFAULT_CAMINHO
    p.parent.mkdir(parents=True, exist_ok=True)
    registros = ler_historico(p)
    itens = [
        {
            "codigo": l.codigo,
            "descricao": l.descricao,
            "quantidade": l.quantidade,
            "preco_unit": l.preco_unit,
            "valor_total": l.valor_total,
            "linha": l.linha,
        }
        for l in lancamentos
    ]
    registros.append(
        {
            "data_hora": datetime.now().isoformat(timespec="seconds"),
            "numero_of": numero_of,
            "total_itens": len(itens),
            "total_valor": sum(i["valor_total"] for i in itens),
            "arquivo_origem": str(arquivo_origem) if arquivo_origem else "",
            "itens": itens,
        }
    )
    registros = registros[-max_entradas:]
    p.write_text(json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")