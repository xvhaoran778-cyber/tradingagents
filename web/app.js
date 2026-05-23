const form = document.querySelector("#analyzeForm");
const tickerInput = document.querySelector("#ticker");
const clearBtn = document.querySelector("#clearBtn");
const submitBtn = document.querySelector("#submitBtn");
const stateBadge = document.querySelector("#stateBadge");
const statusDot = document.querySelector("#statusDot");
const statusText = document.querySelector("#statusText");
const stageItems = [...document.querySelectorAll("#stageList li")];
const reportText = document.querySelector("#reportText");
const tabs = document.querySelector("#tabs");
const clock = document.querySelector("#clock");
const toast = document.querySelector("#toast");
const copyBtn = document.querySelector("#copyBtn");
const recentContainer = document.querySelector("#recentContainer");
const recentList = document.querySelector("#recentList");
const suggestions = document.querySelector("#suggestions");
const historyPanel = document.querySelector("#historyPanel");
const historyToggle = document.querySelector("#historyToggle");

let latest = null;
let activeTab = "technical";
let currentController = null;
let streamDone = false;

const stageKeyOrder = ["collect", "analysts", "debate", "trader", "risk", "decision"];

/* ---------- clock ---------- */
function setClock() {
  const now = new Date();
  clock.textContent = now.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
setClock();
setInterval(setClock, 1000);

/* ---------- clear ---------- */
clearBtn.addEventListener("click", () => {
  tickerInput.value = "";
  tickerInput.focus();
  hideSuggestions();
});

/* ---------- keyboard shortcuts ---------- */
tickerInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !submitBtn.disabled) {
    e.preventDefault();
    form.requestSubmit();
  }
  if (e.key === "ArrowDown") return navigateSuggestion(1);
  if (e.key === "ArrowUp") return navigateSuggestion(-1);
  if (e.key === "Escape") return hideSuggestions();
});

document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !submitBtn.disabled) {
    e.preventDefault();
    form.requestSubmit();
  }
});

/* ---------- autocomplete ---------- */
let debounceTimer = null;
let suggestionIndex = -1;

tickerInput.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  const val = tickerInput.value.trim();
  if (!val || /^\d{6}$/.test(val)) {
    hideSuggestions();
    return;
  }
  debounceTimer = setTimeout(() => fetchSuggestions(val), 300);
});

tickerInput.addEventListener("blur", () => {
  setTimeout(hideSuggestions, 200);
});

tickerInput.addEventListener("focus", () => {
  const val = tickerInput.value.trim();
  if (val && !/^\d{6}$/.test(val)) {
    fetchSuggestions(val);
  }
});

async function fetchSuggestions(query) {
  let resp;
  try {
    resp = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
  } catch (e) {
    return;
  }
  if (!resp.ok) return;
  const data = await resp.json();
  const results = data.results || [];
  if (results.length === 0) {
    hideSuggestions();
    return;
  }
  renderSuggestions(results);
}

function renderSuggestions(items) {
  suggestions.innerHTML = "";
  suggestionIndex = -1;
  items.forEach((item, i) => {
    const div = document.createElement("div");
    div.className = "suggestion-item";
    div.innerHTML = `<span class="suggestion-code">${item.code}</span><span class="suggestion-name">${item.name}</span>`;
    div.addEventListener("mousedown", (e) => {
      e.preventDefault();
      selectSuggestion(item.code);
    });
    div.addEventListener("mouseenter", () => {
      suggestionIndex = i;
      highlightSuggestion();
    });
    suggestions.appendChild(div);
  });
  suggestions.classList.remove("hidden");
}

function hideSuggestions() {
  suggestions.classList.add("hidden");
  suggestionIndex = -1;
}

function navigateSuggestion(dir) {
  if (suggestions.classList.contains("hidden")) return;
  const items = suggestions.querySelectorAll(".suggestion-item");
  if (!items.length) return;
  suggestionIndex = Math.max(-1, Math.min(items.length - 1, suggestionIndex + dir));
  highlightSuggestion();
  if (suggestionIndex >= 0) {
    const code = items[suggestionIndex].querySelector(".suggestion-code").textContent;
    tickerInput.value = code;
  }
}

