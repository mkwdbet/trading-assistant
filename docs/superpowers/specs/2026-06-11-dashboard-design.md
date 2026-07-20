# AlphaForge Dashboard Design

## Goal

Add a dark, information-dense web dashboard that turns the existing signal and outcome records into a research workspace for validating strategy quality.

## Architecture

The dashboard will be served by the existing FastAPI app to keep deployment simple. Backend analytics will live in a focused service module that reads the existing SQLite tables and returns API-ready dictionaries. The frontend will be static HTML, CSS, and JavaScript under `app/static/dashboard`, using Chart.js from a CDN.

## Pages

- Dashboard: headline counts, horizon returns, win rates, daily and cumulative signal charts.
- Signals: filterable signal table with symbol, direction, signal type, date range, and horizon returns.
- Signal Detail: modal-style detail view for one signal with all outcomes and entry metrics.
- Performance: symbol-level comparison.
- Strategy Analysis: signal-type comparison with the best signal highlighted.
- Research: top 20 winners and losers.
- Settings: tracked symbol and Discord webhook status structure for later management.

## API

- `GET /api/v1/dashboard`
- `GET /api/v1/signals` with added filters and outcome summaries
- `GET /api/v1/signals/{signal_id}`
- `GET /api/v1/performance`
- `GET /api/v1/strategy-analysis`
- `GET /api/v1/research`
- `GET /api/v1/settings`

## Data

Use the current `signals` and `signal_outcomes` tables. No new table is required for the first dashboard pass. Settings will return configured defaults and masked Discord status without exposing the webhook URL.

## UI Direction

Dark mode by default, TradingView-inspired, compact, readable, mobile responsive. Visual polish should come from typography, spacing, restrained borders, status colors, and charts rather than decorative graphics.

## Testing

Add service-level analytics tests with in-memory SQLite. Add API smoke coverage where the app can be exercised with dependency overrides. Verify the static dashboard assets load and the backend tests pass before deployment.
