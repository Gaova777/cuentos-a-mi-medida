#!/usr/bin/env bash
# Shortcuts for this project (make isn't installed on the machine it was built on).
set -euo pipefail
cd "$(dirname "$0")"

case "${1:-help}" in
  test)        uv run pytest -q && uv run ruff check src scripts tests ;;
  infra)       docker compose -f infra/docker-compose.yml up -d
               until curl -sf localhost:4566/_localstack/health >/dev/null; do sleep 2; done
               terraform -chdir=infra init -input=false >/dev/null && terraform -chdir=infra apply -auto-approve -input=false ;;
  infra-down)  docker compose -f infra/docker-compose.yml down ;;
  voice)       mkdir -p data/voices && for f in es_MX-ald-medium.onnx es_MX-ald-medium.onnx.json; do
                 curl -sfL -o "data/voices/$f" "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/ald/medium/$f"
               done ;;
  ollama)      ollama serve ;;
  api)         uv run uvicorn cuentos_a_mi_medida.entrypoints.api:app --port 8002 ;;
  worker)      uv run python -m cuentos_a_mi_medida.entrypoints.worker ;;
  web)         cd web && PATH=$HOME/.local/opt/node/bin:$PATH npm run dev -- --port 3002 ;;
  reproduce)   uv run --group repro scripts/reproduce_add.py && uv run --group repro scripts/evaluate_add.py ;;
  readability) uv run scripts/readability_benchmark.py ;;
  consistency) uv run --group repro scripts/consistency_benchmark.py ;;
  safety)      uv run scripts/safety_benchmark.py ;;
  gate)        uv run scripts/quality_gate.py ;;
  *)           echo "usage: ./run.sh test|infra|infra-down|voice|ollama|api|worker|web|reproduce|readability|consistency|safety|gate" ;;
esac