function highlightSuggestion() {
  const items = suggestions.querySelectorAll(".suggestion-item");
  items.forEach((el, i) => el.classList.toggle("active", i === suggestionIndex));
}

function selectSuggestion(code) {
  tickerInput.value = code;
  hideSuggestions();
  form.requestSubmit();
}

/* ---------- form submit ---------- */
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const rawInput = tickerInput.value.trim();
  if (!rawInput) {
    showToast("请输入股票代码或名称", "warn");
    return;
  }

  if (currentController) {
    currentController.abort();
  }

  latest = null;
  streamDone = false;
  setRunning(true);
  resetStages();
  showSkeleton();

  try {
    const ticker = await resolveTicker(rawInput);
    if (!ticker) {
      setRunning(false);
      hideSkeleton();
      return;
    }
    addRecent(rawInput);
    await startStream(ticker);
  } catch (error) {
    if (error.name === "AbortError") return;
    showError(error.message || "分析请求失败");
  } finally {
    setRunning(false);
    hideSkeleton();
  }
});

async function resolveTicker(input) {
  if (/^\d{6}$/.test(input)) return input;

  let resp;
  try {
    resp = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: input }),
    });
  } catch (e) {
    showToast("搜索请求失败: " + e.message, "error");
    return null;
  }

  let data;
  try {
    data = await resp.json();
  } catch (e) {
    showToast("搜索服务返回异常，请检查服务器是否运行", "error");
    return null;
  }

  if (!resp.ok) {
    showToast(data.error || "搜索失败", "error");
    return null;
  }

  const results = data.results || [];
  if (results.length === 0) {
    showToast(`未找到匹配的股票: ${input}`, "error");
    return null;
  }

  const seen = new Set();
  const deduped = results.filter((r) => {
    if (seen.has(r.code)) return false;
    seen.add(r.code);
    return true;
  });

  if (deduped.length === 1) {
    tickerInput.value = deduped[0].code;
    return deduped[0].code;
  }

  const first = deduped[0];
  const second = deduped[1];
  if (first && second && first.code !== second.code) {
    showToast(`找到多个匹配: ${deduped.map((r) => `${r.code} ${r.name}`).join(" / ")}`, "warn");
    return null;
  }

  tickerInput.value = first.code;
  return first.code;
}

function setRunning(isRunning) {
  submitBtn.disabled = isRunning;
  if (isRunning) {
    submitBtn.innerHTML = '<span class="spinner"></span> 分析中...';
    setBadge("运行中", "running");
    statusDot.className = "dot pulse";
    statusText.textContent = "分析中";
  } else {
    submitBtn.innerHTML = '<svg class="play-icon" viewBox="0 0 24 24" width="14" height="14"><path d="M8 5v14l11-7z" fill="currentColor"/></svg> 开始分析';
    statusDot.className = "dot";
    statusText.textContent = "就绪";
  }
}

function setBadge(text, className) {
  stateBadge.textContent = text;
  stateBadge.className = `badge ${className}`;
}

function resetStages() {
  stageItems.forEach((item) => {
    item.className = "";
    item.classList.remove("done", "active", "error");
  });
}

function markStageDone(stageId) {
  stageItems.forEach((item) => {
    if (item.dataset.stage === stageId || stageKeyOrder.indexOf(item.dataset.stage) < stageKeyOrder.indexOf(stageId)) {
      item.classList.add("done");
      item.classList.remove("active");
    }
  });
}

/* ---------- skeleton ---------- */
function showSkeleton() {
  document.querySelector("#rating").style.display = "none";
  document.querySelector("#ratingSkeleton").classList.remove("hidden");
  document.querySelector("#summary").style.display = "none";
  document.querySelector("#summarySkeleton").classList.remove("hidden");
  document.querySelector("#metricsArea").style.display = "none";
  document.querySelector("#metricsSkeleton").classList.remove("hidden");
  document.querySelector("#thesis").style.display = "none";
  document.querySelector("#thesisSkeleton").classList.remove("hidden");
  document.querySelector("#riskWarning").style.display = "none";
  document.querySelector("#riskSkeleton").classList.remove("hidden");
}

