const api = {
  dashboard: "/api/v1/dashboard",
  strategies: "/api/v1/strategies",
  conditions: "/api/v1/conditions",
  backtestStrategies: "/api/v1/backtest-strategies",
  backtestStrategyPerformance: "/api/v1/backtest-strategies/performance",
  backtests: "/api/v1/backtests",
  backtestRun: "/api/v1/backtests/run",
  optimizeExit: "/api/v1/backtests/optimize-exit",
  signals: "/api/v1/signals",
  performance: "/api/v1/performance",
  strategy: "/api/v1/strategy-analysis",
  research: "/api/v1/research",
  settings: "/api/v1/settings",
};

const charts = {};
let selectedStrategy = "";
let selectedHolding = "24";
let conditionRegistry = [];
let selectedConditions = [];
let editingConditionIndex = null;
let backtestStrategies = [];
let optimizerResults = [];

document.querySelectorAll(".nav button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav button").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    document.getElementById(button.dataset.view).classList.add("active");
  });
});

document.getElementById("signalFilters").addEventListener("submit", (event) => {
  event.preventDefault();
  loadSignals(new FormData(event.currentTarget));
});

document.getElementById("backtestForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await runBacktest(new FormData(event.currentTarget));
});

document.querySelectorAll("#backtestModeToggle button").forEach((button) => {
  button.addEventListener("click", () => {
    setBacktestMode(button.dataset.backtestMode);
  });
});

document.getElementById("runOptimizationButton").addEventListener("click", async () => {
  await runExitOptimization(new FormData(document.getElementById("backtestForm")));
});

document.querySelectorAll("#holdingButtons button").forEach((button) => {
  button.addEventListener("click", () => {
    selectedHolding = button.dataset.holding;
    document.querySelectorAll("#holdingButtons button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    document.getElementById("customHoldingHours").hidden = selectedHolding !== "custom";
  });
});

document.getElementById("closeModal").addEventListener("click", () => {
  document.getElementById("detailModal").hidden = true;
});

document.getElementById("conditionTypeSelect").addEventListener("change", () => {
  renderConditionParamFields();
});

document.getElementById("addConditionButton").addEventListener("click", () => {
  addOrUpdateCondition();
});

document.getElementById("saveBacktestStrategyButton").addEventListener("click", async () => {
  await saveBacktestStrategy();
});

document.getElementById("deleteBacktestStrategyButton").addEventListener("click", async () => {
  await deleteSelectedBacktestStrategy();
});

document.getElementById("backtestStrategySelect").addEventListener("change", (event) => {
  applyBacktestStrategy(Number(event.currentTarget.value));
});

function pct(value) {
  if (value === null || value === undefined) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function num(value) {
  if (value === null || value === undefined) return "-";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function cls(value) {
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "neutral";
}

function metricTone(value, kind = "directional") {
  if (value === null || value === undefined) return "neutral";
  if (kind === "inverse") return value < 0 ? "negative" : "neutral";
  if (kind === "profitFactor") return value >= 1 ? "positive" : "negative";
  if (kind === "count") return "neutral";
  return cls(value);
}

function formatReturnR(value) {
  if (value === null || value === undefined) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(2)}R`;
}

function tradeResult(trade) {
  if (trade.exit_reason === "TP" || Number(trade.return_pct || 0) > 0) return "WIN";
  if (trade.exit_reason === "SL" || Number(trade.return_pct || 0) < 0) return "LOSS";
  return "TIME_EXIT";
}

function resultBadge(trade) {
  const result = tradeResult(trade);
  const tone = result === "WIN" ? "win" : result === "LOSS" ? "loss" : "time";
  return `<span class="result-badge ${tone}">${result}</span>`;
}

function time(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("ko-KR", { hour12: false });
}

function dateOnly(value) {
  return value.toISOString().slice(0, 10);
}

function setDefaultBacktestDates() {
  const now = new Date();
  const kstNow = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  const endDate = dateOnly(kstNow);
  const start = new Date(kstNow);
  start.setUTCDate(start.getUTCDate() - 90);
  document.querySelector('#backtestForm input[name="end_date"]').value = endDate;
  document.querySelector('#backtestForm input[name="start_date"]').value = dateOnly(start);
}

function kstDateRangeToUtcIso(startDate, endDate) {
  const startUtc = new Date(`${startDate}T00:00:00+09:00`);
  const endUtc = new Date(`${endDate}T23:59:59+09:00`);
  return {
    start_time: startUtc.toISOString(),
    end_time: endUtc.toISOString(),
  };
}

function resolveMaxHoldingHours(formData) {
  if (selectedHolding === "infinite") {
    const { start_time, end_time } = kstDateRangeToUtcIso(
      formData.get("start_date"),
      formData.get("end_date"),
    );
    return Math.max(1, Math.ceil((new Date(end_time) - new Date(start_time)) / 3_600_000));
  }
  if (selectedHolding === "custom") {
    return Number(formData.get("custom_holding_hours"));
  }
  return Number(selectedHolding);
}

function setMaxHoldingHours(hours) {
  const value = String(hours);
  const preset = ["12", "24", "48"].includes(value) ? value : "custom";
  selectedHolding = preset;
  document.querySelectorAll("#holdingButtons button").forEach((button) => {
    button.classList.toggle("active", button.dataset.holding === preset);
  });
  document.getElementById("customHoldingHours").hidden = preset !== "custom";
  document.getElementById("customHoldingHours").value = hours;
}

function setBacktestMode(mode) {
  const isOptimizer = mode === "optimizer";
  document.querySelectorAll("#backtestModeToggle button").forEach((item) => {
    item.classList.toggle("active", item.dataset.backtestMode === mode);
  });
  document.getElementById("exitOptimizerPanel").hidden = !isOptimizer;
  const singleBacktestHidden = isOptimizer;
  document.querySelectorAll("[data-single-backtest]").forEach((item) => {
    item.hidden = singleBacktestHidden;
    item.classList.toggle("single-backtest-hidden", singleBacktestHidden);
  });
}

function resolveBacktestTimeframe(strategyTimeframe = null) {
  const supported = ["1h", "4h", "12h", "1d", "3d", "1w", "1M"];
  const rank = new Map(supported.map((value, index) => [value, index]));
  const conditionTimeframes = selectedConditions
    .map((condition) => condition.params?.timeframe)
    .filter((value) => rank.has(value));
  if (conditionTimeframes.length) {
    return conditionTimeframes.sort((left, right) => rank.get(left) - rank.get(right))[0];
  }
  return rank.has(strategyTimeframe) ? strategyTimeframe : "4h";
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} ${response.status}`);
  return response.json();
}

function withStrategy(url) {
  const target = new URL(url, window.location.origin);
  if (selectedStrategy) target.searchParams.set("strategy_name", selectedStrategy);
  return `${target.pathname}${target.search}`;
}

async function loadStrategies() {
  const strategies = await getJson(api.strategies);
  const buttons = [
    { name: "", label: "All Strategies" },
    ...strategies.map((item) => ({
      name: item.name,
      label: item.name.replace(/_/g, " "),
    })),
  ];
  document.getElementById("strategyButtons").innerHTML = buttons
    .map((item) => `<button class="${item.name === selectedStrategy ? "active" : ""}" data-strategy="${item.name}">${item.label}</button>`)
    .join("");
  document.querySelectorAll("#strategyButtons button").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedStrategy = button.dataset.strategy || "";
      document.querySelectorAll("#strategyButtons button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      document.getElementById("selectedStrategyLabel").textContent = button.textContent;
      await reloadResearchViews();
    });
  });
}

