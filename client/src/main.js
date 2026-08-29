const state = {
  evaluations: [],
  selectedId: null,
  selected: null,
  session: null,
  job: null,
  busy: false,
  error: "",
  stepInput: "echo: hello from inspector",
  rpcResult: null,
  activeTab: "scenarios",
  logs: [],
};

const app = document.querySelector("#app");

init();

async function init() {
  render();
  await loadEvaluations();
}

async function loadEvaluations() {
  await withBusy(async () => {
    const payload = await api("/api/evaluations");
    state.evaluations = payload.evaluations || [];
    if (!state.selectedId && state.evaluations[0]) {
      await selectEvaluation(state.evaluations[0].id);
    }
  });
}

async function selectEvaluation(id) {
  await withBusy(async () => {
    state.selectedId = id;
    state.selected = await api(`/api/evaluations/${encodeURIComponent(id)}`);
    state.job = null;
    state.rpcResult = null;
    state.stepInput = sampleInput(state.selected);
    state.activeTab = "scenarios";
  });
}

async function connectToSelected() {
  if (!state.selected) return;
  await withBusy(async () => {
    const previousSession = state.session;
    state.session = null;
    if (previousSession) {
      await api(`/api/sessions/${encodeURIComponent(previousSession.id)}`, { method: "DELETE" });
    }
    const targetInput = document.querySelector("#target-input");
    const target = targetInput?.value.trim() || state.selected.target;
    state.session = await api("/api/sessions", {
      method: "POST",
      body: { target },
    });
    state.logs = state.session.logs || [];
    state.activeTab = "notifications";
  });
}

