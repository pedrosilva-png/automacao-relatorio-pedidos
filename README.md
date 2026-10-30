# 03 — Automação de Relatório Diário

Lê CSV de pedidos, gera KPIs + alertas + insight, e documenta **economia de horas** vs processo manual (~50 min → segundos).

## Destaques

- Automação com métrica de impacto (antes/depois)
- Saída pronta para Slack/e-mail (`output/relatorio_latest.md`)
- Manifesto de fluxo no-code (`output/workflow_n8n_make.json`)
- Análise orientada a decisão

## Como rodar

```bash
cd 03-automacao-relatorio
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/automacao.py
```

Abra `output/relatorio_latest.md`.

## Impacto (demo)

| Antes | Depois |
|-------|--------|
| ~50 min/dia montando relatório | < 1 s |
| ~4,2 h/semana | ~4 h/semana economizadas |