async function loadConditions() {
  conditionRegistry = await getJson(api.conditions);
  document.getElementById("conditionTypeSelect").innerHTML = conditionRegistry
    .map((condition) => `<option value="${condition.id}">${condition.label}</option>`)
    .join("");
  renderConditionParamFields();
  renderSelectedConditions();
}

async function loadBacktestRuns() {
  const rows = await getJson(api.backtests);
  renderSummaryTable(
    "backtestRunsTable",
    ["ID", "Name", "Symbol", "Direction", "Trades", "Win Rate", "Avg Return", "Created", ""],
    rows,
    (row) => [
      row.id,
      row.name || "-",
      row.symbol,
      row.direction,
      row.metrics.total_trades,
      pct(row.metrics.win_rate_pct),
      pct(row.metrics.avg_return_pct),
      time(row.created_at),
      `<button type="button" data-run-delete="${row.id}">Delete</button>`,
    ],
  );
  document.querySelectorAll("#backtestRunsTable tbody tr").forEach((row, index) => {
    row.addEventListener("click", () => openBacktestRun(rows[index].id));
  });
  document.querySelectorAll("[data-run-delete]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      await deleteBacktestRun(Number(button.dataset.runDelete));
    });
  });
}

async function openBacktestRun(runId) {
  const result = await getJson(`${api.backtests}/${runId}`);
  renderBacktestResult(result);
}

async function deleteBacktestRun(runId) {
  const response = await fetch(`${api.backtests}/${runId}`, { method: "DELETE" });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Backtest run delete failed");
  }
  await Promise.all([loadBacktestRuns(), loadStrategyPerformance()]);
}

async function loadStrategyPerformance() {
  const rows = await getJson(api.backtestStrategyPerformance);
  renderSummaryTable(
    "strategyPerformanceTable",
    ["Preset", "Symbol", "Runs", "Trades", "Avg Return", "Win Rate", "Profit Factor", "Worst MDD", "Max Losses"],
    rows,
    (row) => [
      row.name,
      row.symbol,
      row.run_count,
      row.total_trades,
      pct(row.avg_return_pct),
      pct(row.avg_win_rate_pct),
      row.avg_profit_factor === null ? "-" : row.avg_profit_factor.toFixed(2),
      pct(row.worst_mdd_pct),
      row.max_consecutive_losses,
    ],
  );
}

async function loadBacktestStrategies() {
  backtestStrategies = await getJson(api.backtestStrategies);
  document.getElementById("backtestStrategySelect").innerHTML = [
    `<option value="">Saved Strategy Presets</option>`,
    ...backtestStrategies.map((strategy) => `<option value="${strategy.id}">${strategy.name}</option>`),
  ].join("");
}

function currentBacktestStrategyPayload() {
  const form = new FormData(document.getElementById("backtestForm"));
  const name = String(form.get("name") || "").trim();
  if (!name) {
    throw new Error("Strategy name is required before saving.");
  }
  return {
    name,
    symbol: form.get("symbol"),
    direction: form.get("direction"),
    timeframe: resolveBacktestTimeframe(),
    entry_conditions: selectedConditions,
    risk: {
      sl_atr_multiplier: Number(form.get("atr_multiplier")),
      risk_reward_ratio: Number(form.get("risk_reward_ratio")),
      max_holding_hours: resolveMaxHoldingHours(form),
    },
  };
}

async function saveBacktestStrategy() {
  const response = await fetch(api.backtestStrategies, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentBacktestStrategyPayload()),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Strategy save failed");
  }
  const saved = await response.json();
  await loadBacktestStrategies();
  await loadStrategyPerformance();
  document.getElementById("backtestStrategySelect").value = saved.id;
}

