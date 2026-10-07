# Aide — agent de cod self-hosted

Infrastructură pentru un agent de programare care rulează pe un model open-weight,
cu buget-țintă de **€60–70/lună**:

- **VPS ieftin, permanent** (Hetzner CX22, ~€5/lună): LiteLLM, Open WebUI, OpenHands,
  runner-ul de task-uri, Postgres, Uptime Kuma.
- **GPU doar la cerere** (RunPod Serverless, 48 GB, scale-to-zero): vLLM cu
  `Qwen3-Coder-30B-A3B-Instruct-FP8`, greutățile pe un Network Volume.

```
GitHub Issue (label: agent) ──► runner ──► aider în sandbox ──► PR + Telegram
Browser (chat) ──► Open WebUI / OpenHands ──► LiteLLM ──► RunPod Serverless (vLLM)
```

## Structura

| Cale | Rol |
|---|---|
| `docker-compose.yml` | toate serviciile de pe VPS |
| `litellm/config.yaml` | endpoint OpenAI-compatible unic (`model: coder`), buget, log |
| `runner/` | serviciul care transformă Issue-urile în PR-uri |
| `scripts/bootstrap.sh` | instalează VPS-ul de la zero (Ubuntu 24.04) |
| `scripts/test-endpoint.sh` | verifică GPU-ul și LiteLLM cu `curl` |
| `docs/runpod.md` | pașii de creare a endpoint-ului Serverless |
| `AGENTS.md` | memoria de proiect citită de agent la fiecare task |

## Instalare pe VPS (rezumat)

1. Creează endpoint-ul RunPod după `docs/runpod.md`; notează `ENDPOINT_ID` și cheia API.
2. Pe VPS, ca root:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/cristinbernic-stack/Aide/main/scripts/bootstrap.sh | bash
   ```
3. Completează `/opt/aide/.env` (pornind de la `.env.example`), apoi `docker compose up -d`.
4. `scripts/test-endpoint.sh` trebuie să răspundă; GPU-ul se oprește singur după `IDLE_TIMEOUT`.
5. Accesul la UI-uri se face **doar prin Tailscale** (nimic public în afară de SSH).

## Cum dai un task agentului

Deschizi un Issue în repo-ul-țintă cu label-ul `agent`. Runner-ul îl preia în max 60 s,
lucrează pe branch-ul `agent/issue-<nr>`, rulează testele și deschide un PR.
Tu doar aprobi PR-ul. Nimic nu ajunge pe `main` fără tine.

## Garduri

- buget hard: spending limit în RunPod **și** `max_budget` în LiteLLM
- per task: `TASK_TIMEOUT_MIN` minute, un singur worker GPU
- token-ul GitHub al runner-ului: doar `contents:write` + `pull_requests:write` + `issues:write`
- `main` protejat în repo-ul-țintă
