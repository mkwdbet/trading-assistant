# Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dark research dashboard for inspecting AlphaForge signals, outcomes, and strategy performance.

**Architecture:** Keep the existing FastAPI deployment. Add a backend analytics service over SQLite, expose research APIs, and serve a static Chart.js dashboard from the same app.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, vanilla HTML/CSS/JS, Chart.js CDN.

---

### Task 1: Analytics Service

**Files:**
- Create: `app/services/dashboard_analytics.py`
- Test: `tests/test_dashboard_analytics.py`

- [ ] Write tests that seed signals and outcomes into in-memory SQLite and assert dashboard totals, horizon summaries, symbol performance, strategy analysis, and research rankings.
- [ ] Implement aggregation helpers grouped by horizon, symbol, direction, and analysis signal type.
- [ ] Run `python -m pytest tests/test_dashboard_analytics.py -q`.

### Task 2: API Routes

**Files:**
- Modify: `app/api/routes.py`
- Modify: `app/services/signal_repository.py`

- [ ] Extend `/signals` filters for direction, signal type, and date range while preserving existing behavior.
- [ ] Add dashboard, signal detail, performance, strategy analysis, research, and settings endpoints.
- [ ] Run focused API or service tests plus existing tests.

### Task 3: Static Dashboard

**Files:**
- Modify: `app/main.py`
- Create: `app/static/dashboard/index.html`
- Create: `app/static/dashboard/styles.css`
- Create: `app/static/dashboard/app.js`

- [ ] Mount static files and redirect `/dashboard` to the dashboard HTML.
- [ ] Build dark responsive navigation and page sections.
- [ ] Fetch APIs and render cards, tables, detail modal, settings status, and charts.
- [ ] Verify in browser at `http://localhost:8000/dashboard`.

### Task 4: Deployment

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/aws_deployment.md`

- [ ] Document local run, dashboard URL, API structure, and AWS deploy command.
- [ ] Run tests and lint.
- [ ] Deploy to AWS with the existing Docker Compose flow.
- [ ] Smoke test `/health`, `/dashboard`, and one analytics API.