function applyBacktestStrategy(strategyId) {
  const strategy = backtestStrategies.find((item) => item.id === strategyId);
  if (!strategy) return;
  const form = document.getElementById("backtestForm");
  form.elements.name.value = strategy.name;
  form.elements.symbol.value = strategy.symbol;
  form.elements.direction.value = strategy.direction;
  form.elements.atr_multiplier.value = strategy.risk.sl_atr_multiplier;
  form.elements.risk_reward_ratio.value = strategy.risk.risk_reward_ratio;
  setMaxHoldingHours(strategy.risk.max_holding_hours);
  selectedConditions = JSON.parse(JSON.stringify(strategy.conditions));
  editingConditionIndex = null;
  document.getElementById("addConditionButton").textContent = "Add Condition";
  renderSelectedConditions();
}

async function deleteSelectedBacktestStrategy() {
  const strategyId = Number(document.getElementById("backtestStrategySelect").value);
  if (!strategyId) return;
  const response = await fetch(`${api.backtestStrategies}/${strategyId}`, { method: "DELETE" });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Strategy delete failed");
  }
  await loadBacktestStrategies();
  await loadStrategyPerformance();
}

function renderConditionParamFields(condition = null) {
  const definition = conditionRegistry.find((item) => item.id === (condition?.type || document.getElementById("conditionTypeSelect").value));
  if (!definition) return;
  const values = condition?.params || {};
  document.getElementById("conditionTypeSelect").value = definition.id;
  if (definition.id === "ma_ordering") {
    renderMaOrderingBuilder(values);
    return;
  }
  document.getElementById("conditionParamFields").innerHTML = Object.entries(definition.params_schema)
    .map(([key, schema]) => {
      const value = values[key] ?? schema.default ?? "";
      if (schema.type === "select") {
        return `
          <label>${key}
            <select name="${key}">
              ${schema.options.map((option) => `<option value="${option}" ${option === value ? "selected" : ""}>${option}</option>`).join("")}
            </select>
          </label>
        `;
      }
      return `
        <label>${key}
          <input name="${key}" type="number" value="${value}" min="${schema.min ?? ""}" max="${schema.max ?? ""}" step="${schema.step ?? "any"}" />
        </label>
      `;
    })
    .join("");
}

function renderMaOrderingBuilder(values = {}) {
  const timeframe = values.timeframe || "4h";
  const items = values.items || [
    { source: "ma", ma_type: "sma", period: 21 },
    { source: "ma", ma_type: "sma", period: 60 },
  ];
  document.getElementById("conditionParamFields").innerHTML = `
    <div class="ma-expression-builder">
      <label>Timeframe
        <select name="timeframe">
          ${["1h", "4h", "12h", "1d", "3d", "1w", "1M"].map((option) => `<option value="${option}" ${option === timeframe ? "selected" : ""}>${option.toUpperCase()}</option>`).join("")}
        </select>
      </label>
      <div class="expression-preview">
        <span>Preview</span>
        <strong id="maExpressionPreview">${maOrderingPreview(items)}</strong>
      </div>
      <div class="ma-expression-items" id="maExpressionItems">
        ${items.map((item, index) => maOrderingItemHtml(item, index, items.length)).join("")}
      </div>
      <button type="button" id="addMaOrderingItem">+ Add Item</button>
    </div>
  `;
  attachMaOrderingHandlers();
}

function maOrderingItemHtml(item, index, itemCount) {
  const source = item.source === "price" ? "price" : "ma";
  const maType = item.ma_type || "sma";
  const period = Number(item.period || 21);
  const presetPeriods = [7, 21, 60, 120, 200, 224, 365];
  const isCustom = source === "ma" && !presetPeriods.includes(period);
  return `
    <div class="ma-expression-row" data-expression-index="${index}">
      ${index > 0 ? '<span class="expression-operator">&gt;</span>' : '<span></span>'}
      <select name="expression_source_${index}">
        <option value="price" ${source === "price" ? "selected" : ""}>Price</option>
        <option value="sma" ${source === "ma" && maType === "sma" ? "selected" : ""}>SMA</option>
        <option value="ema" ${source === "ma" && maType === "ema" ? "selected" : ""}>EMA</option>
      </select>
      <select name="expression_period_${index}" ${source === "price" ? "hidden" : ""}>
        ${presetPeriods.map((option) => `<option value="${option}" ${period === option ? "selected" : ""}>${option}</option>`).join("")}
        <option value="custom" ${isCustom ? "selected" : ""}>Custom</option>
      </select>
      <input name="expression_custom_period_${index}" type="number" min="1" step="1" value="${period}" ${isCustom ? "" : "hidden"} />
      <div class="expression-actions">
        <button type="button" data-expression-action="up" ${index === 0 ? "disabled" : ""}>Up</button>
        <button type="button" data-expression-action="down" ${index === itemCount - 1 ? "disabled" : ""}>Down</button>
        <button type="button" data-expression-action="remove" ${itemCount <= 2 ? "disabled" : ""}>Remove</button>
      </div>
    </div>
  `;
}

function attachMaOrderingHandlers() {
  document.querySelectorAll("#conditionParamFields select, #conditionParamFields input").forEach((field) => {
    field.addEventListener("change", () => {
      renderMaOrderingBuilder(readMaOrderingParams());
    });
  });
  document.querySelectorAll("[data-expression-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const row = button.closest("[data-expression-index]");
      moveMaOrderingItem(Number(row.dataset.expressionIndex), button.dataset.expressionAction);
    });
  });
  document.getElementById("addMaOrderingItem").addEventListener("click", () => addMaOrderingItem());
}