function hideSkeleton() {
  document.querySelector("#rating").style.display = "";
  document.querySelector("#ratingSkeleton").classList.add("hidden");
  document.querySelector("#summary").style.display = "";
  document.querySelector("#summarySkeleton").classList.add("hidden");
  document.querySelector("#metricsArea").style.display = "";
  document.querySelector("#metricsSkeleton").classList.add("hidden");
  document.querySelector("#thesis").style.display = "";
  document.querySelector("#thesisSkeleton").classList.add("hidden");
  document.querySelector("#riskWarning").style.display = "";
  document.querySelector("#riskSkeleton").classList.add("hidden");
}

/* ---------- SSE ---------- */
async function startStream(ticker) {
  const controller = new AbortController();
  currentController = controller;
  streamDone = false;

  const response = await fetch("/api/analyze/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker }),
    signal: controller.signal,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
    throw new Error(err.error || "请求失败");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (!streamDone) {
    let result;
    try {
      result = await reader.read();
    } catch (e) {
      if (e.name === "AbortError") break;
      throw e;
    }
    const { done, value } = result;
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let event = null;
    let data = "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        event = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        data = line.slice(6).trim();
      } else if (line === "" && event && data) {
        try {
          handleEvent(event, JSON.parse(data));
        } catch (e) { /* ignore */ }
        event = null;
        data = "";
      }
    }
  }

  currentController = null;
}

function handleEvent(event, data) {
  switch (event) {
    case "progress":
      handleProgress(data);
      break;
    case "result":
      latest = data;
      renderResult(data);
      setBadge("完成", "done");
      statusDot.className = "dot";
      statusText.textContent = "就绪";
      streamDone = true;
      break;
    case "done":
      streamDone = true;
      break;
    case "error":
      showError(data.error || "分析出错");
      break;
  }
}

function handleProgress(data) {
  const phase = data.phase;

  if (phase === "collect") {
    markStageDone("collect");
    stageItems.forEach((e) => e.dataset.stage === "analysts" && e.classList.add("active"));
  } else if (phase === "analysts" && data.detail === "分析师团队完成") {
    markStageDone("analysts");
    stageItems.forEach((e) => e.dataset.stage === "debate" && e.classList.add("active"));
  } else if (phase === "debate" && data.detail === "研究员辩论完成") {
    markStageDone("debate");
    stageItems.forEach((e) => e.dataset.stage === "trader" && e.classList.add("active"));
  } else if (phase === "trader" && data.detail === "交易方案完成") {
    markStageDone("trader");
    stageItems.forEach((e) => e.dataset.stage === "risk" && e.classList.add("active"));
  } else if (phase === "risk" && data.detail === "风险评估完成") {
    markStageDone("risk");
    stageItems.forEach((e) => e.dataset.stage === "decision" && e.classList.add("active"));
  } else if (phase === "decision" && data.detail === "最终决策完成") {
    markStageDone("decision");
  } else if (phase === "done") {
    stageItems.forEach((e) => e.classList.add("done"));
  }

  if (data.detail && !data.detail.endsWith("完成")) {
    reportText.textContent = data.detail;
    reportText.classList.add("live");
    setTimeout(() => reportText.classList.remove("live"), 500);
  }
}

function showError(message) {
  setBadge("出错", "error");
  statusDot.className = "dot error-dot";
  statusText.textContent = "出错";
  latest = { error: message };
  reportText.textContent = `❌ ${message}`;
  showToast(message, "error");
}

