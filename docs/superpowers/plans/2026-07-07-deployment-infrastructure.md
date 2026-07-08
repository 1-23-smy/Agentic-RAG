# Deployment Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Containerize the existing FastAPI + Celery + Qdrant + Neo4j + Redis stack and make it deployable, always-on, and HTTPS-reachable on a single Azure VM, with a CI/CD pipeline that tests, builds, and rolls out changes automatically.

**Architecture:** One shared Docker image (built from the existing Python codebase) runs as two services — `backend` (uvicorn/FastAPI) and `celery-worker` (Celery, real parallel processing) — alongside the existing `qdrant`, `redis`, and `neo4j` services already defined in `docker-compose.yml`. A `caddy` reverse-proxy service terminates HTTPS and forwards to `backend`. GitHub Actions tests, builds, pushes images to `ghcr.io`, and deploys over SSH on every push to `main`. The Next.js frontend on Vercel is unchanged and calls this backend over HTTPS.

**Tech Stack:** Docker, Docker Compose, Caddy 2, GitHub Actions, `docker/build-push-action`, `appleboy/ssh-action`, Azure VM (Ubuntu 22.04, `Standard_B2s`).

## Global Constraints

- VM size is Azure `Standard_B2s` (2 vCPU, 4GB RAM), OS Ubuntu 22.04 LTS — per `docs/superpowers/specs/2026-07-07-deployment-infrastructure-design.md`.
- Only ports 22 (SSH), 80, and 443 are ever exposed to the public internet. Qdrant, Neo4j, and Redis must not be reachable from outside the VM.
- Celery + Redis are retained for real parallel ingestion processing — do not replace with in-process background tasks.
- The Next.js frontend stays on Vercel; no frontend code changes in this plan.
- Auth, BYOK key management, and multi-tenant data isolation are explicitly out of scope for this plan (see spec's "Out of scope" section) — do not add Supabase integration, user tables, or per-user Qdrant/Neo4j scoping here.
- The existing `test_*.py` unittest suite must keep passing after every task.
- Follow the existing test-stubbing convention in this codebase (see `test_ingest_api.py`, `test_worker_config.py`): stub external modules via `sys.modules`, snapshot/restore module state in `setUp`/`tearDown`.

---

### Task 1: Parameterize the Celery broker/backend URL

**Files:**
- Modify: `worker.py:15-20`
- Test: `test_worker_config.py`

**Interfaces:**
- Produces: `worker.py` reads `REDIS_URL` from the environment (default `"redis://localhost:6379/0"`), used as both the Celery `broker` and `backend` argument. Later tasks (Task 4's `docker-compose.yml`) rely on setting `REDIS_URL=redis://redis:6379/0` for the containerized services.

Currently `worker.py` hardcodes `broker='redis://localhost:6379/0'` and `backend='redis://localhost:6379/0'`. Inside Docker Compose, `localhost` inside the `backend`/`celery-worker` containers refers to the container itself, not the `redis` service — this must become configurable so the containerized deployment can point it at the `redis` service by name while local (non-Docker) development keeps working unchanged.

- [ ] **Step 1: Write the failing tests**

Open `test_worker_config.py` and make these two changes:

Add `import os` to the top imports (currently missing):

```python
import importlib
import os
import sys
import types
import unittest
from pathlib import Path
```

Update `FakeCelery` to capture the constructor arguments so tests can assert on them:

```python
class FakeCelery:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.conf = {}

    def task(self, *args, **kwargs):
        return lambda fn: fn
```

Add `REDIS_URL` snapshot/restore to `setUp`/`tearDown` (matching this file's existing module snapshot/restore pattern), and two new test methods at the end of the `WorkerConfigTest` class:

```python
    def setUp(self):
        self.original_redis_url = os.environ.get("REDIS_URL")
        self.original_modules = {
            name: sys.modules.get(name)
            for name in [
                "celery",
                "dotenv",
                "ingestion",
                "ingestion.parser",
                "ingestion.chunker",
                "ingestion.graph_extractor",
                "storage",
                "storage.vector_store",
                "storage.graph_store",
                "worker",
            ]
        }

        celery = types.ModuleType("celery")
        celery.Celery = FakeCelery
        sys.modules["celery"] = celery

        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = lambda *args, **kwargs: None
        sys.modules["dotenv"] = dotenv

        parser = types.ModuleType("ingestion.parser")
        parser.MedicalDocumentParser = object
        chunker = types.ModuleType("ingestion.chunker")
        chunker.HierarchicalChunker = object
        graph_extractor = types.ModuleType("ingestion.graph_extractor")
        graph_extractor.GraphExtractor = object
        sys.modules["ingestion"] = types.ModuleType("ingestion")
        sys.modules["ingestion.parser"] = parser
        sys.modules["ingestion.chunker"] = chunker
        sys.modules["ingestion.graph_extractor"] = graph_extractor

        vector_store = types.ModuleType("storage.vector_store")
        vector_store.VectorStoreManager = object
        graph_store = types.ModuleType("storage.graph_store")
        graph_store.GraphStoreManager = object
        sys.modules["storage"] = types.ModuleType("storage")
        sys.modules["storage.vector_store"] = vector_store
        sys.modules["storage.graph_store"] = graph_store

        sys.modules.pop("worker", None)

    def tearDown(self):
        sys.modules.pop("worker", None)
        for name, module in self.original_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        if self.original_redis_url is None:
            os.environ.pop("REDIS_URL", None)
        else:
            os.environ["REDIS_URL"] = self.original_redis_url

    def test_worker_adds_project_root_to_import_path(self):
        worker = importlib.import_module("worker")

        self.assertEqual(worker.PROJECT_ROOT, Path(worker.__file__).resolve().parent)
        self.assertIn(str(worker.PROJECT_ROOT), sys.path)

    def test_worker_uses_default_redis_url_when_env_not_set(self):
        os.environ.pop("REDIS_URL", None)

        worker = importlib.import_module("worker")

        self.assertEqual(worker.app.kwargs["broker"], "redis://localhost:6379/0")
        self.assertEqual(worker.app.kwargs["backend"], "redis://localhost:6379/0")

    def test_worker_uses_redis_url_env_var_when_set(self):
        os.environ["REDIS_URL"] = "redis://redis:6379/0"

        worker = importlib.import_module("worker")

        self.assertEqual(worker.app.kwargs["broker"], "redis://redis:6379/0")
        self.assertEqual(worker.app.kwargs["backend"], "redis://redis:6379/0")
```

(The existing `test_worker_adds_project_root_to_import_path` method is shown above unchanged, for placement context — only add the two new methods after it and apply the `setUp`/`tearDown`/import changes above it.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest test_worker_config.py -v`
Expected: `test_worker_uses_default_redis_url_when_env_not_set` and `test_worker_uses_redis_url_env_var_when_set` FAIL with `KeyError: 'broker'` (since `FakeCelery` doesn't yet capture `kwargs`, or `worker.py` doesn't yet read `REDIS_URL`).

- [ ] **Step 3: Implement the minimal code change**

In `worker.py`, replace:

```python
app = Celery(
    'rag_ingestion_worker',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)
```

with:

```python
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    'rag_ingestion_worker',
    broker=REDIS_URL,
    backend=REDIS_URL
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest test_worker_config.py -v`
Expected: all tests PASS (`OK`).

- [ ] **Step 5: Run the full existing test suite to check for regressions**

Run: `python -m unittest test_agent.py test_agent_query.py test_config.py test_ingest_api.py test_ingestion.py test_storage.py test_tools.py test_trace.py test_vector_store.py test_worker_config.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add worker.py test_worker_config.py
git commit -m "feat: make Celery broker/backend URL configurable via REDIS_URL"
```

---

### Task 2: Add a `/health` endpoint

**Files:**
- Modify: `main.py:89-91`
- Test: `test_ingest_api.py`

**Interfaces:**
- Produces: `GET /health` on the FastAPI app, returning `{"status": "ok"}`. Task 7's GitHub Actions workflow calls this endpoint after deploy to confirm the rollout succeeded.

- [ ] **Step 1: Write the failing test**

Add this test method to the `IngestApiTest` class in `test_ingest_api.py` (place it near `test_upload_rejects_non_pdf`, using the same `self.main` fixture from `setUp`):

```python
    def test_health_returns_ok(self):
        result = asyncio.run(self.main.health())

        self.assertEqual(result, {"status": "ok"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest test_ingest_api.IngestApiTest.test_health_returns_ok -v`
Expected: FAIL with `AttributeError: module 'main' has no attribute 'health'`.

- [ ] **Step 3: Implement the endpoint**

In `main.py`, immediately after the existing `root()` endpoint:

```python
@app.get("/")
async def root():
    return {"message": "Agentic RAG Backend is Live and Running!"}

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest test_ingest_api.IngestApiTest.test_health_returns_ok -v`
Expected: PASS.

- [ ] **Step 5: Run the full existing test suite to check for regressions**

Run: `python -m unittest test_agent.py test_agent_query.py test_config.py test_ingest_api.py test_ingestion.py test_storage.py test_tools.py test_trace.py test_vector_store.py test_worker_config.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add main.py test_ingest_api.py
git commit -m "feat: add /health endpoint for deploy verification"
```

---

### Task 3: Add the shared Dockerfile

**Files:**
- Create: `Dockerfile`

**Interfaces:**
- Produces: a Docker image containing the full Python codebase and dependencies, with `BAAI/bge-small-en-v1.5` pre-downloaded at build time. Task 4's `docker-compose.yml` builds `backend` and `celery-worker` from this same image with different `command:` overrides.

- [ ] **Step 1: Create the Dockerfile**

Create `Dockerfile` at the repo root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model at build time so containers don't need
# network access on every restart and startup isn't slowed by a cold
# Hugging Face download.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Build the image to verify it succeeds**

Run: `docker build -t agentic-rag-backend:test .`
Expected: build completes with `Successfully tagged agentic-rag-backend:test` (this step downloads and installs all of `requirements.txt` plus the embedding model, so it will take several minutes the first time).

- [ ] **Step 3: Verify the embedding model was actually pre-downloaded**

Run: `docker run --rm agentic-rag-backend:test python -c "from sentence_transformers import SentenceTransformer; import time; t=time.time(); SentenceTransformer('BAAI/bge-small-en-v1.5'); print('loaded in', time.time()-t, 'seconds, offline:', True)"`
Expected: prints a load time of a few seconds with no network-download progress bar (confirms the model was baked into the image rather than fetched fresh).

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat: add Dockerfile for backend and Celery worker images"
```

---

### Task 4: Add `backend`, `celery-worker`, and `caddy` services to Docker Compose

**Files:**
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: `Dockerfile` (Task 3), `REDIS_URL` env var support in `worker.py` (Task 1), `/health` endpoint (Task 2).
- Produces: a `docker compose up -d` that brings up the full stack — `qdrant`, `redis`, `neo4j`, `backend`, `celery-worker`, `caddy` — with only `caddy`'s ports 80/443 reachable from outside the VM, and `qdrant`/`neo4j` bound to `127.0.0.1` only (reachable via SSH tunnel for debugging, not from the public internet). Task 7's CI/CD workflow runs `docker compose pull backend celery-worker && docker compose up -d` against this file on the VM.

- [ ] **Step 1: Replace `docker-compose.yml` with the full updated file**

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: medscan-qdrant
    ports:
      - "127.0.0.1:6333:6333"
      - "127.0.0.1:6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped
    environment:
      QDRANT_ALLOW_ANONYMOUS_READ: "true"

  redis:
    image: redis:alpine
    container_name: medscan-redis
    restart: unless-stopped

  neo4j:
    image: neo4j:latest
    container_name: medscan-neo4j
    ports:
      - "127.0.0.1:7474:7474"
      - "127.0.0.1:7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password123
    volumes:
      - neo4j_data:/data
    restart: unless-stopped

  backend:
    build: .
    image: ghcr.io/OWNER/REPO:${IMAGE_TAG:-latest}
    container_name: medscan-backend
    command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
    env_file:
      - .env
    environment:
      REDIS_URL: redis://redis:6379/0
      QDRANT_URL: http://qdrant:6333
    depends_on:
      - qdrant
      - redis
      - neo4j
    restart: unless-stopped
    volumes:
      - ./data:/app/data

  celery-worker:
    build: .
    image: ghcr.io/OWNER/REPO:${IMAGE_TAG:-latest}
    container_name: medscan-celery-worker
    command: ["celery", "-A", "worker.app", "worker", "--loglevel=info", "--concurrency=2"]
    env_file:
      - .env
    environment:
      REDIS_URL: redis://redis:6379/0
      QDRANT_URL: http://qdrant:6333
    depends_on:
      - qdrant
      - redis
      - neo4j
    restart: unless-stopped
    volumes:
      - ./data:/app/data

  caddy:
    image: caddy:2-alpine
    container_name: medscan-caddy
    ports:
      - "80:80"
      - "443:443"
    environment:
      DOMAIN: ${DOMAIN}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  qdrant_data:
    driver: local
  neo4j_data:
    driver: local
  caddy_data:
    driver: local
  caddy_config:
    driver: local
```

Replace `OWNER/REPO` with the actual lowercase GitHub `owner/repository` (e.g. `srdasdev/agentic-rag`) — this is what Task 7's CI pipeline pushes to and what the VM pulls from. Both `build:` and `image:` are set on `backend`/`celery-worker` intentionally: local `docker compose up --build` builds from source (used in Step 2 below and Task 9), while the VM's deploy step (Task 7/8) uses `docker compose pull` to fetch the CI-built image instead of rebuilding on the VM's limited CPU. The image tag is `${IMAGE_TAG:-latest}` rather than a hardcoded `:latest` — Task 7's deploy script sets `IMAGE_TAG` to the commit SHA on every deploy, and Task 8's runbook documents how to roll back by re-running with a previous SHA.

Both `backend` and `celery-worker` mount the same `./data:/app/data` host directory — `backend`'s `/ingest/upload` endpoint writes uploaded PDFs to `data/raw/`, and since they're separate containers, `celery-worker` can only see that file if it's mounted from the same host path rather than baked into either container's own image layer.

- [ ] **Step 2: Validate the compose file and confirm the new services build**

Run: `docker compose config --quiet && echo "valid"`
Expected: prints `valid` with no errors (confirms YAML syntax and variable interpolation are correct — `DOMAIN` will show as empty since it's not set yet, that's fine at this step).

Run: `docker compose build backend celery-worker`
Expected: both build successfully, reusing the same image layers from Task 3's `docker build`.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add backend, celery-worker, and caddy services to docker-compose"
```

---

### Task 5: Add the Caddyfile

**Files:**
- Create: `Caddyfile`

**Interfaces:**
- Consumes: `DOMAIN` env var (referenced by `docker-compose.yml`'s `caddy` service from Task 4).
- Produces: HTTPS termination and reverse-proxying to the `backend` service.

- [ ] **Step 1: Create the Caddyfile**

Create `Caddyfile` at the repo root:

```
{$DOMAIN} {
	reverse_proxy backend:8000
}
```

Caddy automatically obtains and renews a Let's Encrypt TLS certificate for whatever hostname `DOMAIN` resolves to, as long as that hostname's DNS A record points at the VM's public IP and ports 80/443 are reachable — no manual certificate steps needed.

- [ ] **Step 2: Verify the syntax locally**

Run: `docker run --rm -v "$(pwd)/Caddyfile:/etc/caddy/Caddyfile" caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile`
Expected: prints `Valid configuration` (this only checks syntax — it does not require `DOMAIN` to be set or reachable).

- [ ] **Step 3: Commit**

```bash
git add Caddyfile
git commit -m "feat: add Caddyfile for HTTPS reverse proxy to backend"
```

---

### Task 6: Update `.env.example` with deployment variables

**Files:**
- Modify: `.env.example`

**Interfaces:**
- Produces: documented `REDIS_URL` and `DOMAIN` variables that the operator copies into the VM's real `.env` (Task 8's runbook references these).

- [ ] **Step 1: Add the new variables**

Append to `.env.example` (after the existing `FRONTEND_ORIGIN` line):

```
# Deployment (Azure VM / docker-compose)
# Set to redis://redis:6379/0 when running via docker-compose; defaults to
# redis://localhost:6379/0 for local (non-Docker) development.
REDIS_URL=redis://redis:6379/0

# Public hostname the Caddy reverse proxy obtains a TLS certificate for.
# Must have a DNS A record pointing at the VM's public IP.
DOMAIN=api.yourdomain.com
```

Also update the existing `FRONTEND_ORIGIN` line's context — change:

```
# Frontend
FRONTEND_ORIGIN=http://localhost:3000
```

to:

```
# Frontend (set to your Vercel deployment URL in production, e.g.
# https://your-app.vercel.app)
FRONTEND_ORIGIN=http://localhost:3000
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: document REDIS_URL and DOMAIN deployment variables"
```

---

### Task 7: Add the GitHub Actions CI/CD workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: `/health` endpoint (Task 2), `ghcr.io/OWNER/REPO:${IMAGE_TAG:-latest}` image reference (Task 4).
- Produces: automatic test → build → push → SSH deploy → health-check pipeline on every push to `main`, exporting `IMAGE_TAG=<commit-sha>` on the VM before `docker compose pull`/`up` so `docker-compose.yml`'s `${IMAGE_TAG:-latest}` picks up that exact build. Requires four GitHub Actions repo secrets that don't exist yet: `AZURE_VM_HOST`, `AZURE_VM_USER`, `AZURE_VM_SSH_KEY`, `DOMAIN` — Task 8's runbook covers adding these once the VM exists, and also covers rolling back to a previous SHA.

- [ ] **Step 1: Create the workflow file**

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Backend

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run test suite
        run: |
          python -m unittest test_agent.py test_agent_query.py test_config.py \
            test_ingest_api.py test_ingestion.py test_storage.py test_tools.py \
            test_trace.py test_vector_store.py test_worker_config.py -v

  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push backend image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:${{ github.sha }}
            ghcr.io/${{ github.repository }}:latest

      - name: Deploy to Azure VM
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.AZURE_VM_HOST }}
          username: ${{ secrets.AZURE_VM_USER }}
          key: ${{ secrets.AZURE_VM_SSH_KEY }}
          script: |
            cd ~/Agentic-RAG
            git pull origin main
            echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
            export IMAGE_TAG=${{ github.sha }}
            docker compose pull backend celery-worker
            docker compose up -d
            for i in $(seq 1 10); do
              if curl -fs "https://${{ secrets.DOMAIN }}/health"; then
                echo "Health check passed"
                exit 0
              fi
              sleep 3
            done
            echo "Health check failed after deploy"
            exit 1
```

- [ ] **Step 2: Validate the YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml')); print('valid')"`
Expected: prints `valid` with no exception. (This only checks YAML syntax; the workflow can't run end-to-end until the four secrets in Task 8 exist and there's a real VM to deploy to — that's exercised for the first time in Task 9's local pass and then for real once Task 8 is complete.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "feat: add CI/CD workflow to test, build, and deploy the backend"
```

---

### Task 8: Write the Azure VM provisioning runbook

**Files:**
- Create: `docs/deployment/azure-vm-provisioning.md`

**Interfaces:**
- Consumes: `docker-compose.yml` (Task 4), `Caddyfile` (Task 5), `.env.example` (Task 6), `.github/workflows/deploy.yml` (Task 7).
- Produces: a step-by-step runbook a human follows once to stand up the VM and wire it to the CI/CD pipeline. This is a documentation deliverable, not code — there is no automated test for it, but each command must be copy-paste-correct.

- [ ] **Step 1: Write the runbook**

Create `docs/deployment/azure-vm-provisioning.md`:

```markdown
# Azure VM Provisioning Runbook

One-time setup to stand up the Azure VM that hosts the backend stack
(FastAPI, Qdrant, Neo4j, Redis, Celery worker, Caddy), per
`docs/superpowers/specs/2026-07-07-deployment-infrastructure-design.md`.

## 1. Create the VM

Using the Azure CLI (`az login` first if you haven't):

​```bash
az group create --name agentic-rag-rg --location eastus

az vm create \
  --resource-group agentic-rag-rg \
  --name agentic-rag-vm \
  --image Ubuntu2204 \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys
​```

Note the `publicIpAddress` printed in the output — you'll need it below.

## 2. Open only the required ports

​```bash
az vm open-port --resource-group agentic-rag-rg --name agentic-rag-vm --port 80 --priority 100
az vm open-port --resource-group agentic-rag-rg --name agentic-rag-vm --port 443 --priority 110
​```

Port 22 (SSH) is open by default on `az vm create`. Do not open any other
ports — Qdrant, Neo4j, and Redis must stay unreachable from the public
internet (they're bound to `127.0.0.1` in `docker-compose.yml`, and
restricting the NSG to 22/80/443 is a second layer of defense on top of
that).

## 3. Point your domain at the VM

Create a DNS A record for the hostname you'll use (e.g. `api.yourdomain.com`)
pointing at the VM's public IP from Step 1. If you don't have a domain yet,
a free DuckDNS subdomain works the same way.

## 4. Install Docker and Docker Compose on the VM

SSH in and install Docker:

​```bash
ssh azureuser@<VM_PUBLIC_IP>

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit
​```

Log back in (`ssh azureuser@<VM_PUBLIC_IP>`) so the group change takes
effect, then confirm:

​```bash
docker --version
docker compose version
​```

## 5. Clone the repo and configure `.env`

​```bash
git clone https://github.com/OWNER/REPO.git Agentic-RAG
cd Agentic-RAG
cp .env.example .env
```

Edit `.env` and fill in real values for every key — your own LLM/parsing
API keys (this is the operator's own set, used until the BYOK subsystem
from the deployment spec's "out of scope" list is built), `REDIS_URL=redis://redis:6379/0`,
`DOMAIN=api.yourdomain.com` (matching Step 3), and
`FRONTEND_ORIGIN=https://your-app.vercel.app` (your actual Vercel URL).

## 6. First deploy

​```bash
docker compose up -d --build
​```

This builds the `backend`/`celery-worker` images locally the first time
(subsequent deploys from CI will `docker compose pull` a pre-built image
instead — see step 8). Confirm everything is healthy:

​```bash
docker compose ps
curl https://api.yourdomain.com/health
​```

Expected: `docker compose ps` shows all six services as `Up`/`running`,
and the `curl` returns `{"status":"ok"}`. The first TLS certificate
request from Caddy can take up to a minute — retry the `curl` if it
fails immediately after `docker compose up`.

## 7. Add GitHub Actions secrets

In the GitHub repo, go to Settings → Secrets and variables → Actions, and
add:

| Secret | Value |
|---|---|
| `AZURE_VM_HOST` | the VM's public IP from Step 1 |
| `AZURE_VM_USER` | `azureuser` |
| `AZURE_VM_SSH_KEY` | the **private** key from `~/.ssh/id_rsa` generated by `az vm create --generate-ssh-keys` on the machine you ran Step 1 from (not the VM) |
| `DOMAIN` | the hostname from Step 3, e.g. `api.yourdomain.com` |

## 8. Verify CI/CD end-to-end

Push any small change to `main` and watch the "Deploy Backend" workflow
run in the GitHub Actions tab. It should: run the test suite, build and
push the image to `ghcr.io`, SSH into the VM, pull the new image, restart
the containers, and confirm `/health` responds — all without manual
intervention.

## 9. Rolling back a bad deploy

Every image is tagged with the commit SHA it was built from (in addition
to `:latest`), and `docker-compose.yml` reads the tag to run from the
`IMAGE_TAG` environment variable (defaulting to `latest`). To roll back,
find the previous good commit's SHA (`git log --oneline` on your local
machine), then SSH into the VM and run:

​```bash
ssh azureuser@<VM_PUBLIC_IP>
cd ~/Agentic-RAG
export IMAGE_TAG=<previous-good-commit-sha>
docker compose pull backend celery-worker
docker compose up -d
curl https://api.yourdomain.com/health
​```

This rolls the `backend` and `celery-worker` containers back to that
exact previous build without rebuilding or touching `qdrant`/`neo4j`/
`redis`'s data. The next push to `main` will deploy forward again with a
new `IMAGE_TAG`, overriding this manual rollback.
​```

- [ ] **Step 2: Review the runbook for copy-paste correctness**

Read through every command block once as if you were a new operator with
no prior context, and confirm: no placeholder values remain except the
ones explicitly marked as user-specific (`OWNER/REPO`, `<VM_PUBLIC_IP>`,
`api.yourdomain.com`), and each command's prerequisites are stated before
it's used (e.g. `az login` before any `az` command).

- [ ] **Step 3: Commit**

```bash
git add docs/deployment/azure-vm-provisioning.md
git commit -m "docs: add Azure VM provisioning runbook"
```

---

### Task 9: Full local integration verification

**Files:** none (verification only — no new files).

**Interfaces:**
- Consumes: every artifact from Tasks 1-6 (`Dockerfile`, `docker-compose.yml`, `Caddyfile`, `.env.example`, the `REDIS_URL`-aware `worker.py`, the `/health` endpoint).

This is the final deliverable tying everything together: prove the full
containerized stack works end-to-end on a local machine before it's ever
pushed to the Azure VM, exactly as recommended in the spec's testing
section ("`docker compose up` locally first... to catch integration
issues before they reach the deploy pipeline").

- [ ] **Step 1: Configure a local `.env`**

```bash
cp .env.example .env
```

Fill in real API keys (`LLAMA_CLOUD_API_KEY`, `GEMINI_API_KEY`, etc.) —
these are the operator's own keys for this local verification pass, not
end-user BYOK keys (that subsystem doesn't exist yet). Set
`REDIS_URL=redis://redis:6379/0` and leave `DOMAIN` unset (Caddy isn't
being exercised in this local pass — see Step 4).

- [ ] **Step 2: Bring up the full stack**

Run: `docker compose up -d --build qdrant redis neo4j backend celery-worker`
Expected: all five services start; `docker compose ps` shows each as
`Up`/`running` with no immediate restarts (a crash-looping container
shows a rapidly increasing `Up X seconds` reset in `docker compose ps`
run twice a few seconds apart).

- [ ] **Step 3: Verify the backend responds**

Run: `curl http://localhost:8000/health`
Expected: `{"status":"ok"}`

Run: `curl http://localhost:8000/`
Expected: `{"message":"Agentic RAG Backend is Live and Running!"}`

- [ ] **Step 4: Verify the Celery worker is consuming the queue**

Run: `docker compose logs celery-worker | tail -20`
Expected: log lines showing the worker connected to
`redis://redis:6379/0` and is ready (Celery prints a banner including
`[queues] .> celery` and `celery@<hostname> ready.` on successful
startup).

- [ ] **Step 5: Verify an end-to-end ingestion request**

Place a small PDF at `data/raw/test.pdf`, then run:

```bash
curl -X POST http://localhost:8000/ingest/upload -F "file=@data/raw/test.pdf"
```

Expected: a JSON response with a `task_id` and `"status":"queued"`. Then
poll (substituting the real `task_id`):

```bash
curl http://localhost:8000/ingest/status/<task_id>
```

Expected: `status` moves from `PENDING`/`STARTED` to `SUCCESS` within a
few minutes (parsing + chunking + graph extraction + embedding all run
for real here, using the operator's own API keys from Step 1).

- [ ] **Step 6: Tear down**

Run: `docker compose down`
Expected: all containers stop and are removed; `qdrant_data`/`neo4j_data`
volumes persist (confirm with `docker volume ls`) so data survives a
restart, matching the spec's persistence requirement.

- [ ] **Step 7: Commit** (only if Steps 1-6 required any fixes to committed files)

```bash
git add -A
git commit -m "fix: address issues found during local integration verification"
```

If no fixes were needed, skip this step — verification-only tasks don't
require an empty commit.