function readMaOrderingParams() {
  const container = document.getElementById("conditionParamFields");
  const items = [...container.querySelectorAll("[data-expression-index]")].map((row) => {
    const index = row.dataset.expressionIndex;
    const sourceValue = row.querySelector(`[name="expression_source_${index}"]`).value;
    if (sourceValue === "price") return { source: "price" };
    const periodValue = row.querySelector(`[name="expression_period_${index}"]`).value;
    const period = periodValue === "custom"
      ? Number(row.querySelector(`[name="expression_custom_period_${index}"]`).value)
      : Number(periodValue);
    return { source: "ma", ma_type: sourceValue, period };
  });
  return {
    timeframe: container.querySelector('[name="timeframe"]').value,
    items,
  };
}

function addMaOrderingItem() {
  const params = readMaOrderingParams();
  params.items.push({ source: "ma", ma_type: "sma", period: 60 });
  renderMaOrderingBuilder(params);
}

function moveMaOrderingItem(index, action) {
  const params = readMaOrderingParams();
  if (action === "remove") {
    params.items.splice(index, 1);
  }
  if (action === "up" && index > 0) {
    [params.items[index - 1], params.items[index]] = [params.items[index], params.items[index - 1]];
  }
  if (action === "down" && index < params.items.length - 1) {
    [params.items[index + 1], params.items[index]] = [params.items[index], params.items[index + 1]];
  }
  renderMaOrderingBuilder(params);
}

function maOrderingPreview(items) {
  return (items || []).map(maOrderingItemLabel).join(" > ") || "Price > SMA21 > SMA60";
}

function maOrderingItemLabel(item) {
  if (item.source === "price") return "Price";
  return `${String(item.ma_type || "sma").toUpperCase()}${item.period || 21}`;
}

function addOrUpdateCondition() {
  const type = document.getElementById("conditionTypeSelect").value;
  const definition = conditionRegistry.find((item) => item.id === type);
  if (!definition) return;
  const params = type === "ma_ordering" ? readMaOrderingParams() : {};
  if (type !== "ma_ordering") {
    for (const [key, schema] of Object.entries(definition.params_schema)) {
      const value = document.querySelector(`#conditionParamFields [name="${key}"]`).value;
      params[key] = schema.type === "number" ? Number(value) : value;
    }
  }
  const condition = { type, params };
  if (editingConditionIndex === null) {
    selectedConditions.push(condition);
  } else {
    selectedConditions[editingConditionIndex] = condition;
    editingConditionIndex = null;
    document.getElementById("addConditionButton").textContent = "Add Condition";
  }
  renderSelectedConditions();
}

function renderSelectedConditions() {
  const target = document.getElementById("selectedConditionList");
  if (!selectedConditions.length) {
    target.innerHTML = `<div class="empty-conditions">No entry conditions selected. The backtest will enter on every candle.</div>`;
    return;
  }
  target.innerHTML = selectedConditions
    .map((condition, index) => {
      const definition = conditionRegistry.find((item) => item.id === condition.type);
      const details = conditionDetails(condition);
      return `
        <article class="selected-condition condition-card">
          <div>
            <strong>${definition?.label || condition.type}</strong>
            <div class="condition-detail-grid">
              ${details.map(([label, value]) => `<span><b>${label}</b>${value}</span>`).join("")}
            </div>
          </div>
          <div class="condition-actions">
            <button type="button" data-action="edit" data-index="${index}">Edit</button>
            <button type="button" data-action="duplicate" data-index="${index}">Duplicate</button>
            <button type="button" data-action="delete" data-index="${index}">Delete</button>
          </div>
        </article>
      `;
    })
    .join("");
  target.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.index);
      if (button.dataset.action === "edit") editCondition(index);
      if (button.dataset.action === "duplicate") duplicateCondition(index);
      if (button.dataset.action === "delete") deleteCondition(index);
    });
  });
}

function conditionDetails(condition) {
  const params = condition.params || {};
  if (condition.type === "ma_alignment") {
    return [
      ["Direction", titleCase(params.direction)],
      ["TF", String(params.timeframe || "-").toUpperCase()],
      ["MA", `${String(params.ma_type || "sma").toUpperCase()} ${params.fast} / ${params.mid} / ${params.slow}`],
    ];
  }
  if (condition.type === "ma_touch") {
    return [
      ["TF", String(params.timeframe || "-").toUpperCase()],
      ["MA", `${String(params.ma_type || "sma").toUpperCase()} ${params.period}`],
      ["Tolerance", `${(Number(params.tolerance_pct || 0) * 100).toFixed(2)}%`],
    ];
  }
  if (condition.type === "ma_ordering") {
    return [
      ["TF", String(params.timeframe || "-").toUpperCase()],
      ["Expression", maOrderingPreview(params.items)],
    ];
  }
  return Object.entries(params).map(([key, value]) => [key, value]);
}

function titleCase(value) {
  if (!value) return "-";
  const text = String(value);
  return `${text.slice(0, 1).toUpperCase()}${text.slice(1).toLowerCase()}`;
}
function editCondition(index) {
  editingConditionIndex = index;
  renderConditionParamFields(selectedConditions[index]);
  document.getElementById("addConditionButton").textContent = "Update Condition";
}

function duplicateCondition(index) {
  selectedConditions.splice(index + 1, 0, JSON.parse(JSON.stringify(selectedConditions[index])));
  renderSelectedConditions();
}

function deleteCondition(index) {
  selectedConditions.splice(index, 1);
  if (editingConditionIndex === index) {
    editingConditionIndex = null;
    document.getElementById("addConditionButton").textContent = "Add Condition";
  }
  renderSelectedConditions();
}

