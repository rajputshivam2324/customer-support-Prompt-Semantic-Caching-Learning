# Relay — AI Customer Support Gateway

An explainable B2B support demo. Operators sign in, create separate saved chats, and inspect the real path for every answer: exact Redis cache, semantic pgvector cache, pgvector RAG plus Gemini, direct Gemini, or an invoice lookup plus Gemini.

## Stack

- Next.js + TypeScript frontend (Vercel)
- FastAPI + LangGraph + LangChain Google integration (Render)
- PostgreSQL + pgvector for customer records, conversations, knowledge retrieval, semantic cache, and traces
- Redis for exact response caching
- Gemini 2.5 Flash for answers and `gemini-embedding-001` for semantic matching and retrieval

The default is one fictional `Demo Workspace` with an Acme Corp sample customer. It does not use real customer data or require tenant keys. Conversations belong to the signed-in operator; the backend checks this ownership on every read and chat request. An admin can see tenant-wide traces and metrics, but only their own chats.

## Run locally

1. Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local` if those files do not already exist.
2. Set `GOOGLE_API_KEY` in `backend/.env`. No tenant API keys are needed for the fictional demo. Keep the key private. Change `DEMO_OPERATOR_PASSWORD` if the default is unsuitable.
3. From the repository root run `docker compose up --build`. This starts PostgreSQL, Redis, and FastAPI on port 8000.
4. In another terminal run `cd frontend && npm install && npm run dev`. Open `http://localhost:3000` and sign in with `demo@relay.example` / `DemoPass123!` unless you changed the demo credentials.

The backend seeds the demo workspace, its Acme Corp sample customer, two invoices, and six knowledge documents when it starts. Ask “What is our P1 SLA?” twice: the first request should show RAG + Gemini; the second should show Exact cache. Paraphrase it to try the semantic cache. Ask “Why did our bill increase in April?” twice: the first uses the invoice tool and the second hits Exact cache if the invoice snapshot is unchanged. Editing an invoice changes its cache fingerprint and forces a fresh tool lookup. Context-dependent follow-ups bypass both caches.

To run backend tests: `cd backend && python -m pytest -q` after installing `requirements.txt` and `pytest` in a virtual environment. To verify the UI: `cd frontend && npm run build`.

## Deploy

1. Push this repository to your Git provider.
2. In Render, create a Blueprint from `render.yaml`. Supply `GOOGLE_API_KEY`, a strong `DEMO_OPERATOR_PASSWORD`, and the eventual Vercel origin as `FRONTEND_ORIGIN`. The Blueprint provisions the API, PostgreSQL, and Redis-compatible Key Value service. The backend enables the supported `vector` extension and creates HNSW indexes at startup. Render's database URL is normalized to the installed psycopg driver by the backend.
3. In Vercel, import the same repository with **Root Directory** set to `frontend`. Set `API_BASE_URL` to the public Render API URL. Deploy. Vercel needs no tenant-key or Gemini-key variable. The Next.js server stores the operator's opaque session token in an HTTP-only cookie and forwards it to FastAPI.
4. Update `FRONTEND_ORIGIN` on Render to the final Vercel URL if it changed. Visit `/health` on the API, then open the Vercel app and ask a question.

The Gemini key remains on the backend. The browser never receives the Gemini key or the session token. The included password-based login is scoped to this fictional demo, not a production identity provider. For real customer data, add managed identity/SSO, password reset, audit logs, rate limiting, and reviewed migrations before launch.

## Current scope

On PostgreSQL, both RAG and semantic-cache similarity use 768-dimensional Gemini embeddings stored as pgvector columns and indexed with HNSW. The SQLite test suite uses an in-process cosine fallback. Semantic entries are scoped to tenant, customer, intent, and the current knowledge version. Exact cache is in Redis with a TTL; billing keys include a hash of the current invoice snapshot, while knowledge keys include a hash of the current documents. Changed documents are re-embedded on retrieval. Cached token savings are estimates based on the original answer's reported usage.

This MVP sends complete answers. Token streaming, rate limiting, background document indexing, a migration framework, and production identity integration are later work. Startup applies additive SQL for the previous demo schema, but future schema changes should use reviewed migrations.
