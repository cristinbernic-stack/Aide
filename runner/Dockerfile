FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates build-essential \
 && rm -rf /var/lib/apt/lists/*

# aider = agentul de cod; requests = GitHub/Telegram API
RUN pip install --no-cache-dir aider-chat requests

RUN useradd -m -u 1000 agent
WORKDIR /work
RUN chown agent:agent /work
USER agent

COPY --chown=agent:agent runner.py /app/runner.py

CMD ["python", "-u", "/app/runner.py"]