async function reloadResearchViews() {
  await Promise.all([
    loadDashboard(),
    loadSignals(new FormData(document.getElementById("signalFilters"))),
    loadPerformance(),
    loadStrategy(),
    loadResearch(),
  ]);
}

async function loadDashboard() {
  const data = await getJson(withStrategy(api.dashboard));
  const cards = [
    ["총 신호", data.counts.total_signals],
    ["LONG", data.counts.long_signals],
    ["SHORT", data.counts.short_signals],
    ["최근 7일", data.counts.signals_7d],
    ["최근 30일", data.counts.signals_30d],
  ];
  document.getElementById("summaryCards").innerHTML = cards
    .map(([label, value]) => `<article class="metric"><span>${label}</span><strong>${value}</strong></article>`)
    .join("");

  document.getElementById("horizonCards").innerHTML = Object.entries(data.horizons)
    .map(([horizon, item]) => `
      <article class="horizon-card">
        <span>${horizon}</span>
        <strong class="${cls(item.avg_return_pct)}">${pct(item.avg_return_pct)}</strong>
        <span>Win ${pct(item.win_rate_pct)} · MFE ${pct(item.avg_mfe_pct)} · MAE ${pct(item.avg_mae_pct)}</span>
      </article>
    `)
    .join("");

  drawLine("dailySignalsChart", data.charts.daily_signal_counts, "date", "count", "Daily Signals", "#60a5fa");
  drawLine("cumulativeSignalsChart", data.charts.cumulative_signal_counts, "date", "count", "Cumulative", "#24d17e");
  drawBar(
    "symbolReturnsChart",
    data.charts.symbol_avg_returns,
    "symbol",
    "avg_return_pct",
    "24h Avg Return",
    "#f4c95d",
  );
}

async function loadSignals(formData = null) {
  const params = new URLSearchParams({ limit: "200" });
  if (selectedStrategy) params.set("strategy_name", selectedStrategy);
  if (formData) {
    for (const [key, value] of formData.entries()) {
      if (!value) continue;
      params.set(key, key === "start" || key === "end" ? new Date(value).toISOString() : value);
    }
  }
  const rows = await getJson(`${api.signals}?${params}`);
  document.getElementById("signalsTable").innerHTML = rows
    .map((row) => {
      const signal = row.signal;
      const h24 = row.outcomes["24h"]?.return_pct;
      const h72 = row.outcomes["72h"]?.return_pct;
      return `
        <tr data-id="${signal.id}">
          <td>${signal.id}</td>
          <td>${signal.symbol}</td>
          <td><span class="badge ${signal.direction === "LONG" ? "long" : "short"}">${signal.direction || "-"}</span></td>
          <td>${signal.analysis_signal_type || signal.signal_type}</td>
          <td>${time(signal.occurred_at)}</td>
          <td>${num(signal.entry_price)}</td>
          <td class="${cls(h24)}">${pct(h24)}</td>
          <td class="${cls(h72)}">${pct(h72)}</td>
        </tr>
      `;
    })
    .join("");
  document.querySelectorAll("#signalsTable tr").forEach((row) => {
    row.addEventListener("click", () => openDetail(row.dataset.id));
  });
}

