# BaseChatt

An AI financial research tool for Nigeria.

Ask a question in plain English. Get an answer grounded in real data from the CBN, NBS, SEC Nigeria, NGX, FMDQ, and company investor relations.

## What it does

- Pulls documents from six public Nigerian data sources
- Chunks and embeds them into a search index (Postgres + pgvector)
- Runs your question through a research agent that retrieves evidence, writes an answer, and checks itself
- Returns the answer with citations and a yes/no support verdict

## How it works

1. A LangGraph agent gets your query
2. It searches the vector index using both semantic and keyword search
3. It writes an answer using only the retrieved evidence
4. It checks whether the evidence actually supports the answer
5. It returns the answer, citations, and the verdict

## Quick start

Needs Python 3.12 and Docker.

```bash
# install
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"

# set up env
copy .env.example .env
# add your BASECHATT_GROQ_API_KEY (free at https://console.groq.com)

# start postgres and redis
make db-up

# create tables and seed companies
make seed

# pull documents from the sources
make sync

# run the API (http://127.0.0.1:8000/docs)
make run
```

## CLI

```bash
# ask a question
python -m basechatt.cli ask "What was Nigeria's GDP growth in 2024?"
python -m basechatt.cli ask "How did GTCO's profit move in Q3 2024?" --company GTCO

# sync one source
python -m basechatt.cli sync cbn
python -m basechatt.cli sync-status

# run evaluation
python -m basechatt.cli seed-eval
python -m basechatt.cli eval
python -m basechatt.cli eval --mock

# check your setup
python -m basechatt.cli doctor
```

## HTTP API

All endpoints are under `/api/v1`. If you set `BASECHATT_API_KEY`, send it as the `X-API-Key` header. Without a key, auth is open (dev only).

| Method | Path                         | What it does                        |
| ------ | ---------------------------- | ----------------------------------- |
| GET    | /api/v1/health               | Service and database health         |
| POST   | /api/v1/query                | Run the research agent              |
| GET    | /api/v1/sync/status          | Latest sync run per source          |
| POST   | /api/v1/sync                 | Trigger sync for all or some sources |
| POST   | /api/v1/sync/{source}        | Trigger sync for one source         |
| GET    | /api/v1/documents            | List indexed documents              |
| GET    | /api/v1/companies            | List seeded companies               |
| GET    | /api/v1/sources              | List registered sources             |
| GET    | /api/v1/metrics              | Latency and counter summary         |
| POST   | /api/v1/calculate            | Growth, CAGR, margin, ratio math    |
| GET    | /api/v1/evaluation/results   | Last evaluation runs                |

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"query": "What was the Q2 2024 unemployment rate?"}'
```

## Project layout

```
apps/api/          FastAPI app
src/basechatt/
  agents/          Research graph and prompts
  chunking/        Text chunkers
  config/          Settings (env prefix BASECHATT_)
  database/        Models and queries (pgvector)
  evaluation/      Test harness
  ingestion/       Source connectors and parsing
  llm/             Provider factory (groq, openai, anthropic, mock)
  observability/   Logging and metrics
  retrieval/       Search and reranking
  security/        Auth and rate limits
  tools/           Financial math
  verification/    Answer checker
  workers/         Background jobs
  cli.py           Command line
config/            Company list (companies.yaml)
datasets/          Evaluation questions
docker/            Docker setup
```

## Tests and linting

```bash
make lint      # ruff
make test      # pytest
make typecheck # mypy
```

## Notes

- Default LLM is Groq (free tier). Set `BASECHATT_LLM_PROVIDER=mock` for offline testing.
- Embedding size is 768. Changing it after ingest needs a re-embed.
- Postgres runs on port 5433 and Redis on 6380 to avoid clashes with local services.