/* ---------- render result ---------- */
function renderResult(data) {
  const decision = data.final_decision || {};
  const realtime = data.raw_data?.realtime || {};
  const research = data.research_plan || {};
  const trade = data.trade_proposal || {};

  const ratingEl = document.querySelector("#rating");
  ratingEl.textContent = `${decision.rating_cn || "未生成"} ${decision.rating ? `(${decision.rating})` : ""}`;
  ratingEl.style.color = ratingColor(decision.rating);
  document.querySelector("#summary").textContent = decision.executive_summary || "暂无摘要。";

  const meta = `${data.ticker || "--"} ${data.ticker_name || ""}`;
  const searchInput = data.search_input;
  document.querySelector("#tickerMeta").textContent = searchInput && searchInput !== data.ticker ? `${searchInput} → ${meta}` : meta;

  document.querySelector("#currentPrice").textContent = formatValue(realtime.current);
  const cp = document.querySelector("#changePct");
  cp.textContent = formatPct(realtime.change_pct);
  cp.style.color = (realtime.change_pct || 0) >= 0 ? "var(--good)" : "var(--bad)";
  document.querySelector("#targetPrice").textContent = decision.price_target || trade.target_price || "--";
  document.querySelector("#horizon").textContent = decision.time_horizon || research.time_horizon || "--";
  document.querySelector("#thesis").textContent = decision.investment_thesis || "暂无内容。";
  document.querySelector("#riskWarning").textContent = decision.risk_warning || "暂无内容。";
  document.querySelector("#newsCount").textContent = `${data.raw_data?.news?.length || 0} 条新闻`;

  renderKv("#researchList", [
    ["推荐", research.recommendation],
    ["置信度", research.confidence == null ? "" : `${Math.round(research.confidence * 100)}%`],
    ["周期", research.time_horizon],
    ["理由", research.rationale],
    ["关键风险", Array.isArray(research.key_risks) ? research.key_risks.join(" / ") : ""],
  ]);

  renderKv("#tradeList", [
    ["操作", trade.action],
    ["入场区间", trade.entry_price_range],
    ["建议仓位", trade.position_sizing],
    ["止损", trade.stop_loss],
    ["目标位", trade.target_price],
    ["理由", trade.reasoning],
  ]);

  renderReport();
}

function ratingColor(rating) {
  return ({ Buy: "var(--good)", Overweight: "var(--good)", Hold: "var(--warn)", Underweight: "var(--bad)", Sell: "var(--bad)" })[rating] || "var(--text)";
}

function renderKv(selector, rows) {
  const node = document.querySelector(selector);
  node.innerHTML = "";
  rows.forEach(([label, value]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value || "--";
    node.append(dt, dd);
  });
}

function renderReport() {
  if (!latest || latest.error) return;
  const reports = latest.reports || {};
  const risk = latest.risk_assessments || [];
  const content = {
    technical: reports.technical,
    sentiment: reports.sentiment,
    news: reports.news,
    fundamental: reports.fundamental,
    risk: risk.map((item) => `【${item.agent}】\n${item.assessment}`).join("\n\n"),
    logs: latest.logs,
  }[activeTab];
  reportText.textContent = content || "暂无内容。";
  reportText.classList.remove("live");
}

/* ---------- tab switching ---------- */
tabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-tab]");
  if (!button) return;
  activeTab = button.dataset.tab;
  [...tabs.querySelectorAll("button")].forEach((item) => item.classList.toggle("active", item === button));
  renderReport();
});

/* ---------- copy ---------- */
copyBtn.addEventListener("click", copyReport);

function copyReport() {
  if (!latest || latest.error) {
    showToast("没有可复制的内容，请先运行分析", "warn");
    return;
  }

  const decision = latest.final_decision || {};
  const parts = [
    `${"=".repeat(40)}`,
    `Trading Agent 分析报告`,
    `${"=".repeat(40)}`,
    ``,
    `股票: ${latest.ticker} ${latest.ticker_name || ""}`,
    `评级: ${decision.rating_cn || ""} (${decision.rating || ""})`,
    `摘要: ${decision.executive_summary || ""}`,
    ``,
    `当前价: ${formatValue(latest.raw_data?.realtime?.current)}`,
    `涨跌幅: ${formatPct(latest.raw_data?.realtime?.change_pct)}`,
    `目标价: ${decision.price_target || "--"}`,
    `持有周期: ${decision.time_horizon || "--"}`,
    ``,
    `投资论点:`,
    decision.investment_thesis || "",
    ``,
    `风险提示:`,
    decision.risk_warning || "",
  ];

  if (latest.research_plan) {
    const rp = latest.research_plan;
    parts.push(``, `研究推荐: ${rp.recommendation} (置信度: ${Math.round((rp.confidence || 0) * 100)}%)`);
    parts.push(`理由: ${rp.rationale || ""}`);
  }

  if (latest.trade_proposal) {
    const tp = latest.trade_proposal;
    parts.push(``, `交易操作: ${tp.action || ""}`);
    if (tp.entry_price_range) parts.push(`入场区间: ${tp.entry_price_range}`);
    if (tp.position_sizing) parts.push(`仓位: ${tp.position_sizing}`);
    if (tp.stop_loss) parts.push(`止损: ${tp.stop_loss}`);
    if (tp.target_price) parts.push(`目标位: ${tp.target_price}`);
  }

  parts.push(``, `${"=".repeat(40)}`);

  navigator.clipboard.writeText(parts.join("\n")).then(() => {
    showToast("报告已复制到剪贴板", "success");
  }).catch(() => {
    showToast("复制失败，请手动复制", "error");
  });
}