async function disconnectSession() {
  if (!state.session) return;
  const sessionId = state.session.id;
  state.session = null;
  state.rpcResult = null;
  await api(`/api/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  render();
}

async function sendStep() {
  if (!state.session) return;
  await withBusy(async () => {
    const input = document.querySelector("#step-input")?.value || "";
    state.stepInput = input;
    state.rpcResult = await api(`/api/sessions/${encodeURIComponent(state.session.id)}/rpc`, {
      method: "POST",
      body: {
        method: "agent/step",
        params: { input },
      },
    });
    state.logs = [
      ...(state.logs || []),
      {
        time: new Date().toISOString(),
        level: state.rpcResult.error ? "error" : "info",
        message: `agent/step ${state.rpcResult.error ? "failed" : "completed"}`,
        payload: state.rpcResult,
      },
    ];
    state.activeTab = "results";
  });
}

async function resetAgent() {
  if (!state.session) return;
  await withBusy(async () => {
    const result = await api(`/api/sessions/${encodeURIComponent(state.session.id)}/rpc`, {
      method: "POST",
      body: { method: "agent/reset", params: {} },
    });
    state.logs = [
      ...(state.logs || []),
      {
        time: new Date().toISOString(),
        level: result.error ? "error" : "info",
        message: `agent/reset ${result.error ? "failed" : "completed"}`,
        payload: result,
      },
    ];
    state.rpcResult = result;
    state.activeTab = "notifications";
  });
}

async function runEvaluation() {
  if (!state.selected) return;
  await withBusy(async () => {
    const started = await api(`/api/evaluations/${encodeURIComponent(state.selected.id)}/run`, {
      method: "POST",
    });
    state.job = started;
    state.activeTab = "results";
    pollJob(started.job_id);
  });
}

async function pollJob(jobId) {
  let keepGoing = true;
  while (keepGoing) {
    await sleep(700);
    const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
    state.job = job;
    keepGoing = job.status === "running";
    render();
  }
}

function render() {
  app.innerHTML = `
    <div class="shell">
      <header class="topbar">
        <div>
          <h1>ECP Inspector</h1>
        </div>
        <button class="icon-button" id="refresh-button" title="Refresh evaluations" aria-label="Refresh evaluations">Refresh</button>
      </header>

      <main class="workspace">
        <aside class="sidebar">
          <div class="panel-heading">
            <h2>Evaluations</h2>
            <span>${state.evaluations.length}</span>
          </div>
          <div class="evaluation-list">
            ${state.evaluations.map(renderEvaluationItem).join("") || emptyState("No manifests found in examples/.")}
          </div>
        </aside>

        <section class="main-panel">
          ${state.error ? `<div class="error-banner">${escapeHtml(state.error)}</div>` : ""}
          ${state.selected ? renderInspector() : emptyState("Select an evaluation to begin.")}
        </section>
      </main>
    </div>
  `;

  bindEvents();
}

function renderEvaluationItem(evaluation) {
  const active = evaluation.id === state.selectedId ? "active" : "";
  return `
    <button class="evaluation-item ${active}" data-select="${escapeAttr(evaluation.id)}">
      <span class="item-title">${escapeHtml(evaluation.name)}</span>
      <span class="item-meta">${escapeHtml(evaluation.transport)} | ${escapeHtml(evaluation.status)}</span>
    </button>
  `;
}

function renderInspector() {
  const evaluation = state.selected;
  return `
    <section class="connection-pane">
      <div class="connection-copy">
        <h2>${escapeHtml(evaluation.name)}</h2>
        <p>${escapeHtml(evaluation.description)}</p>
      </div>
      <div class="target-row">
        <label for="target-input">Target</label>
        <input id="target-input" value="${escapeAttr(evaluation.target)}" spellcheck="false" />
      </div>
      <div class="connection-actions">
        <span class="status-pill">${escapeHtml(evaluation.transport)}</span>
        <button id="connect-button">${state.session ? "Reconnect" : "Connect"}</button>
        ${state.session ? `<button id="disconnect-button" class="secondary">Disconnect</button>` : ""}
        <button id="run-button" class="primary">Run Evaluation</button>
      </div>
    </section>

    <nav class="tabs" aria-label="Inspector tabs">
      ${tabButton("scenarios", "Scenarios")}
      ${tabButton("results", "Results")}
      ${tabButton("notifications", "Notifications")}
      ${tabButton("manifest", "Manifest")}
    </nav>

    <section class="tab-surface">
      ${renderActiveTab()}
    </section>
  `;
}

function renderActiveTab() {
  if (state.activeTab === "results") return renderResults();
  if (state.activeTab === "notifications") return renderNotifications();
  if (state.activeTab === "manifest") return renderManifest();
  return renderScenarios();
}

function renderScenarios() {
  const scenarios = state.selected.scenarios || [];
  return `
    <div class="scenario-grid">
      ${scenarios.map(renderScenario).join("")}
    </div>
    <div class="step-tester">
      <div>
        <h3>Step Tester</h3>
      </div>
      <textarea id="step-input" rows="3">${escapeHtml(state.stepInput)}</textarea>
      <div class="tester-actions">
        <button id="send-step-button" ${state.session ? "" : "disabled"}>Send Step</button>
        <button id="reset-button" class="secondary" ${state.session ? "" : "disabled"}>Reset</button>
      </div>
    </div>
  `;
}

function renderScenario(scenario, index) {
  return `
    <article class="scenario">
      <div class="scenario-heading">
        <h3>${escapeHtml(scenario.name || `Scenario ${index + 1}`)}</h3>
        <span>${(scenario.steps || []).length} step${(scenario.steps || []).length === 1 ? "" : "s"}</span>
      </div>
      ${(scenario.steps || []).map(renderStep).join("")}
    </article>
  `;
}

function renderStep(step) {
  return `
    <div class="step">
      <p>${escapeHtml(step.input)}</p>
      <div class="grader-row">
        ${(step.graders || []).map((grader) => `<span>${escapeHtml(grader.type)}</span>`).join("")}
      </div>
    </div>
  `;
}

function renderResults() {
  const job = state.job;
  const rpc = state.rpcResult;
  return `
    <div class="result-layout">
      <section>
        <h3>Evaluation Run</h3>
        ${
          job
            ? `
              <div class="metric-strip">
                <span>Status: ${escapeHtml(job.status)}</span>
                <span>Passed: ${escapeHtml(String(job.results?.passed ?? "-"))}</span>
                <span>Total: ${escapeHtml(String(job.results?.total ?? "-"))}</span>
              </div>
              ${renderScenarioResults(job.results?.scenarios || [])}
              ${job.stderr ? `<pre class="log-output">${escapeHtml(job.stderr)}</pre>` : ""}
            `
            : emptyState("Run the selected manifest to see grader results.")
        }
      </section>
      <section>
        <h3>Last RPC Response</h3>
        ${rpc ? `<pre>${escapeHtml(JSON.stringify(rpc, null, 2))}</pre>` : emptyState("Send a step to inspect the JSON-RPC response.")}
      </section>
    </div>
  `;
}

function renderScenarioResults(scenarios) {
  if (!scenarios.length) return "";
  return scenarios
    .map(
      (scenario) => `
        <article class="scenario-result">
          <h4>${escapeHtml(scenario.name)}</h4>
          ${(scenario.steps || [])
            .map(
              (step) => `
                <div class="step-result">
                  <p>${escapeHtml(step.input)}</p>
                  ${(step.checks || [])
                    .map(
                      (check) => `
                        <span class="check ${check.passed ? "pass" : "fail"}">
                          ${check.passed ? "PASS" : "FAIL"} | ${escapeHtml(check.type)}
                        </span>
                      `
                    )
                    .join("")}
                </div>
              `
            )
            .join("")}
        </article>
      `
    )
    .join("");
}

function renderNotifications() {
  const logs = [...(state.logs || []), ...(state.session?.logs || [])];
  return `
    <div class="notifications">
      ${logs.length ? logs.map(renderLog).join("") : emptyState("No protocol messages yet.")}
    </div>
  `;
}

function renderLog(log) {
  return `
    <details class="log-line">
      <summary>
        <span>${escapeHtml(log.level || "info")}</span>
        <strong>${escapeHtml(log.message || "")}</strong>
        <time>${escapeHtml(new Date(log.time || Date.now()).toLocaleTimeString())}</time>
      </summary>
      ${log.payload ? `<pre>${escapeHtml(JSON.stringify(log.payload, null, 2))}</pre>` : ""}
    </details>
  `;
}

function renderManifest() {
  return `<pre>${escapeHtml(state.selected.raw || "")}</pre>`;
}

function tabButton(id, label) {
  return `<button class="${state.activeTab === id ? "active" : ""}" data-tab="${id}">${label}</button>`;
}

function emptyState(message) {
  return `<div class="empty">${escapeHtml(message)}</div>`;
}

function bindEvents() {
  document.querySelector("#refresh-button")?.addEventListener("click", loadEvaluations);
  document.querySelectorAll("[data-select]").forEach((button) => {
    button.addEventListener("click", () => selectEvaluation(button.dataset.select));
  });
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      render();
    });
  });
  document.querySelector("#connect-button")?.addEventListener("click", connectToSelected);
  document.querySelector("#disconnect-button")?.addEventListener("click", disconnectSession);
  document.querySelector("#run-button")?.addEventListener("click", runEvaluation);
  document.querySelector("#send-step-button")?.addEventListener("click", sendStep);
  document.querySelector("#reset-button")?.addEventListener("click", resetAgent);
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error?.message || `Request failed: ${response.status}`);
  }
  return payload;
}

async function withBusy(operation) {
  state.busy = true;
  state.error = "";
  render();
  try {
    await operation();
  } catch (error) {
    state.error = error instanceof Error ? error.message : String(error);
    state.logs = [
      ...(state.logs || []),
      {
        time: new Date().toISOString(),
        level: "error",
        message: state.error,
      },
    ];
  } finally {
    state.busy = false;
    render();
  }
}

function sampleInput(evaluation) {
  return evaluation?.scenarios?.[0]?.steps?.[0]?.input || "hello";
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#96;");
}
