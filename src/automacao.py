"""
Automação de relatório diário de pedidos.

Antes (manual): ~45–60 min montando planilha + texto no Slack/e-mail.
Agora: segundos, com métricas e insights acionáveis.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "pedidos_dia.csv"
OUT_DIR = ROOT / "output"

# Estimativa usada no portfólio (documentar o ganho de horas)
MINUTOS_MANUAL_ESTIMADOS = 50


@dataclass
class Metricas:
    total_pedidos: int
    entregues: int
    cancelados: int
    taxa_cancelamento_pct: float
    gmv: float
    ticket_medio: float
    tempo_medio_min: float
    nps_proxy_media: float
    top_restaurantes: list[dict]
    piores_avaliacoes: list[dict]
    alertas: list[str]


def carregar(path: Path = CSV_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df


def calcular(df: pd.DataFrame) -> Metricas:
    entregues = df[df["status"] == "entregue"]
    cancelados = df[df["status"] == "cancelado"]
    gmv = float(entregues["valor"].sum())
    ticket = float(entregues["valor"].mean()) if len(entregues) else 0.0
    tempo = float(entregues["tempo_min"].mean()) if len(entregues) else 0.0
    nps = float(entregues["avaliacao"].dropna().mean()) if len(entregues) else 0.0

    top = (
        entregues.groupby("restaurante")["valor"]
        .sum()
        .sort_values(ascending=False)
        .head(3)
        .reset_index()
        .rename(columns={"valor": "gmv"})
        .to_dict(orient="records")
    )
    for row in top:
        row["gmv"] = round(float(row["gmv"]), 2)

    piores = (
        entregues.dropna(subset=["avaliacao"])
        .sort_values("avaliacao")
        .head(3)[["pedido_id", "restaurante", "avaliacao", "tempo_min"]]
        .to_dict(orient="records")
    )

    alertas: list[str] = []
    taxa_cancel = (len(cancelados) / len(df) * 100) if len(df) else 0.0
    if taxa_cancel >= 10:
        alertas.append(f"Taxa de cancelamento alta: {taxa_cancel:.1f}%")
    lentos = entregues[entregues["tempo_min"] >= 45]
    if len(lentos):
        alertas.append(f"{len(lentos)} entrega(s) com tempo ≥ 45 min")
    ruins = entregues[entregues["avaliacao"] <= 2]
    if len(ruins):
        alertas.append(f"{len(ruins)} avaliação(ões) ≤ 2 — revisar qualidade")
    if not alertas:
        alertas.append("Nenhum alerta crítico no dia.")

    return Metricas(
        total_pedidos=int(len(df)),
        entregues=int(len(entregues)),
        cancelados=int(len(cancelados)),
        taxa_cancelamento_pct=round(taxa_cancel, 2),
        gmv=round(gmv, 2),
        ticket_medio=round(ticket, 2),
        tempo_medio_min=round(tempo, 1),
        nps_proxy_media=round(nps, 2),
        top_restaurantes=top,
        piores_avaliacoes=piores,
        alertas=alertas,
    )


def gerar_markdown(m: Metricas, segundos: float) -> str:
    top_lines = "\n".join(
        f"- {r['restaurante']}: R$ {r['gmv']:.2f}" for r in m.top_restaurantes
    )
    piores = "\n".join(
        f"- {p['pedido_id']} ({p['restaurante']}): nota {p['avaliacao']} — {p['tempo_min']} min"
        for p in m.piores_avaliacoes
    )
    alertas = "\n".join(f"- {a}" for a in m.alertas)
    economia = MINUTOS_MANUAL_ESTIMADOS - (segundos / 60)
    return f"""# Relatório diário de pedidos

Gerado em {datetime.now().strftime("%Y-%m-%d %H:%M")}

## KPIs
| Métrica | Valor |
|---------|-------|
| Pedidos | {m.total_pedidos} |
| Entregues | {m.entregues} |
| Cancelados | {m.cancelados} ({m.taxa_cancelamento_pct}%) |
| GMV | R$ {m.gmv:.2f} |
| Ticket médio | R$ {m.ticket_medio:.2f} |
| Tempo médio | {m.tempo_medio_min} min |
| Avaliação média | {m.nps_proxy_media} |

## Top restaurantes (GMV)
{top_lines}

## Piores avaliações
{piores}

## Alertas
{alertas}

## Impacto da automação
- Tempo manual estimado: **{MINUTOS_MANUAL_ESTIMADOS} min**
- Tempo desta execução: **{segundos:.2f} s**
- Economia estimada: **~{economia:.1f} min/dia** (~{economia * 5 / 60:.1f} h/semana)
"""


def gerar_insight_ia(m: Metricas) -> str:
    """Insight em linguagem natural (template; plugável em LLM)."""
    foco = m.alertas[0]
    top = m.top_restaurantes[0]["restaurante"] if m.top_restaurantes else "N/A"
    return (
        f"Priorize hoje: {foco} "
        f"GMV concentrado em {top}. "
        f"Ticket médio R$ {m.ticket_medio:.2f} com avaliação {m.nps_proxy_media}."
    )


def executar(csv_path: Path = CSV_PATH) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    df = carregar(csv_path)
    metricas = calcular(df)
    elapsed = time.perf_counter() - t0
    md = gerar_markdown(metricas, elapsed)
    insight = gerar_insight_ia(metricas)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = OUT_DIR / f"relatorio_{stamp}.md"
    json_path = OUT_DIR / f"metricas_{stamp}.json"
    latest_md = OUT_DIR / "relatorio_latest.md"
    latest_json = OUT_DIR / "metricas_latest.json"

    payload = {
        "metricas": asdict(metricas),
        "segundos": round(elapsed, 4),
        "minutos_manual_estimados": MINUTOS_MANUAL_ESTIMADOS,
        "economia_minutos": round(MINUTOS_MANUAL_ESTIMADOS - elapsed / 60, 2),
        "insight": insight,
    }

    md_path.write_text(md + f"\n## Insight\n{insight}\n", encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    # Workflow n8n/Make-ready: manifesto de automação
    workflow = {
        "nome": "relatorio-diario-pedidos",
        "trigger": "cron 0 18 * * 1-5",
        "passos": [
            {"app": "CSV/Drive", "acao": "ler pedidos_dia.csv"},
            {"app": "este script", "acao": "python src/automacao.py"},
            {"app": "Slack/Email", "acao": "enviar output/relatorio_latest.md"},
        ],
        "economia_horas_semana": round((MINUTOS_MANUAL_ESTIMADOS * 5) / 60, 1),
    }
    (OUT_DIR / "workflow_n8n_make.json").write_text(
        json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return payload


if __name__ == "__main__":
    result = executar()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nRelatório: {OUT_DIR / 'relatorio_latest.md'}")
