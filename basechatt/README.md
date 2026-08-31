# BaseChatt

BaseChatt — an AI financial research analyst for the Nigerian economy, markets,
and companies. Ask questions in plain English and get answers grounded in
primary sources (the CBN, NBS, SEC Nigeria, NGX, FMDQ and company investor
relations releases) with citations and a verification verdict.

The system retrieves from a RAG index (pgvector + hybrid search), routes
through a LangGraph research agent, and verifies each answer against the
retrieved evidence before it is returned or persisted as a citation.

## Features

- **Hybrid retrieval** — dense (embedding) + lexical (pgvector `tsvector`)
  fusion with RRF and a deterministic reranker (authority + freshness).
- **Agentic research** — a LangGraph pipeline: retrieve → answer → verify,
  supporting follow-up queries when evidence is weak.
- **Multi-source ingestion** — six registered connectors (`cbn`, `nbs`,
  `sec_nigeria`, `ngx`, `fmdq`, `company_ir`) with dedup, versioning,
  chunking and embedding.
- **Verification & citations** — every answer carries a supported / not
  supported verdict plus the evidence it is grounded on.
- **Evaluation harness** — curated Nigerian-finance questions with
  recall@k / MRR / token-F1 reporting (`basechatt eval`).
- **HTTP API** — FastAPI with API-key auth and rate limiting.

## Quick start

Requires Python 3.12, Docker (for Postgres + Redis).

```bash
# 1. Install
python -m venv .venv
.venv/bin/pip install -e ".[dev]"      # Windows: .venv\Scripts\pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# set BASECHATT_GROQ_API_KEY (free tier here: https://console.groq.com)

# 3. Start Postgres (pgvector) + Redis on their non-default ports
make db-up                                 # docker compose up -d postgres redis

# 4. Create the schema and seed companies/sources
make seed                                  # runs init-db, then python -m basechatt.cli seed

# 5. Ingest documents from all sources
make sync                                  # python -m basechatt.cli sync

# 6. Run the API (docs at http://127.0.0.1:8000/docs)
make run                                   # uvicorn apps.api.main:app --reload
```

## Using the CLI

```bash
# Ask the research agent a question
python -m basechatt.cli ask "What was Nigeria's GDP growth in 2024?"
python -m basechatt.cli ask "How did GTCO's PAT move in Q3 2024?" --company GTCO --json

# Sync a single source
python -m basechatt.cli sync cbn
python -m basechatt.cli sync-status

# Evaluation
python -m basechatt.cli seed-eval          # load datasets/evaluation/questions.json
python -m basechatt.cli eval               # run the harness (--mock for offline)
python -m basechatt.cli doctor             # environment checks
```

## HTTP API

All endpoints are under `/api/v1`. When `BASECHATT_API_KEY` is set, send the
key via the `X-API-Key` header (otherwise auth is open in development).

| Method | Path                          | Description                          |
| ------ | ----------------------------- | ------------------------------------ |
| GET    | `/api/v1/health`              | Service + database health            |
| POST   | `/api/v1/query`               | Run the research agent on a question |
| GET    | `/api/v1/sync/status`         | Latest sync run per source           |
| POST   | `/api/v1/sync`                | Trigger sync for all / some sources  |
| POST   | `/api/v1/sync/{source}`       | Trigger sync for one source          |
| GET    | `/api/v1/documents`           | List indexed documents (filters)     |
| GET    | `/api/v1/companies`           | List the seeded company universe     |
| GET    | `/api/v1/sources`             | List registered sources              |
| GET    | `/api/v1/metrics`             | In-process latency / counter summary |
| POST   | `/api/v1/calculate`           | Growth, CAGR, margin & ratio math    |
| GET    | `/api/v1/evaluation/results`  | Last evaluation runs                 |

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BASECHATT_API_KEY" \
  -d '{"query": "What was the Q2 2024 unemployment rate?", "company_ticker": null}'
```

## Project layout

```
apps/api/          FastAPI application
src/basechatt/
  agents/          Research graph, state, tool prompts
  chunking/        Structural and semantic chunkers
  config/          Pydantic settings (env prefix BASECHATT_)
  database/        SQLAlchemy models + repositories (pgvector)
  evaluation/      Harness + retrieval metrics
  ingestion/       Connectors, discovery, parsing, dedup, versioning
  llm/             Provider factory (groq/openai/anthropic/mock)
  observability/   Logging, metrics, tracing
  retrieval/       Dense/lexical search, RRF fusion, reranker
  security/        API keys, rate limiting, query sanitisation
  tools/           Financial calculations
  verification/    Answer verifier + citation persistence
  workers/         Sync / ingestion / indexing workers
  cli.py           Command-line interface
config/            Company universe (companies.yaml)
datasets/          Evaluation question corpus
docker/            Image definition
```

## Quality gates

```bash
make lint      # ruff check src tests apps/api
make test      # pytest                       (unit tests, no database needed)
make typecheck # mypy src                     (optional)
```

## Notes

- The default LLM/embedding provider is **Groq** (free tier, no local
  downloads). Set `BASECHATT_LLM_PROVIDER=mock` for fully offline test runs.
- Embedding dimension is fixed at 768 (`BASECHATT_EMBEDDING_DIM`) — changing
  it after initial ingest requires a re-embed of the corpus.
- Ports are intentionally host-mapped to `5433` (Postgres) and `6380` (Redis)
  so they don't collide with system services.