/* ---------- toast ---------- */
function showToast(message, type) {
  toast.textContent = message;
  toast.className = `toast ${type}`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.add("hidden"), 3000);
}

function formatValue(value) {
  if (value == null || value === "") return "--";
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(2) : String(value);
}

function formatPct(value) {
  if (value == null || value === "") return "--";
  const n = Number(value);
  return Number.isFinite(n) ? `${n > 0 ? "+" : ""}${n.toFixed(2)}%` : String(value);
}

/* ---------- recent stocks ---------- */
function addRecent(input) {
  let recents = JSON.parse(localStorage.getItem("trading_agent_recent") || "[]");
  recents = [input, ...recents.filter((t) => t !== input)].slice(0, 5);
  localStorage.setItem("trading_agent_recent", JSON.stringify(recents));
  renderRecents();
}

function renderRecents() {
  const recents = JSON.parse(localStorage.getItem("trading_agent_recent") || "[]");
  if (recents.length === 0) {
    recentContainer.classList.add("hidden");
    return;
  }
  recentContainer.classList.remove("hidden");
  recentList.innerHTML = "";
  recents.forEach((input) => {
    const tag = document.createElement("button");
    tag.className = "recent-tag";
    tag.textContent = input;
    tag.addEventListener("click", () => {
      tickerInput.value = input;
      form.requestSubmit();
    });
    recentList.appendChild(tag);
  });
}

renderRecents();

/* ---------- history ---------- */
historyToggle.addEventListener("click", async () => {
  if (historyToggle.textContent === "展开") {
    historyToggle.textContent = "加载中...";
    historyToggle.disabled = true;
    await loadHistory();
    historyToggle.textContent = "收起";
    historyToggle.disabled = false;
    historyPanel.classList.remove("hidden");
  } else {
    historyPanel.classList.add("hidden");
    historyToggle.textContent = "展开";
  }
});

async function loadHistory() {
  let resp;
  try {
    resp = await fetch("/api/history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 20 }),
    });
  } catch (e) {
    historyPanel.innerHTML = '<div class="hint" style="padding:8px">无法加载历史记录</div>';
    return;
  }
  if (!resp.ok) {
    historyPanel.innerHTML = '<div class="hint" style="padding:8px">加载失败</div>';
    return;
  }
  const data = await resp.json();
  const items = data.history || [];
  if (items.length === 0) {
    historyPanel.innerHTML = '<div class="hint" style="padding:8px">暂无历史记录</div>';
    return;
  }
  historyPanel.innerHTML = "";
  items.forEach((item) => {
    const div = document.createElement("div");
    div.className = "history-item";
    div.innerHTML = `
      <span class="history-item-ticker">${item.ticker}</span>
      <span class="history-item-name">${item.ticker_name || ""}</span>
      <span class="history-item-time">${item.created_at ? item.created_at.slice(0, 16) : ""}</span>
    `;
    div.addEventListener("click", () => loadHistoryDetail(item.id));
    historyPanel.appendChild(div);
  });
}

async function loadHistoryDetail(id) {
  let resp;
  try {
    resp = await fetch(`/api/history/${id}`, { method: "POST" });
  } catch (e) {
    showToast("加载历史详情失败", "error");
    return;
  }
  if (!resp.ok) return;
  const data = await resp.json();
  if (data.state) {
    renderResult(data.state);
    setBadge("完成", "done");
    statusDot.className = "dot";
    statusText.textContent = "就绪";
    showToast("已加载历史分析", "success");
    hideSkeleton();
    setRunning(false);
  }
}