async function openDetail(id) {
  const row = await getJson(`${api.signals}/${id}`);
  const signal = row.signal;
  document.getElementById("detailContent").innerHTML = `
    <p class="eyebrow">Signal Detail</p>
    <h2>#${signal.id} ${signal.symbol}</h2>
    <div class="horizon-grid">
      <div class="horizon-card"><span>Direction</span><strong>${signal.direction || "-"}</strong></div>
      <div class="horizon-card"><span>Entry</span><strong>${num(signal.entry_price)}</strong></div>
      <div class="horizon-card"><span>Signal Time</span><strong>${time(signal.occurred_at)}</strong></div>
      <div class="horizon-card"><span>Type</span><strong>${signal.analysis_signal_type || signal.signal_type}</strong></div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Horizon</th><th>Return</th><th>MFE</th><th>MAE</th><th>Price After</th></tr></thead>
        <tbody>
          ${["12h", "24h", "48h", "72h"].map((key) => {
            const item = row.outcomes[key];
            return `<tr><td>${key}</td><td class="${cls(item?.return_pct)}">${pct(item?.return_pct)}</td><td>${pct(item?.max_favorable_return_pct)}</td><td>${pct(item?.max_adverse_return_pct)}</td><td>${num(item?.price_after)}</td></tr>`;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
  document.getElementById("detailModal").hidden = false;
}

async function loadPerformance() {
  const data = await getJson(withStrategy(api.performance));
  renderSummaryTable("performanceTable", ["Symbol", "Signals", "Avg Return", "Win Rate", "MFE", "MAE"], data.symbols, (item) => [
    item.symbol,
    item.signal_count,
    pct(item.avg_return_pct),
    pct(item.win_rate_pct),
    pct(item.avg_mfe_pct),
    pct(item.avg_mae_pct),
  ]);
}

async function loadStrategy() {
  const data = await getJson(withStrategy(api.strategy));
  document.getElementById("bestSignalType").textContent = data.best_signal_type
    ? `Best: ${data.best_signal_type.signal_type} ${pct(data.best_signal_type.avg_return_pct)}`
    : "성과 기록 대기 중";
  renderSummaryTable("strategyTable", ["Signal Type", "Signals", "Avg Return", "Win Rate", "MFE", "MAE"], data.signal_types, (item) => [
    item.signal_type,
    item.signal_count,
    pct(item.avg_return_pct),
    pct(item.win_rate_pct),
    pct(item.avg_mfe_pct),
    pct(item.avg_mae_pct),
  ]);
  drawBar("strategyReturnsChart", data.signal_types, "signal_type", "avg_return_pct", "24h Avg Return", "#60a5fa");
}

async function loadResearch() {
  const data = await getJson(withStrategy(api.research));
  const headers = ["ID", "Symbol", "Direction", "Type", "Return", "MFE", "MAE"];
  const mapper = (item) => [
    item.signal_id,
    item.symbol,
    item.direction,
    item.signal_type,
    pct(item.return_pct),
    pct(item.mfe_pct),
    pct(item.mae_pct),
  ];
  renderSummaryTable("winnersTable", headers, data.top_winners, mapper);
  renderSummaryTable("losersTable", headers, data.top_losers, mapper);
}

async function loadSettings() {
  const data = await getJson(api.settings);
  document.getElementById("settingsPanel").innerHTML = `
    <article class="settings-card"><span>Tracked Symbols</span><p>${data.tracked_symbols.join(", ")}</p></article>
    <article class="settings-card"><span>Discord</span><p>${data.discord.enabled ? "Enabled" : "Disabled"} · ${data.discord.configured ? "Configured" : "Not configured"}</p></article>
    <article class="settings-card"><span>Outcome Tracking</span><p>${data.outcome_tracking.enabled ? "Enabled" : "Disabled"} · ${data.outcome_tracking.horizons.join("h / ")}h</p></article>
  `;
}

async function runBacktest(formData) {
  const dateRange = kstDateRangeToUtcIso(formData.get("start_date"), formData.get("end_date"));
  const payload = {
    name: formData.get("name") || null,
    symbol: formData.get("symbol"),
    direction: formData.get("direction"),
    timeframe: resolveBacktestTimeframe(),
    start_time: dateRange.start_time,
    end_time: dateRange.end_time,
    entry_conditions: selectedConditions,
    atr_multiplier: Number(formData.get("atr_multiplier")),
    risk_reward_ratio: Number(formData.get("risk_reward_ratio")),
    max_holding_hours: resolveMaxHoldingHours(formData),
  };
  const response = await fetch(api.backtestRun, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Backtest failed");
  }
  renderBacktestResult(await response.json());
  await Promise.all([loadBacktestRuns(), loadStrategyPerformance()]);
}

async function runExitOptimization(formData) {
  formData = withOptimizerFormData(formData);
  const estimate = estimateOptimizerCombinations();
  document.getElementById("optimizerCombinationWarning").textContent =
    estimate > 2000 ? `${estimate.toLocaleString()} combinations. This can take a little while.` : `${estimate.toLocaleString()} combinations`;
  const dateRange = kstDateRangeToUtcIso(formData.get("start_date"), formData.get("end_date"));
  const payload = {
    symbol: formData.get("symbol"),
    direction: formData.get("direction"),
    timeframe: resolveBacktestTimeframe(),
    start_time: dateRange.start_time,
    end_time: dateRange.end_time,
    entry_conditions: selectedConditions,
    risk_optimization: {
      atr_period: 14,
      atr_multiplier: {
        from: Number(formData.get("optimizer_atr_from")),
        to: Number(formData.get("optimizer_atr_to")),
        step: Number(formData.get("optimizer_atr_step")),
      },
      risk_reward_ratio: {
        from: Number(formData.get("optimizer_rr_from")),
        to: Number(formData.get("optimizer_rr_to")),
        step: Number(formData.get("optimizer_rr_step")),
      },
      max_holding: resolveMaxHoldingHours(formData),
    },
    filters: {
      min_trades: Number(formData.get("optimizer_min_trades") || 0),
      min_profit_factor: nullableNumber(formData.get("optimizer_min_pf")),
      max_mdd: nullableNumber(formData.get("optimizer_max_mdd")),
    },
    sort_by: formData.get("optimizer_sort_by"),
  };
  const response = await fetch(api.optimizeExit, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Exit optimization failed");
  }
  renderOptimizationResults(await response.json());
}

function estimateOptimizerCombinations() {
  const formData = withOptimizerFormData(new FormData(document.getElementById("backtestForm")));
  const atrCount = rangeCount(
    Number(formData.get("optimizer_atr_from")),
    Number(formData.get("optimizer_atr_to")),
    Number(formData.get("optimizer_atr_step")),
  );
  const rrCount = rangeCount(
    Number(formData.get("optimizer_rr_from")),
    Number(formData.get("optimizer_rr_to")),
    Number(formData.get("optimizer_rr_step")),
  );
  return atrCount * rrCount;
}

function withOptimizerFormData(formData) {
  document.querySelectorAll("#exitOptimizerPanel [name]").forEach((field) => {
    formData.set(field.name, field.value);
  });
  return formData;
}

function rangeCount(from, to, step) {
  if (!Number.isFinite(from) || !Number.isFinite(to) || !Number.isFinite(step) || step <= 0 || to < from) return 0;
  return Math.floor((to - from) / step + 1.000001);
}

function nullableNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  return Number(value);
}

function renderOptimizationResults(result) {
  optimizerResults = result.results || [];
  document.getElementById("optimizerResultPanel").hidden = false;
  const summary = result.summary || {};
  const best = summary.best_by_expectancy;
  document.getElementById("optimizerResultMeta").textContent = best
    ? `Best ATR ${best.atr_multiplier} / R:R ${best.risk_reward_ratio} / ${num(best.expectancy_r)}R`
    : "No combinations passed filters";
  const cards = [
    ["Combinations", summary.total_combinations || 0],
    ["Passed Filters", summary.filtered_combinations || 0],
    ["Entry Candidates", summary.entry_candidate_count || 0],
    ["Best ATR", best ? best.atr_multiplier : "-"],
    ["Best R:R", best ? best.risk_reward_ratio : "-"],
  ];
  document.getElementById("optimizerSummaryCards").innerHTML = cards
    .map(([label, value]) => `<article class="metric"><span>${label}</span><strong>${value}</strong></article>`)
    .join("");

  const topRows = optimizerResults.slice(0, 10).map((row) => ({
    label: `${row.atr_multiplier}/${row.risk_reward_ratio}`,
    expectancy_r: row.expectancy_r,
  }));
  drawBar("optimizerTopChart", topRows, "label", "expectancy_r", "Expectancy(R)", "#24d17e");

  renderSummaryTable(
    "optimizerResultsTable",
    ["Rank", "ATR", "R:R", "Trades", "Win Rate", "Expectancy(R)", "PF", "MDD", "Max Losses", "Avg MFE", "Avg MAE", "Total Return", ""],
    optimizerResults,
    (row, index) => [
      row.rank,
      row.atr_multiplier,
      row.risk_reward_ratio,
      `${row.total_trades}${row.total_trades < 30 ? '<span class="sample-warning">Low sample</span>' : ""}`,
      pct(row.win_rate),
      `${num(row.expectancy_r)}R`,
      row.profit_factor === null ? "-" : row.profit_factor.toFixed(2),
      pct(row.mdd),
      row.max_loss_streak,
      pct(row.avg_mfe),
      pct(row.avg_mae),
      pct(row.total_return),
      `<button type="button" data-optimizer-save="${index}">Save as Strategy</button>`,
    ],
  );
  document.querySelectorAll("[data-optimizer-save]").forEach((button) => {
    button.addEventListener("click", async () => {
      await saveOptimizedStrategy(Number(button.dataset.optimizerSave));
    });
  });
  renderTopOptimizationPreview(optimizerResults);
}

function renderTopOptimizationPreview(rows) {
  const target = document.getElementById("topOptimizationList");
  if (!target) return;
  const topRows = rows.slice(0, 5);
  if (!topRows.length) {
    target.innerHTML = `<article class="top-result-empty">No optimization results passed the filters.</article>`;
    return;
  }
  target.innerHTML = topRows
    .map((row, index) => `
      <article class="top-result-card">
        <div>
          <span>#${index + 1} ATR ${row.atr_multiplier} / R:R ${row.risk_reward_ratio}</span>
          <strong class="${cls(row.expectancy_r)}">${formatReturnR(row.expectancy_r)}</strong>
        </div>
        <p>PF ${row.profit_factor === null ? "-" : row.profit_factor.toFixed(2)} · Trades ${row.total_trades} · MDD ${pct(row.mdd)}</p>
        <button type="button" data-optimizer-save="${index}">Save Strategy</button>
      </article>
    `)
    .join("");
  target.querySelectorAll("[data-optimizer-save]").forEach((button) => {
    button.addEventListener("click", async () => {
      await saveOptimizedStrategy(Number(button.dataset.optimizerSave));
    });
  });
}

async function saveOptimizedStrategy(index) {
  const row = optimizerResults[index];
  if (!row) return;
  const form = new FormData(document.getElementById("backtestForm"));
  const defaultName = `Optimized ATR ${row.atr_multiplier} RR ${row.risk_reward_ratio}`;
  const name = window.prompt("Strategy name", String(form.get("name") || defaultName).trim() || defaultName);
  if (!name) return;
  const response = await fetch(api.backtestStrategies, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      symbol: form.get("symbol"),
      direction: form.get("direction"),
      timeframe: resolveBacktestTimeframe(),
      entry_conditions: selectedConditions,
      risk: {
        sl_atr_multiplier: row.atr_multiplier,
        risk_reward_ratio: row.risk_reward_ratio,
        max_holding_hours: resolveMaxHoldingHours(form),
      },
      optimization_result: row,
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Optimized strategy save failed");
  }
  const saved = await response.json();
  await loadBacktestStrategies();
  await loadStrategyPerformance();
  document.getElementById("backtestStrategySelect").value = saved.id;
}

function renderBacktestResult(result) {
  document.getElementById("backtestResultPanel").hidden = false;
  document.getElementById("backtestResultMeta").textContent = `${result.symbol} · ${result.direction} · ${result.timeframe}`;
  const metrics = result.metrics;
  renderKpiCards(metrics);
  renderBacktestCharts(result.charts || buildBacktestCharts(result.trades || []));
  document.getElementById("backtestTradesTable").innerHTML = result.trades
    .slice(0, 200)
    .map((trade) => `
      <tr class="trade-row ${tradeResult(trade).toLowerCase()}">
        <td>${time(trade.entry_time)}</td>
        <td>${time(trade.exit_time)}</td>
        <td>${num(trade.entry_price)}</td>
        <td>${num(trade.exit_price)}</td>
        <td>${resultBadge(trade)}</td>
        <td class="${cls(trade.return_r)}">${formatReturnR(trade.return_r)}</td>
        <td class="${cls(trade.return_pct)}">${pct(trade.return_pct)}</td>
        <td>${pct(trade.mfe_pct)}</td>
        <td>${pct(trade.mae_pct)}</td>
      </tr>
    `)
    .join("");
}

function renderKpiCards(metrics) {
  const cards = [
    { label: "Trades", value: metrics.total_trades, tone: "count", primary: true, caption: "Closed trades" },
    { label: "Win Rate", value: pct(metrics.win_rate_pct), toneValue: metrics.win_rate_pct, primary: true, caption: "Positive outcomes" },
    { label: "Expectancy(R)", value: formatReturnR(metrics.expectancy_r), toneValue: metrics.expectancy_r, primary: true, featured: true, caption: "Average R per trade" },
    {
      label: "Profit Factor",
      value: metrics.profit_factor === null ? "-" : metrics.profit_factor.toFixed(2),
      toneValue: metrics.profit_factor,
      tone: "profitFactor",
      primary: true,
      caption: "Gross profit / loss",
    },
    { label: "MDD", value: pct(metrics.mdd_pct), toneValue: metrics.mdd_pct, tone: "inverse", primary: true, caption: "Worst drawdown" },
    { label: "Max Loss Streak", value: metrics.max_consecutive_losses, tone: "count", caption: "Consecutive losses" },
    { label: "Avg MFE", value: pct(metrics.avg_mfe_pct), toneValue: metrics.avg_mfe_pct, caption: "Favorable excursion" },
    { label: "Avg MAE", value: pct(metrics.avg_mae_pct), toneValue: metrics.avg_mae_pct, tone: "inverse", caption: "Adverse excursion" },
    { label: "Avg Return", value: pct(metrics.avg_return_pct), toneValue: metrics.avg_return_pct, caption: "Secondary metric" },
  ];
  document.getElementById("backtestMetrics").innerHTML = cards
    .map((card) => `
      <article class="kpi-card ${card.primary ? "primary" : "secondary"} ${card.featured ? "featured" : ""} ${metricTone(card.toneValue, card.tone)}">
        <span>${card.label}</span>
        <strong>${card.value}</strong>
        <small>${card.caption}</small>
      </article>
    `)
    .join("");
}

function buildBacktestCharts(trades) {
  let equity = 0;
  let peak = 0;
  const monthly = {};
  const equity_curve = [];
  const drawdown_curve = [];
  trades.forEach((trade, index) => {
    const returnPct = Number(trade.return_pct || 0);
    equity += returnPct;
    peak = Math.max(peak, equity);
    const month = String(trade.exit_time || "unknown").slice(0, 7);
    monthly[month] = (monthly[month] || 0) + returnPct;
    equity_curve.push({ trade: index + 1, exit_time: trade.exit_time, equity_pct: equity });
    drawdown_curve.push({ trade: index + 1, exit_time: trade.exit_time, drawdown_pct: equity - peak });
  });
  const buckets = [
    ["< -3%", (value) => value < -3],
    ["-3% to -1%", (value) => value >= -3 && value < -1],
    ["-1% to 0%", (value) => value >= -1 && value < 0],
    ["0% to 1%", (value) => value >= 0 && value < 1],
    ["1% to 3%", (value) => value >= 1 && value < 3],
    ["> 3%", (value) => value >= 3],
  ];
  const returns = trades.map((trade) => Number(trade.return_pct || 0));
  return {
    equity_curve,
    drawdown_curve,
    return_distribution: buckets.map(([bucket, predicate]) => ({
      bucket,
      count: returns.filter(predicate).length,
    })),
    monthly_returns: Object.entries(monthly)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([month, return_pct]) => ({ month, return_pct })),
  };
}

function renderBacktestCharts(chartsData) {
  drawLine("backtestEquityChart", chartsData.equity_curve, "trade", "equity_pct", "Equity %", "#24d17e");
  drawLine("backtestDrawdownChart", chartsData.drawdown_curve, "trade", "drawdown_pct", "Drawdown %", "#ff5d6c");
  drawBar("backtestDistributionChart", chartsData.return_distribution, "bucket", "count", "Trades", "#60a5fa");
  drawBar("backtestMonthlyChart", chartsData.monthly_returns, "month", "return_pct", "Monthly Return %", "#f4c95d");
}

function renderSummaryTable(id, headers, rows, mapper) {
  document.getElementById(id).innerHTML = `
    <thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((row, index) => `<tr>${mapper(row, index).map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody>
  `;
}

function drawLine(id, rows, labelKey, valueKey, label, color) {
  drawChart(id, "line", rows, labelKey, valueKey, label, color);
}

function drawBar(id, rows, labelKey, valueKey, label, color) {
  drawChart(id, "bar", rows, labelKey, valueKey, label, color);
}

function drawChart(id, type, rows, labelKey, valueKey, label, color) {
  const context = document.getElementById(id);
  if (!context) return;
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(context, {
    type,
    data: {
      labels: rows.map((row) => row[labelKey]),
      datasets: [{
        label,
        data: rows.map((row) => row[valueKey] ?? 0),
        borderColor: color,
        backgroundColor: `${color}55`,
        tension: 0.35,
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#8b97a8" } } },
      scales: {
        x: { ticks: { color: "#8b97a8" }, grid: { color: "#1f2b3a" } },
        y: { ticks: { color: "#8b97a8" }, grid: { color: "#1f2b3a" } },
      },
    },
  });
}

async function boot() {
  setDefaultBacktestDates();
  await loadStrategies();
  await loadConditions();
  await loadBacktestStrategies();
  await Promise.all([
    loadDashboard(),
    loadSignals(),
    loadPerformance(),
    loadStrategy(),
    loadResearch(),
    loadSettings(),
    loadBacktestRuns(),
    loadStrategyPerformance(),
  ]);
}

boot().catch((error) => {
  console.error(error);
  document.querySelector(".shell").insertAdjacentHTML(
    "afterbegin",
    `<section class="panel"><h2>Dashboard load failed</h2><p>${error.message}</p></section>`,
  );
});

