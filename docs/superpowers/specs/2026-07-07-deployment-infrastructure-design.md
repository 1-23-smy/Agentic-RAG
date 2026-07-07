# Deployment Infrastructure — Design

## Context

Agentic-RAG currently runs entirely locally: a single global document corpus, one set of LLM/parsing API keys in `.env`, and `docker-compose.yml` bringing up Qdrant + Redis + Neo4j for a single developer. The goal is to turn this into a live, deployed product that real users can sign up for and use — as a capstone project intended to demonstrate a fully functional, deployed system to recruiters.

This is the first of several sub-projects needed to get there (the others — auth & accounts, BYOK key management, and multi-tenant data isolation — will each get their own spec). This spec covers **where and how the system is hosted**, since that choice constrains how the later subsystems are built (e.g. Neo4j's free-tier instance limits force logical rather than physical per-user isolation).

## Goal

Design a deployment architecture that is:
- Real enough to demo live to recruiters without embarrassing cold-starts or broken links
- Affordable within an Azure student credit ($100 over 365 days)
- Compatible with the product decisions already made: BYOK (users supply their own LLM/parsing API keys, so the operator pays $0 for usage) and per-user private document corpora
- Able to keep Celery + Redis for genuine parallel ingestion processing (an explicit requirement — FastAPI `BackgroundTasks` was considered and rejected in favor of real worker parallelism)

## Decisions (confirmed during brainstorming)

- **Cost model:** BYOK. Each user supplies their own API keys; the operator never pays for LLM/parsing usage.
- **Data scope:** Per-user private document corpora, not one shared corpus.
- **Compute budget:** Azure student credit, $100 over 365 days. Sized for a comfortable VM (~4GB RAM) lasting roughly 3-4 months, prioritizing demo reliability over maximum credit lifespan.
- **Backend hosting:** Self-hosted on a single Azure VM via Docker Compose, rather than a patchwork of managed free tiers. This avoids Neo4j Aura's single-free-instance node/relationship cap and Qdrant Cloud's 1GB free-tier cap, and avoids cold-starts from free web-service tiers (e.g. Render).
- **Frontend hosting:** Stays on Vercel (free), separate from the VM. Vercel's CDN/image optimization/ISR and zero-effort CI/CD outweigh the benefit of unifying everything under one deployment surface; the only cost is a small CORS config on the FastAPI side.
- **Async ingestion:** Celery + Redis, retained as explicitly requested (not replaced with in-process background tasks), because real parallel processing across multiple users' concurrent uploads is a requirement, not just a nice-to-have.
- **Auth & per-user secrets storage:** Supabase free tier (Postgres + built-in Auth), independent of the VM. Full design deferred to the Auth & accounts sub-project spec, but the storage location and secret-handling pattern (see below) are locked in now because they affect this spec's secrets-management section.

## Architecture

| Component | Where | Notes |
|---|---|---|
| Next.js frontend | Vercel (free) | Auto-deploys on push to `main`; free preview deployments per branch/PR |
| FastAPI backend | Azure VM, Docker container | Always-on, no cold starts |
| Qdrant | Azure VM, Docker container (existing `docker-compose.yml` service) | Per-user collections; storage bounded only by VM disk, not a 1GB free-tier cap |
| Neo4j | Azure VM, Docker container (existing service) | Per-user logical isolation via a `user_id` property on every node/relationship and every Cypher query scoped by it — not physical per-user databases, since even self-hosted Neo4j Community Edition supports only one database easily |
| Redis | Azure VM, Docker container (existing service) | Celery broker + result backend |
| Celery worker | Azure VM, new Docker service (containerizing the existing `worker.py`) | Real parallelism via `--concurrency=N`, sized to the VM's vCPU count |
| Auth, user records, encrypted BYOK keys | Supabase free tier | Independent of the VM; full schema/flow designed in the Auth & accounts sub-project |
| PDF parsing / LLM calls | Each user's own BYOK key | $0 operator cost regardless of usage volume |

## VM specifics

- **Size:** Azure `Standard_B2s` (2 vCPU, 4GB RAM) — runs Qdrant + Neo4j + FastAPI (with its embedding model loaded) + Redis + Celery worker together without memory pressure. ~$30/month, consuming the $100 credit over roughly 3-4 months.
- **OS:** Ubuntu 22.04 LTS.
- **Networking:** Azure Network Security Group open only on 22 (SSH, restricted to the operator's IP where possible), 80/443 (HTTPS to the backend, via reverse proxy). Qdrant, Neo4j, and Redis ports are never exposed publicly — they stay on the internal Docker network, reachable only by the FastAPI and Celery containers.
- **Domain + TLS:** A Caddy reverse-proxy container in front of FastAPI, auto-provisioning Let's Encrypt certificates, so the backend is served over HTTPS at a real (sub)domain rather than a bare IP:port. A free DuckDNS subdomain is an acceptable substitute if a real domain isn't available yet.
- **Persistence:** Qdrant and Neo4j data volumes (already defined in `docker-compose.yml`) live on the VM's disk. There is no managed-service redundancy anymore, so VM/disk snapshots before risky changes are the operator's responsibility.

## Secrets & configuration management

Two distinct categories of secret, handled differently:

- **System-level secrets** — Supabase service-role key, Neo4j password, Qdrant API key (if set), and the master encryption key described below. These live in a single `.env` file on the VM (never committed; `docker-compose.yml` already uses this pattern via `env_file:`). The same values are duplicated into GitHub Actions repo secrets for anything the CI/CD pipeline needs to inject at deploy time.
- **Per-user BYOK API keys** — not environment variables. Stored encrypted at rest in a Supabase table (`user_api_keys`), encrypted with the single server-side master key mentioned above. The backend decrypts a given user's key in-memory only for the duration of the request or Celery task that needs it, and never logs or persists the plaintext value outside that encrypted column. This means a leaked log or crash dump cannot expose a user's OpenAI/Gemini/Anthropic/LlamaParse key, and rotating the master key is a single contained operation rather than something scattered across files.

## CI/CD

- **Frontend:** no custom pipeline — Vercel already auto-deploys `main` and provides preview URLs for other branches.
- **Backend:** a GitHub Actions workflow triggered on push to `main`:
  1. Run the existing Python `test_*.py` unittest suite as a gate; do not proceed if it fails.
  2. Build the FastAPI and Celery-worker Docker images, tag them by commit SHA, and push to GitHub Container Registry (`ghcr.io`).
  3. SSH into the Azure VM (using a deploy key stored as a GitHub Actions secret) and run `docker compose pull && docker compose up -d` to roll out the new images.
  4. Hit a `/health` endpoint on the backend after rollout; fail the workflow loudly if it doesn't return 200 within a short timeout, rather than leaving a broken deploy silently running.
- **Rollback:** images are tagged by commit SHA; the last 2-3 tags are kept on the registry/VM so a rollback is re-running the deploy step against a previous SHA rather than rebuilding from scratch.

## Testing / verification plan

- `docker compose up` locally, using the same compose file the VM runs, to catch integration issues before they reach the deploy pipeline.
- The existing `test_*.py` suite (parsing, chunking, storage, agent, ingestion) runs in CI as the automated gate.
- Manual smoke test after each real deploy: sign up as a test user, enter a test BYOK key, upload a small PDF, confirm the Celery worker picks it up and completes ingestion, then ask a question and confirm a cited answer returns.
- No automated frontend tests are planned, matching the existing project convention — frontend changes are verified manually in a live browser, the same way prior scroll-morph-hero work in this project was verified.

## Out of scope (deferred to their own specs)

- Auth & accounts (signup/login, session management) — only the storage location (Supabase) is locked in here.
- BYOK key management UI/flow (where/how a user enters and updates their API keys) — only the at-rest encryption pattern is locked in here.
- Multi-tenant data isolation implementation (the actual `user_id`-scoped Qdrant collections and Neo4j queries, and the per-user ingestion pipeline changes to `worker.py`/`ingestion/*`).
- Cost-control guardrails (per-user document/storage quotas to bound the operator's own Qdrant/Neo4j disk usage, since BYOK only covers LLM/parsing cost, not infrastructure cost).
