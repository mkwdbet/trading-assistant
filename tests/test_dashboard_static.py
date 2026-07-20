from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_uses_alphaforge_branding() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")

    assert "<title>AlphaForge Strategy Research Lab</title>" in html
    assert "<strong>AlphaForge</strong>" in html
    assert "<span>Strategy Research Lab</span>" in html
    assert "<h1>AlphaForge Research Lab</h1>" in html
    assert "Research. Validate. Deploy." in html
    assert "Build, backtest, and validate crypto trading strategies." in html
    assert "TradingAssistant" not in html
    assert "Signal Research Lab" not in html
    assert "신호 검증 연구실" not in html
    assert "전략 검증 연구실" not in html


def test_backtest_lab_uses_date_only_kst_inputs_and_holding_presets() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")

    assert 'name="start_date" type="date"' in html
    assert 'name="end_date" type="date"' in html
    assert 'name="start_time" type="datetime-local"' not in html
    assert 'name="end_time" type="datetime-local"' not in html
    assert 'data-holding="infinite"' in html
    assert 'data-holding="custom"' in html
    assert "kstDateRangeToUtcIso" in js
    assert "resolveMaxHoldingHours" in js


def test_backtest_lab_has_parameterized_condition_builder() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")

    assert 'id="conditionTypeSelect"' in html
    assert 'id="conditionParamFields"' in html
    assert 'id="addConditionButton"' in html
    assert 'id="selectedConditionList"' in html
    assert "entry_conditions" in js
    assert "renderConditionParamFields" in js
    assert "duplicateCondition" in js


def test_backtest_lab_has_ma_ordering_expression_builder() -> None:
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/dashboard/styles.css").read_text(encoding="utf-8")

    assert "renderMaOrderingBuilder" in js
    assert "maExpressionPreview" in js
    assert "addMaOrderingItem" in js
    assert "moveMaOrderingItem" in js
    assert "maOrderingPreview" in js
    assert "Price > SMA21 > SMA60" in js
    assert "Duplicate" in js
    assert ".ma-expression-builder" in css
    assert ".expression-preview" in css


def test_backtest_lab_exposes_research_timeframes() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")

    assert 'name="timeframe"' not in html
    assert "resolveBacktestTimeframe" in js
    for value in ["1h", "4h", "12h", "1d", "3d", "1w", "1M"]:
        assert value in js


def test_backtest_lab_has_aligned_control_grids() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    css = (ROOT / "app/static/dashboard/styles.css").read_text(encoding="utf-8")

    assert 'class="backtest-form primary-controls"' in html
    assert 'class="holding-control full-row"' in html
    assert 'class="condition-param-grid aligned-param-grid"' in html
    assert ".primary-controls" in css
    assert ".full-row" in css
    assert ".holding-buttons" in css
    assert ".aligned-param-grid" in css


def test_exit_optimizer_hides_single_backtest_controls() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/dashboard/styles.css").read_text(encoding="utf-8")

    assert html.count("data-single-backtest") >= 3
    assert 'name="atr_multiplier"' in html
    assert 'name="risk_reward_ratio"' in html
    assert "Run Backtest" in html
    assert "setBacktestMode" in js
    assert "[data-single-backtest]" in js
    assert "singleBacktestHidden" in js
    assert ".single-backtest-hidden" in css


def test_backtest_lab_has_strategy_preset_controls() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")

    assert 'id="backtestStrategySelect"' in html
    assert 'id="saveBacktestStrategyButton"' in html
    assert 'id="deleteBacktestStrategyButton"' in html
    assert "backtestStrategies" in js
    assert "saveBacktestStrategy" in js
    assert "loadBacktestStrategies" in js
    assert "applyBacktestStrategy" in js


def test_backtest_lab_has_run_management_and_strategy_performance() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")

    assert 'id="backtestRunsTable"' in html
    assert 'id="strategyPerformanceTable"' in html
    assert "backtests:" in js
    assert "backtestStrategyPerformance" in js
    assert "loadBacktestRuns" in js
    assert "openBacktestRun" in js
    assert "deleteBacktestRun" in js
    assert "loadStrategyPerformance" in js


def test_backtest_result_has_performance_charts() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")

    assert 'id="backtestEquityChart"' in html
    assert 'id="backtestDrawdownChart"' in html
    assert 'id="backtestDistributionChart"' in html
    assert 'id="backtestMonthlyChart"' in html
    assert "renderBacktestCharts" in js
    assert "equity_curve" in js
    assert "drawdown_curve" in js
    assert "return_distribution" in js
    assert "monthly_returns" in js


def test_backtest_lab_has_research_platform_layout() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    css = (ROOT / "app/static/dashboard/styles.css").read_text(encoding="utf-8")
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")

    assert 'class="backtest-workspace"' in html
    assert 'class="panel backtest-control-panel"' in html
    assert 'class="panel backtest-result-panel"' in html
    assert 'id="topOptimizationPreview"' in html
    assert 'id="strategyScoreSlot"' in html
    assert 'class="chart-panel equity-focus"' in html
    assert "renderKpiCards" in js
    assert "formatReturnR" in js
    assert "resultBadge" in js
    assert "condition-card" in js
    assert ".kpi-grid" in css
    assert ".kpi-card.primary" in css
    assert ".condition-card" in css
    assert ".equity-focus canvas" in css
    assert ".result-badge.win" in css


def test_dashboard_has_professional_research_visual_hierarchy() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    css = (ROOT / "app/static/dashboard/styles.css").read_text(encoding="utf-8")
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")

    assert 'class="brand-mark">AF<' in html
    assert 'class="hero-actions"' in html
    assert 'class="research-pill"' in html
    assert 'class="result-stack"' in html
    assert 'class="section-label">Risk Settings</span>' in html
    assert "featured" in js
    assert "card.caption" in js
    assert ".hero-actions" in css
    assert ".research-pill" in css
    assert ".result-stack" in css
    assert ".kpi-card.featured" in css
    assert ".section-label" in css


def test_backtest_lab_has_exit_optimizer_mode() -> None:
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")

    assert 'data-backtest-mode="single"' in html
    assert 'data-backtest-mode="optimizer"' in html
    assert 'id="exitOptimizerPanel"' in html
    assert 'name="optimizer_atr_from"' in html
    assert 'name="optimizer_rr_from"' in html
    assert 'id="optimizerResultsTable"' in html
    assert 'id="optimizerTopChart"' in html
    assert "optimizeExit" in js
    assert "runExitOptimization" in js
    assert "renderOptimizationResults" in js
    assert "saveOptimizedStrategy" in js


def test_backtest_mode_toggle_has_clear_active_state() -> None:
    css = (ROOT / "app/static/dashboard/styles.css").read_text(encoding="utf-8")

    assert ".backtest-mode-toggle button.active::before" in css
    assert "box-shadow: 0 0 0 1px" in css
    assert "background: linear-gradient(135deg" in css
    assert 'content: "✓"' in css
