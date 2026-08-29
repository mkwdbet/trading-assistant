const api = {
  dashboard: "/api/v1/dashboard",
  settings: "/api/v1/settings",
  edgeRules: "/api/v1/edge-rules",
  evaluate: "/api/v1/edge-rules/evaluate",
  signals: "/api/v1/signals?limit=100",
};

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("edgeRuleForm").addEventListener("submit", saveRule);
  document.getElementById("evaluateNowButton").addEventListener("click", evaluateNow);
  refreshAll();
});

async function refreshAll() {
  const [dashboard, settings, rules, signals] = await Promise.all([
    getJson(api.dashboard),
    getJson(api.settings),
    getJson(api.edgeRules),
    getJson(api.signals),
  ]);

  renderSummary(dashboard, settings);
  renderRules(rules);
  renderSignals(signals);
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} failed: ${response.status}`);
  return response.json();
}

function renderSummary(dashboard, settings) {
  document.getElementById("activeRules").textContent = dashboard.counts.active_rules;
  document.getElementById("totalSignals").textContent = dashboard.counts.total_signals;
  document.getElementById("signals30d").textContent = dashboard.counts.signals_30d;
  document.getElementById("evaluatorStatus").textContent = settings.edge_rule_evaluator.enabled
    ? `${Math.round(settings.edge_rule_evaluator.interval_seconds / 60)}m`
    : "off";
  document.getElementById("discordStatus").textContent = settings.discord.configured
    ? settings.discord.enabled
      ? "enabled"
      : "configured"
    : "not configured";
  document.getElementById("productMode").textContent = settings.product.mode.replaceAll("_", " ");
  document.getElementById("checkInterval").textContent = settings.edge_rule_evaluator.enabled
    ? `${Math.round(settings.edge_rule_evaluator.interval_seconds / 60)} minutes`
    : "off";
}

function renderRules(rules) {
  renderTable(
    "rulesTable",
    ["Name", "Symbol", "TF", "Rule", "Tolerance", "Cooldown", ""],
    rules,
    (rule) => [
      rule.name,
      rule.symbol,
      rule.timeframe.toUpperCase(),
      `${rule.ma_type.toUpperCase()}${rule.ma_period} touch`,
      `${formatPercent(rule.tolerance_pct)}%`,
      `${rule.cooldown_hours}h`,
      `<button class="danger" data-delete-rule="${rule.id}">Delete</button>`,
    ],
    "저장된 장기 조건이 없습니다."
  );

  document.querySelectorAll("[data-delete-rule]").forEach((button) => {
    button.addEventListener("click", async () => {
      await fetch(`${api.edgeRules}/${button.dataset.deleteRule}`, { method: "DELETE" });
      refreshAll();
    });
  });
}

function renderSignals(rows) {
  renderTable(
    "signalsTable",
    ["Time", "Symbol", "TF", "Signal", "Situation", "Price"],
    rows,
    (row) => {
      const signal = row.signal;
      return [
        formatDate(signal.occurred_at),
        signal.symbol,
        signal.timeframe.toUpperCase(),
        signal.signal_type,
        signal.situation || "-",
        formatNumber(signal.current_price || signal.entry_price),
      ];
    },
    "아직 발생한 알림이 없습니다."
  );
}

async function saveRule(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  const payload = {
    name: text(formData, "name"),
    symbol: text(formData, "symbol"),
    timeframe: text(formData, "timeframe"),
    direction: text(formData, "direction"),
    ma_type: "sma",
    ma_period: Number(formData.get("ma_period")),
    tolerance_pct: Number(formData.get("tolerance_pct")) / 100,
    cooldown_hours: Number(formData.get("cooldown_hours")),
    thesis: text(formData, "thesis"),
    judgment: text(formData, "judgment"),
    enabled: true,
  };

  const response = await fetch(api.edgeRules, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const saveStatus = document.getElementById("saveStatus");
  if (!response.ok) {
    const error = await response.json();
    saveStatus.textContent = error.detail || "저장 실패";
    return;
  }
  saveStatus.textContent = "저장 완료";
  await refreshAll();
}

async function evaluateNow() {
  const target = document.getElementById("evaluationResult");
  target.textContent = "평가 중...";
  const response = await fetch(api.evaluate, { method: "POST" });
  const result = await response.json();
  target.textContent = `평가 ${result.rules_evaluated}, 매칭 ${result.rules_matched}, 알림 ${result.signals_created}`;
  await refreshAll();
}

function renderTable(id, headers, rows, mapper, emptyText) {
  const table = document.getElementById(id);
  if (!rows.length) {
    table.innerHTML = `<tbody><tr><td class="empty-row" colspan="${headers.length}">${emptyText}</td></tr></tbody>`;
    return;
  }
  const head = `<thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead>`;
  const body = rows
    .map((row) => `<tr>${mapper(row).map((value) => `<td>${value ?? "-"}</td>`).join("")}</tr>`)
    .join("");
  table.innerHTML = `${head}<tbody>${body}</tbody>`;
}

function text(formData, key) {
  return String(formData.get(key) || "").trim();
}

function formatPercent(value) {
  return (Number(value || 0) * 100).toFixed(2).replace(/\.?0+$/, "");
}

function formatNumber(value) {
  if (value === null || value === undefined) return "-";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" });
}
