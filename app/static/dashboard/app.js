const api = {
  dashboard: "/api/v1/dashboard",
  settings: "/api/v1/settings",
  edgeRules: "/api/v1/edge-rules",
  evaluate: "/api/v1/edge-rules/evaluate",
  testAlert: "/api/v1/notifications/discord/test",
  signals: "/api/v1/signals?limit=100",
};

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("evaluateNowButton").addEventListener("click", evaluateNow);
  document.getElementById("sendTestAlertButton").addEventListener("click", sendTestAlert);
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
  renderSignalBoard(dashboard.rule_summaries || []);
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
    ["Name", "Symbol", "TF", "Rule", "Tolerance", "Cooldown", "Status", ""],
    rules,
    (rule) => [
      rule.name,
      rule.symbol,
      rule.timeframe.toUpperCase(),
      `${rule.ma_type.toUpperCase()}${rule.ma_period} touch`,
      `${formatPercent(rule.tolerance_pct)}%`,
      `${rule.cooldown_hours}h`,
      rule.enabled ? `<span class="pill on">Watching</span>` : `<span class="pill">Paused</span>`,
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

function renderSignalBoard(items) {
  const board = document.getElementById("signalBoard");
  if (!items.length) {
    board.innerHTML = `<div class="empty-card">아직 감시 중인 신호가 없습니다.</div>`;
    return;
  }

  board.innerHTML = items
    .map(
      (item) => `
        <article class="signal-card">
          <div class="signal-card-top">
            <span class="pill ${item.enabled ? "on" : ""}">${item.status}</span>
            <strong>${item.symbol}</strong>
          </div>
          <h3>${item.name}</h3>
          <p>${item.timeframe.toUpperCase()} · ${item.rule} · ${formatPercent(item.tolerance_pct)}% tolerance</p>
          <div class="signal-stats">
            <div>
              <span>Total</span>
              <strong>${item.signal_count}</strong>
            </div>
            <div>
              <span>30D</span>
              <strong>${item.signals_30d}</strong>
            </div>
            <div>
              <span>Last</span>
              <strong>${item.last_signal_at ? formatShortDate(item.last_signal_at) : "None"}</strong>
            </div>
          </div>
          <footer>
            <span>${item.last_situation || "조건 대기 중"}</span>
            <span>${formatNumber(item.last_price)}</span>
          </footer>
        </article>
      `
    )
    .join("");
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

async function evaluateNow() {
  const target = document.getElementById("evaluationResult");
  target.textContent = "평가 중...";
  const response = await fetch(api.evaluate, { method: "POST" });
  const result = await response.json();
  target.textContent = `평가 ${result.rules_evaluated}, 매칭 ${result.rules_matched}, 알림 ${result.signals_created}`;
  await refreshAll();
}

async function sendTestAlert() {
  const target = document.getElementById("testAlertStatus");
  target.textContent = "전송 중...";
  const response = await fetch(api.testAlert, { method: "POST" });
  if (!response.ok) {
    const error = await response.json();
    target.textContent = error.detail || "전송 실패";
    return;
  }
  target.textContent = "테스트 알림 전송 완료";
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

function formatShortDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Seoul",
  });
}
