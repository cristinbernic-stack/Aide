# RunPod Serverless — endpoint vLLM

Scop: un endpoint OpenAI-compatible care pornește singur la prima cerere și se oprește
singur după `IDLE_TIMEOUT`. Plătești pe secundă doar cât rulează.

## 0. Cont

1. Cont RunPod, card adăugat.
2. **Settings → Billing → Spending limit**: setează ~$60/lună. Este gardul principal;
   LiteLLM are al doilea (`max_budget`).
3. **Settings → API Keys**: creează o cheie (Read/Write) → `RUNPOD_API_KEY` în `.env`.

## 1. Network Volume (greutățile modelului)

**Storage → Network Volumes → New**

| Câmp | Valoare |
|---|---|
| Nume | `aide-models` |
| Datacenter | unul cu A40/A6000 disponibile (ex. EU-RO-1, EU-SE-1); endpoint-ul va rula **în același datacenter** |
| Mărime | 60 GB (modelul FP8 ≈ 31 GB; loc pentru un al doilea model) |

Cost: 60 GB × $0.07 = $4.2/lună, indiferent dacă GPU-ul rulează.

## 2. Endpoint Serverless

**Serverless → New Endpoint → Quick Deploy → vLLM** (sau imaginea `runpod/worker-v1-vllm:stable-cuda12.1.0`)

| Câmp | Valoare |
|---|---|
| Nume | `aide-coder` |
| GPU | **48 GB** (A40 / A6000 — $1.22/h; nu alege L40S/6000 Ada, $1.75/h fără câștig aici) |
| Active workers | **0** (altfel plătești 24/7) |
| Max workers | **1** |
| Idle timeout | **600** s (10 min: pașii succesivi ai agentului nu plătesc cold start) |
| FlashBoot | activat |
| Network volume | `aide-models` |
| Execution timeout | 900 s |

Environment variables ale endpoint-ului:

| Variabilă | Valoare | De ce |
|---|---|---|
| `MODEL_NAME` | `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8` | ~31 GB FP8, 256K context nativ, Apache 2.0 |
| `HF_HOME` | `/runpod-volume/hf` | greutățile rămân pe volum; se descarcă o singură dată |
| `MAX_MODEL_LEN` | `65536` | suficient pentru aider/OpenHands; lasă loc KV cache |
| `GPU_MEMORY_UTILIZATION` | `0.92` | |
| `ENABLE_AUTO_TOOL_CHOICE` | `true` | OpenHands folosește tool calling |
| `TOOL_CALL_PARSER` | `qwen3_coder` | parserul specific modelului |
| `DTYPE` | `auto` | |

Model alternativ pe **24 GB** ($0.69/h): `Qwen/Qwen3-Coder-30B-A3B-Instruct` cuantizat AWQ
(ex. `cpatonn/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit`) cu `MAX_MODEL_LEN=32768`.
Și modelul din `litellm/config.yaml` trebuie schimbat la fel.

## 3. Prima pornire

Prima cerere descarcă modelul pe volum (~31 GB, 5–10 min), apoi cold start-urile
scad la 1–3 min. Rulează din VPS:

```bash
bash scripts/test-endpoint.sh
```

Apoi urmărește în RunPod **Serverless → aide-coder → Workers**: după 10 min fără cereri
worker-ul trebuie să dispară (0 running). Dacă nu dispare, ai un Active worker setat >0.

## 4. Endpoint-ul în `.env`

```
RUNPOD_API_KEY=rpa_...
RUNPOD_ENDPOINT_ID=abc123xyz          # din URL-ul endpoint-ului
RUNPOD_API_BASE=https://api.runpod.ai/v2/abc123xyz/openai/v1
MODEL_NAME=Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8
```

## 5. Când treci la Pod (on-demand)

Dacă LiteLLM arată > ~45 ore GPU/lună, un pod A40 ($0.49/h) devine mai ieftin, cu
prețul unui script de auto-start/stop. Schimbarea atinge doar `RUNPOD_API_BASE` și
`RUNPOD_API_KEY`; agenții, Open WebUI și runner-ul nu se modifică.
