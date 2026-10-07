#!/usr/bin/env bash
# Verifică lanțul complet: LiteLLM -> RunPod Serverless -> vLLM.
# Prima cerere după idle durează 1-3 min (cold start); următoarele, secunde.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

BASE="http://${BIND_IP:-127.0.0.1}:4000"

echo "==> LiteLLM liveliness"
curl -fsS "$BASE/health/liveliness"; echo

echo "==> Modele expuse"
curl -fsS "$BASE/v1/models" -H "Authorization: Bearer $LITELLM_MASTER_KEY" | python3 -m json.tool

echo "==> Cerere de test (poate dura până la 3 min la cold start)"
time curl -fsS "$BASE/v1/chat/completions" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"coder","messages":[{"role":"user","content":"Scrie o funcție Python care verifică dacă un număr e prim. Doar codul."}],"max_tokens":200}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'

echo "==> OK. Verifică în RunPod că worker-ul trece pe idle și apoi se oprește."
