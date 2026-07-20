# Backtest Lab MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first working Backtest Lab that can evaluate condition combinations against Binance candle data and report research metrics.

**Architecture:** Add focused modules for indicator calculation, condition registry, and a deterministic backtest engine. Expose registry and backtest APIs through the existing FastAPI app, then add a static dashboard page that calls those APIs.

**Tech Stack:** FastAPI, SQLAlchemy models for saved backtest runs, SQLite, httpx/Binance klines, vanilla HTML/CSS/JS.

---

### Task 1: Registry And Engine Tests

**Files:**
- Create: `tests/test_condition_registry.py`
- Create: `tests/test_backtest_engine.py`

- [ ] Write failing tests for condition registry metadata.
- [ ] Write failing tests for LONG TP, SHORT SL, and conservative same-candle SL handling.

### Task 2: Core Backtest Modules

**Files:**
- Create: `app/indicators/core.py`
- Create: `app/conditions/registry.py`
- Create: `app/backtest/models.py`
- Create: `app/backtest/engine.py`

- [ ] Implement SMA, RSI, ATR helpers.
- [ ] Implement condition registry with MA, RSI, volume, and ATR condition descriptors.
- [ ] Implement backtest input/result dataclasses.
- [ ] Implement engine using selected conditions, ATR stop, risk-reward target, and max holding time.

### Task 3: API And Persistence

**Files:**
- Modify: `app/db/models.py`
- Modify: `app/db/session.py`
- Modify: `app/api/routes.py`
- Create: `app/services/backtest_service.py`

- [ ] Add `backtest_runs` table.
- [ ] Add `GET /api/v1/conditions`.
- [ ] Add `POST /api/v1/backtests/run`.
- [ ] Store summary and trades JSON for later review.

### Task 4: Dashboard UI

**Files:**
- Modify: `app/static/dashboard/index.html`
- Modify: `app/static/dashboard/styles.css`
- Modify: `app/static/dashboard/app.js`

- [ ] Add Backtest Lab menu item.
- [ ] Add controls for symbol, date range, direction, conditions, ATR multiplier, R:R, and max holding hours.
- [ ] Render metrics and trades table.

### Task 5: Verification And Deployment

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`

- [ ] Run tests and Ruff.
- [ ] Smoke test local API.
- [ ] Deploy changed files to AWS and smoke test production endpoints.
