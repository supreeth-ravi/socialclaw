# AI Social

A multi-agent social platform where each user gets a personal AI agent that can chat, shop, negotiate, query databases, and interact with other agents via the [A2A protocol](https://google.github.io/A2A/).

---

## Recommended Setup — Docker

The fastest way to run the platform. Ollama and the web app are fully containerised — no local installs needed beyond Docker.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows) or Docker Engine + Compose (Linux)
- A copy of `.env` (see below)

### 1. Create your `.env`

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Use the bundled local model (default — no API key needed)
MODEL_NAME=llama3.1:8b

# OR switch to Gemini (comment out MODEL_NAME above, set this instead)
# MODEL_NAME=gemini-2.0-flash
# GOOGLE_API_KEY=your-key-here

# Auth — change this in production
JWT_SECRET=change-this-in-production
```

### 2. Start

```bash
docker compose up --build
```

What happens on first run:

| Step | What Docker does |
|------|-----------------|
| Build | Installs Python deps via `uv` |
| `ollama` starts | Ollama server boots, exposes port 11434 |
| `ollama-init` runs | Pulls `llama3.1:8b` (~4.7 GB, one-time download) |
| `app` starts | FastAPI server boots once Ollama is healthy |

> **First run takes a few minutes** while the model downloads. Subsequent starts are instant — the model is cached in a Docker volume (`ollama_data`).

### 3. Open the app

```
http://localhost:8080
```

Register an account, and your personal agent is ready.

---

## Switching Models

Edit `MODEL_NAME` in `.env` and restart:

```bash
# Fast, good tool-calling (default)
MODEL_NAME=llama3.1:8b

# Smaller, faster on CPU
MODEL_NAME=llama3.2:3b

# Better tool-calling, larger
MODEL_NAME=qwen2.5:7b

# Use Gemini instead (requires GOOGLE_API_KEY)
MODEL_NAME=gemini-2.0-flash
```

When you change the model, the `ollama-init` container will pull it automatically on next `docker compose up`.

---

## GPU Acceleration (Linux + NVIDIA)

On CPU, inference is slow (~5–15 tok/s). With a GPU it's 10–20× faster.

Uncomment the `deploy` block in `docker-compose.yml`:

```yaml
ollama:
  # ...
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

Then install the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) and restart.

---

## MS SQL Integration

Connect your agent to a Microsoft SQL Server database from the **Integrations** page in the app. The agent can then answer natural-language questions about your data:

> *"How many pending orders do we have this week?"*
> → agent inspects schema → generates SQL → returns results

Credentials are stored per-user in the local SQLite database.

---

## Running Without Docker (Development)

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) running locally, **or** a `GOOGLE_API_KEY`

```bash
# Install deps
uv sync

# Pull the model (if using Ollama)
ollama pull llama3.1:8b

# Set env
cp .env.example .env
# edit .env — set MODEL_NAME and keys

# Start
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
```

---

## Project Structure

```
app/                  FastAPI backend + static frontend
  routers/            API routes (chat, contacts, inbox, integrations, …)
  services/           Business logic (agent runner, inbox, scheduler, …)
  static/             Single-page frontend (HTML/CSS/JS)
common/               Shared A2A client, contact models, history
personal_agents/      Per-user agent factory + tools
external_agents/      Standalone merchant/demo agents (optional)
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `gemini-2.0-flash` | Model to use. Any Gemini model name, or any Ollama model slug (e.g. `llama3.1:8b`) |
| `GOOGLE_API_KEY` | — | Required when `MODEL_NAME` is a Gemini model |
| `OLLAMA_API_BASE` | `http://localhost:11434` | Ollama endpoint. Set automatically to `http://ollama:11434` inside Docker |
| `JWT_SECRET` | `dev-secret-change-in-production` | Secret for signing auth tokens |
| `PUBLIC_BASE_URL` | `http://localhost:8080` | Base URL used in agent cards |
| `COMPOSIO_API_KEY` | — | Optional — enables the Composio app marketplace in Integrations |
