# AGENTS.md — memoria de proiect a agentului

Acest fișier este citit de agent (aider `--read`, OpenHands) la începutul fiecărui task.
Este **memoria pe termen lung**: tot ce nu se poate deduce din cod și trebuie știut
de fiecare dată. Se copiază în repo-ul-țintă (ex. Nexus) și se adaptează.

## Proiect

- Nume: Aide (infrastructura agentului). Repo-ul-țintă al task-urilor: `TARGET_REPO` din `.env`.
- Limba de lucru: română în mesaje, comentarii și PR-uri; codul și identificatorii în engleză.

## Reguli neschimbabile

1. Nu se modifică API-ul public fără cerere explicită în issue.
2. Fiecare modificare de comportament vine cu test sau cu actualizarea testului existent.
3. Nu se adaugă dependențe noi fără a le menționa în mesajul de commit.
4. Nu se șterg fișiere de configurare sau date; se preferă deprecierea.
5. Commit-uri mici, mesaje în format `tip(scop): ce și de ce` (ex. `fix(analysis): ...`).

## Cum se rulează

- Teste: `TEST_CMD` din `.env` (în repo-ul-țintă: completează aici comanda exactă).
- Lint/format: (completează)

## Decizii luate (jurnal)

- 2026-10-07: GPU serverless 48 GB, model Qwen3-Coder-30B-A3B FP8, un singur worker; se revizuiește după o lună pe baza orelor reale din LiteLLM.
- 2026-10-07: integrarea umană = aprobarea PR-ului; fără auto-merge în faza 1.

## Preferințele lui Radu

- Răspunsuri scurte, cu decizii clare, nu liste de opțiuni.
- Totul cât mai hands-free; prefer un PR greșit pe care îl resping unui agent care întreabă.
