"""
Runner: transformă Issue-urile cu label `agent` din TARGET_REPO în Pull Request-uri.

Bucla:
  poll Issues (label: agent, fără agent:running/done/failed)
    -> clone curat în /work/issue-<nr>, branch agent/issue-<nr>
    -> aider --message "<titlu + corp issue>" (--auto-test dacă TEST_CMD e setat)
    -> verificare finală TEST_CMD
    -> push + PR ("Closes #<nr>") + label agent:done + Telegram
  la eroare: label agent:failed + comentariu cu coada log-ului + Telegram

Nimic nu ajunge pe TARGET_BRANCH: doar branch-uri agent/* și PR-uri.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

import requests

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
TARGET_REPO = os.environ["TARGET_REPO"]
TARGET_BRANCH = os.environ.get("TARGET_BRANCH", "main")
TEST_CMD = os.environ.get("TEST_CMD", "").strip()
TASK_TIMEOUT = int(os.environ.get("TASK_TIMEOUT_MIN", "30")) * 60
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SEC", "60"))
AIDER_MODEL = os.environ.get("AIDER_MODEL", "openai/coder")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

WORK = Path("/work")
API = "https://api.github.com"
GH = requests.Session()
GH.headers.update({
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
})

LABEL_TODO, LABEL_RUNNING, LABEL_DONE, LABEL_FAILED = "agent", "agent:running", "agent:done", "agent:failed"
LABELS = {
    LABEL_TODO: ("1d76db", "Task pentru agent"),
    LABEL_RUNNING: ("fbca04", "Agentul lucrează"),
    LABEL_DONE: ("0e8a16", "PR deschis de agent"),
    LABEL_FAILED: ("d93f0b", "Agentul a eșuat; vezi comentariul"),
}


# ---------- utilitare ----------

def log(msg: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def sh(cmd: list[str], cwd: Path | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def telegram(text: str) -> None:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
    except requests.RequestException as e:
        log(f"telegram: {e}")


def tail(text: str, lines: int = 40) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


# ---------- GitHub ----------

def ensure_labels() -> None:
    for name, (color, desc) in LABELS.items():
        r = GH.post(f"{API}/repos/{TARGET_REPO}/labels", json={"name": name, "color": color, "description": desc})
        if r.status_code not in (201, 422):  # 422 = există deja
            log(f"label {name}: {r.status_code} {r.text}")


def pending_issues() -> list[dict]:
    r = GH.get(f"{API}/repos/{TARGET_REPO}/issues",
               params={"labels": LABEL_TODO, "state": "open", "sort": "created", "direction": "asc"})
    r.raise_for_status()
    out = []
    for issue in r.json():
        if "pull_request" in issue:
            continue
        names = {l["name"] for l in issue["labels"]}
        if names & {LABEL_RUNNING, LABEL_DONE, LABEL_FAILED}:
            continue
        out.append(issue)
    return out


def set_label(number: int, add: str, remove: str | None = None) -> None:
    if remove:
        GH.delete(f"{API}/repos/{TARGET_REPO}/issues/{number}/labels/{remove}")
    GH.post(f"{API}/repos/{TARGET_REPO}/issues/{number}/labels", json={"labels": [add]})


def comment(number: int, body: str) -> None:
    GH.post(f"{API}/repos/{TARGET_REPO}/issues/{number}/comments", json={"body": body})


def open_pr(number: int, branch: str, title: str, body: str) -> str:
    r = GH.post(f"{API}/repos/{TARGET_REPO}/pulls",
                json={"title": title, "head": branch, "base": TARGET_BRANCH, "body": body})
    if r.status_code == 201:
        return r.json()["html_url"]
    if r.status_code == 422:  # PR deja deschis pentru branch (re-rulare)
        owner = TARGET_REPO.split("/")[0]
        r2 = GH.get(f"{API}/repos/{TARGET_REPO}/pulls", params={"head": f"{owner}:{branch}", "state": "open"})
        if r2.ok and r2.json():
            return r2.json()[0]["html_url"]
    r.raise_for_status()
    return ""


# ---------- git / aider ----------

def setup_git_credentials() -> None:
    """Token-ul stă în ~/.git-credentials, nu în URL-ul remote-ului (nu apare în log-uri)."""
    home = Path.home()
    (home / ".git-credentials").write_text(f"https://x-access-token:{GITHUB_TOKEN}@github.com\n")
    os.chmod(home / ".git-credentials", 0o600)
    sh(["git", "config", "--global", "credential.helper", "store"])
    sh(["git", "config", "--global", "user.name", os.environ.get("GIT_AUTHOR_NAME", "Aide Agent")])
    sh(["git", "config", "--global", "user.email", os.environ.get("GIT_AUTHOR_EMAIL", "aide@users.noreply.github.com")])


def build_message(issue: dict) -> str:
    body = (issue.get("body") or "").strip()
    return (
        f"Task (GitHub issue #{issue['number']}): {issue['title']}\n\n"
        f"{body}\n\n"
        "Reguli: lucrezi doar în acest branch; nu modifica API-ul public dacă nu ți se cere explicit; "
        "adaugă sau actualizează teste pentru ce schimbi; dacă ceva e neclar, alege varianta cea mai "
        "conservatoare și explic-o în mesajul de commit."
    )


def run_aider(repo: Path, message: str) -> subprocess.CompletedProcess:
    cmd = [
        "aider",
        "--model", AIDER_MODEL,
        "--yes-always",
        "--auto-commits",
        "--no-check-update",
        "--no-show-model-warnings",
        "--no-stream",
        "--message", message,
    ]
    if (repo / "AGENTS.md").exists():
        cmd += ["--read", "AGENTS.md"]  # memoria de proiect, doar citire
    if TEST_CMD:
        cmd += ["--auto-test", "--test-cmd", TEST_CMD]
    return sh(cmd, cwd=repo, timeout=TASK_TIMEOUT)


def process(issue: dict) -> None:
    number = issue["number"]
    branch = f"agent/issue-{number}"
    repo = WORK / f"issue-{number}"
    log(f"#{number} start: {issue['title']}")
    set_label(number, LABEL_RUNNING, remove=None)
    comment(number, f"Am preluat task-ul. Lucrez pe branch `{branch}`.")
    telegram(f"▶️ #{number} {issue['title']}\nAgentul a început.")

    try:
        if repo.exists():
            shutil.rmtree(repo)
        r = sh(["git", "clone", "--branch", TARGET_BRANCH, f"https://github.com/{TARGET_REPO}.git", str(repo)])
        if r.returncode != 0:
            raise RuntimeError(f"clone:\n{r.stderr}")
        sh(["git", "checkout", "-b", branch], cwd=repo)

        aider = run_aider(repo, build_message(issue))
        aider_log = aider.stdout + "\n" + aider.stderr

        ahead = sh(["git", "rev-list", "--count", f"origin/{TARGET_BRANCH}..HEAD"], cwd=repo).stdout.strip()
        if ahead in ("", "0"):
            raise RuntimeError("Agentul nu a produs niciun commit.\n\n" + tail(aider_log))

        tests_note = "fără teste configurate (TEST_CMD gol)"
        if TEST_CMD:
            t = sh(["sh", "-c", TEST_CMD], cwd=repo, timeout=TASK_TIMEOUT)
            if t.returncode != 0:
                raise RuntimeError("Testele pică după modificări:\n\n" + tail(t.stdout + t.stderr))
            tests_note = f"`{TEST_CMD}` ✅"

        push = sh(["git", "push", "--force", "origin", branch], cwd=repo)
        if push.returncode != 0:
            raise RuntimeError(f"push:\n{push.stderr}")

        commits = sh(["git", "log", "--oneline", f"origin/{TARGET_BRANCH}..HEAD"], cwd=repo).stdout.strip()
        pr_url = open_pr(
            number, branch,
            title=f"[agent] {issue['title']}",
            body=f"Closes #{number}\n\n**Commit-uri**\n```\n{commits}\n```\n\n**Teste:** {tests_note}\n\n"
                 f"<details><summary>Log aider (coadă)</summary>\n\n```\n{tail(aider_log, 80)}\n```\n</details>",
        )
        set_label(number, LABEL_DONE, remove=LABEL_RUNNING)
        comment(number, f"Gata. PR: {pr_url}\nTeste: {tests_note}")
        telegram(f"✅ #{number} {issue['title']}\nPR: {pr_url}\nTeste: {tests_note}")
        log(f"#{number} done: {pr_url}")

    except subprocess.TimeoutExpired:
        fail(number, issue["title"], f"Timeout după {TASK_TIMEOUT // 60} min.")
    except Exception as e:  # noqa: BLE001 — orice eroare trebuie raportată în issue, nu să oprească runner-ul
        fail(number, issue["title"], str(e))
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def fail(number: int, title: str, reason: str) -> None:
    log(f"#{number} FAILED: {reason.splitlines()[0] if reason else ''}")
    set_label(number, LABEL_FAILED, remove=LABEL_RUNNING)
    comment(number, f"Nu am reușit.\n\n```\n{reason[-3500:]}\n```\n\n"
                    f"Scoate label-ul `{LABEL_FAILED}` și lasă `{LABEL_TODO}` ca să reîncerc.")
    telegram(f"❌ #{number} {title}\n{reason.splitlines()[0] if reason else 'eroare'}")


# ---------- main ----------

def main() -> None:
    WORK.mkdir(exist_ok=True)
    setup_git_credentials()
    ensure_labels()
    log(f"runner pornit; repo={TARGET_REPO} branch={TARGET_BRANCH} model={AIDER_MODEL} poll={POLL_INTERVAL}s")
    while True:
        try:
            for issue in pending_issues():
                process(issue)  # unul câte unul: un singur worker GPU
        except Exception as e:  # noqa: BLE001
            log(f"poll error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
