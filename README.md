# CompassX

**An open-source, agent-native data platform.**

[![License](https://img.shields.io/badge/license-TBD-lightgrey)](#license)

CompassX brings together notebooks, dashboards, a SQL warehouse, a unified catalog, and an AI data engineer (**Nova**) built into the platform from day one — not bolted on later. Think of it as a self-hosted alternative to Databricks, with an agent that can actually plan, write, and run your data work alongside you.

You can run it on anything from a single Postgres instance to a full Kubernetes deployment.

<!-- Add a screenshot or short GIF of Nova + notebook view here -->

## Where things stand

**This is early.** CompassX is in alpha. Core workflows work — notebooks, catalog, SQL execution, dashboards — but there are rough edges, and Nova itself is still maturing. We're releasing now because we'd rather build this in the open with real feedback than polish in private.

A few things we know are still shaky and are actively working on:
- Nova's tool-calling reliability on more complex, multi-step tasks
- The compute attach / kernel provisioning flow (moving toward zero manual setup)
- Permission enforcement across catalog objects (schema exists, enforcement is still landing)
- Upgrade path robustness across versions

If you hit something broken, that's expected — and exactly what we want to hear about.

## What we're looking for right now

We're not asking you to bet a production workload on this yet. We're asking you to try it, poke at it, and tell us what's wrong, missing, or confusing.

**If you're a data/platform engineer:** try the notebook → catalog → SQL warehouse flow. Load some data, write a query, build a small dashboard. Tell us where it breaks or where it doesn't match how you'd actually work.

**If you're into AI agents:** try Nova. Give it a real (or realistic) data task, watch how it plans, and see where the plan/checkpoint model holds up or falls apart. We're especially interested in cases where it does something surprising — good or bad.

**If you want to contribute code:** see [CONTRIBUTING.md](./CONTRIBUTING.md) for local dev setup, and check issues labeled `good-first-issue` and `help-wanted`.

## How to give feedback

The most useful feedback tells us:
1. What you were trying to do
2. What actually happened
3. What you expected instead

Open a [GitHub Issue](#) for bugs or specific breakage, or start a [Discussion](#) for broader thoughts, workflow gaps, or "here's what I wish this did." Both are welcome, and neither needs to be polished.

---

## ⚡ Quick Start with Docker (Recommended)

The fastest way to test and explore CompassX. No Python, Node.js, or virtual environments required — just Docker.

**Before you start:** first startup can take a few minutes depending on your machine while images pull and services come up. Recommended: 8GB+ RAM free, ~5GB disk.

### 1. Start Platform
```bash
git clone https://github.com/compassx-platform/compassx.git
cd compassx
docker compose -f deployments/docker-compose/docker-compose.yml up -d
```

### 2. Open the UI
Once the containers are up, open your browser:

👉 http://localhost:5173

### 3. Stop Platform
```bash
docker compose -f deployments/docker-compose/docker-compose.yml down
```

---

## 🚀 Your First 5 Minutes

Once the UI is up:

1. **Log in** with the default credentials shown in the setup output (or `admin` / `admin` if unset).
2. **Create a workspace** (or use the default one provided).
3. **Load some sample data.** If you don't have a dataset handy, grab the small CSV we've included at `samples/sample_data.csv` and upload it as a volume/table through the catalog UI.
4. **Open a new notebook** and run a simple query against the data you just loaded — this exercises the notebook → catalog → SQL warehouse path.
5. **Ask Nova to help.** In the notebook, open the Nova chat panel and try something like: *"Summarize this dataset and chart the top categories."* Watch how it plans, review the diff it proposes, and approve or reject it.

That's the core loop. If any of these five steps confused you, broke, or didn't do what you expected — that's exactly the feedback we want (see [How to give feedback](#how-to-give-feedback) above).

---

## Service Endpoints & Credentials

These are mainly for advanced use, debugging, and infrastructure inspection — most people only need the Frontend UI above.

> ⚠️ **Local development only.** The credentials below are insecure defaults meant for local testing. Do not use these in any exposed or shared deployment.

| Service | URL | Credentials / Notes |
|---|---|---|
| Frontend UI | http://localhost:5173 | Main user interface |
| Backend API Docs | http://localhost:8000/api/swagger/docs | Interactive Swagger UI |
| Backend Health | http://localhost:8000/healthcheck | API healthcheck endpoint |
| MinIO Console | http://localhost:9001 | User: `minioadmin` \| Pass: `minioadmin` |
| Airflow UI | http://localhost:8080 | User: `admin` \| Pass: `admin` |
| Enterprise Gateway | http://localhost:8888 | Jupyter kernel gateway |
| Prometheus | http://localhost:9090 | Metrics & cluster monitoring |
| PostgreSQL | localhost:5433 | User: `postgres` \| Pass: `postgres` |

---

## Deployment Options & Releases

All platform deployment configurations are located in `deployments/`:

- **Quick Test (Full Docker Compose Stack):** Standalone container deployment in `deployments/docker-compose/`.
  ```bash
  docker compose -f deployments/docker-compose/docker-compose.yml up -d
  ```
- **Local Development:** Run frontend & backend natively with containerized dependencies. See [CONTRIBUTING.md](./CONTRIBUTING.md).
- **Kubernetes Cloud Release (Helm Chart):** Production-grade Helm chart for AWS EKS, Azure AKS, and Google GKE in `deployments/helm/compassx/`.
  ```bash
  helm install compassx ./deployments/helm/compassx --namespace compassx
  ```

## Troubleshooting

**1. Docker Daemon is Not Running**
```
Error: Docker daemon is not running. Start Docker Desktop...
```
Solution: Open Docker Desktop and wait until the engine starts before running `docker compose` or `./compassx up`.

**2. macOS: Terminal Automation Permission Denied**
```
Error: Failed to open Terminal.app for 'backend'...
```
Solution: Open System Settings > Privacy & Security > Automation, find your terminal/IDE (e.g. VS Code, Terminal, iTerm), and toggle Terminal on.

**3. Port Already in Use**
```
Error: A required port is already in use by another process.
```
Solution: Ensure other database servers or conflicting processes aren't holding ports `5433`, `8000`, `5173`, `6379`, `9000`, `9001`, or `8080`. Run `docker compose down` or `./compassx down` to terminate previous sessions.

**4. Backend Python Not Found (Local Dev Mode)**
```
Error: Could not find a backend Python interpreter.
```
Solution: See [CONTRIBUTING.md](./CONTRIBUTING.md) for local dev environment setup.

## License

TBD — see [LICENSE](./LICENSE).