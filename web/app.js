const $ = (s, p) => (p || document).querySelector(s);
const $$ = (s, p) => [...(p || document).querySelectorAll(s)];

const form = $("#form");
const input = $("#ticker");
const clearBtn = $("#clearBtn");
const submitBtn = $("#submitBtn");
const statusDot = $("#statusDot");
const statusText = $("#statusText");
const badge = $("#badge");
const stages = $$("#stages li");
const reportEl = $("#report");
const tabs = $("#tabs");
const clock = $("#clock");
const toast = $("#toast");
const copyBtn = $("#copyBtn");
const recentContainer = $("#recent");
const recentList = $("#recentList");
const suggestions = $("#suggestions");
const historyPanel = $("#historyPanel");
const historyBtn = $("#historyBtn");
const loader = $("#loader");
const loaderText = $("#loaderText");
const elapsed = $("#elapsed");

let latest = null;
let activeTab = "technical";
let abortC = null;
let timerInt = null;
let timerSec = 0;
const STAGES = ["collect","analysts","debate","trader","risk","decision"];

/* ---------- clock ---------- */
(function tick() {
  clock.textContent = new Date().toLocaleTimeString("zh-CN", { hour:"2-digit", minute:"2-digit", second:"2-digit" });
  setTimeout(tick, 1000 - Date.now() % 1000);
})();

/* ---------- clear ---------- */
clearBtn.addEventListener("click", () => { input.value = ""; input.focus(); hideSugg(); });

/* ---------- keyboard ---------- */
input.addEventListener("keydown", e => {
  if (e.key === "Enter" && !submitBtn.disabled) { e.preventDefault(); form.requestSubmit(); }
  if (e.key === "ArrowDown") return navSugg(1);
  if (e.key === "ArrowUp") return navSugg(-1);
  if (e.key === "Escape") return hideSugg();
});

/* ---------- autocomplete ---------- */
let deb = null, suggIdx = -1;
input.addEventListener("input", () => {
  clearTimeout(deb);
  const v = input.value.trim();
  if (!v || /^\d{6}$/.test(v)) { hideSugg(); return; }
  deb = setTimeout(() => fetchSugg(v), 300);
});
input.addEventListener("blur", () => setTimeout(hideSugg, 200));
input.addEventListener("focus", () => {
  const v = input.value.trim();
  if (v && !/^\d{6}$/.test(v)) fetchSugg(v);
});

async function fetchSugg(q) {
  let r;
  try { r = await fetch("/api/search", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({query:q}) }); }
  catch { return; }
  if (!r.ok) return;
  const items = (await r.json()).results || [];
  if (!items.length) { hideSugg(); return; }
  renderSugg(items);
}

function renderSugg(items) {
  suggestions.innerHTML = "";
  suggIdx = -1;
  items.forEach((item, i) => {
    const div = document.createElement("div");
    div.className = "suggestion-item";
    div.innerHTML = `<span class="suggestion-code">${item.code}</span><span>${item.name}</span>`;
    div.addEventListener("mousedown", e => { e.preventDefault(); pickSugg(item.code); });
    div.addEventListener("mouseenter", () => { suggIdx = i; highlightSugg(); });
    suggestions.appendChild(div);
  });
  suggestions.classList.remove("hidden");
}

function hideSugg() { suggestions.classList.add("hidden"); suggIdx = -1; }

function navSugg(dir) {
  if (suggestions.classList.contains("hidden")) return;
  const items = suggestions.querySelectorAll(".suggestion-item");
  if (!items.length) return;
  suggIdx = Math.max(-1, Math.min(items.length - 1, suggIdx + dir));
  highlightSugg();
  if (suggIdx >= 0) input.value = items[suggIdx].querySelector(".suggestion-code").textContent;
}

function highlightSugg() {
  suggestions.querySelectorAll(".suggestion-item").forEach((el, i) => el.classList.toggle("active", i === suggIdx));
}

function pickSugg(code) { input.value = code; hideSugg(); form.requestSubmit(); }

/* ---------- submit ---------- */
form.addEventListener("submit", async e => {
  e.preventDefault();
  const raw = input.value.trim();
  if (!raw) { showToast("请输入股票代码或名称", "warn"); return; }

  if (abortC) { abortC.abort(); abortC = null; }
  clearInterval(timerInt);

  latest = null;
  setBusy(true);
  resetStages();
  showSkel();
  hideResult();

  try {
    const ticker = await resolveTicker(raw);
    if (!ticker) { setBusy(false); hideSkel(); return; }
    addRecent(raw);
    await startLoad(ticker);
  } catch (err) {
    if (err.name === "AbortError") return;
    showErr(err.message || "分析失败");
  } finally {
    setBusy(false);
    hideSkel();
    hideLoader();
  }
});

async function resolveTicker(raw) {
  if (/^\d{6}$/.test(raw)) return raw;
  let r;
  try { r = await fetch("/api/search", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({query:raw}) }); }
  catch (e) { showToast("搜索请求失败", "err"); return null; }
  let data;
  try { data = await r.json(); } catch { showToast("搜索服务异常", "err"); return null; }
  if (!r.ok) { showToast(data.error || "搜索失败", "err"); return null; }
  const items = data.results || [];
  if (!items.length) { showToast("未找到匹配: " + raw, "err"); return null; }
  const seen = new Set();
  const dedup = items.filter(r => { if (seen.has(r.code)) return false; seen.add(r.code); return true; });
  if (dedup.length === 1) { input.value = dedup[0].code; return dedup[0].code; }
  const a = dedup[0], b = dedup[1];
  if (a && b && a.code !== b.code) { showToast("多个匹配: " + dedup.map(r=>r.code+" "+r.name).join(" / "), "warn"); return null; }
  input.value = a.code;
  return a.code;
}

/* ---------- loader ---------- */
function showLoader(msg) {
  loader.classList.remove("hidden");
  loaderText.textContent = msg || "分析中，预计 2~3 分钟...";
  timerSec = 0;
  elapsed.textContent = "00:00";
  clearInterval(timerInt);
  timerInt = setInterval(() => {
    timerSec++;
    const m = String(Math.floor(timerSec / 60)).padStart(2, "0");
    const s = String(timerSec % 60).padStart(2, "0");
    elapsed.textContent = m + ":" + s;
  }, 1000);
}

function hideLoader() {
  loader.classList.add("hidden");
  clearInterval(timerInt);
}

/* ---------- result visibility ---------- */
function hideResult() {
  document.querySelectorAll(".grid-2, .card:has(#tabs)").forEach(el => el.style.display = "none");
}

function showResult() {
  document.querySelectorAll(".grid-2, .card:has(#tabs)").forEach(el => el.style.display = "");
}

/* ---------- blocking POST ---------- */
async function startLoad(ticker) {
  showLoader("分析中，预计 2~3 分钟...");

  const ac = new AbortController();
  abortC = ac;

  const r = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker }),
    signal: ac.signal,
  });
  abortC = null;

  if (!r.ok) {
    const err = await r.json().catch(() => ({ error: "HTTP " + r.status }));
    throw new Error(err.error || "请求失败");
  }
  const data = await r.json();
  if (data.error) throw new Error(data.error);

  latest = data;
  markDone("decision");
  renderResult(data);
  setBadge("完成", "done");
  statusDot.className = "dot";
  statusText.textContent = "就绪";
  showResult();
  hideLoader();
}

/* ---------- busy state ---------- */
function setBusy(on) {
  submitBtn.disabled = on;
  submitBtn.innerHTML = on
    ? '<span class="spinner"></span> 分析中'
    : '<svg width="14" height="14" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" fill="currentColor"/></svg> 开始分析';
  setBadge(on ? "运行中" : "待命", on ? "running" : "idle");
  statusDot.className = "dot" + (on ? " pulse" : "");
  statusText.textContent = on ? "分析中" : "就绪";
}

function setBadge(text, cls) {
  badge.textContent = text;
  badge.className = "badge " + cls;
}

function resetStages() {
  stages.forEach(el => { el.className = ""; el.classList.remove("done","active"); });
}

function markDone(id) {
  stages.forEach(el => {
    if (el.dataset.stage === id || STAGES.indexOf(el.dataset.stage) < STAGES.indexOf(id)) {
      el.classList.add("done");
      el.classList.remove("active");
    }
  });
}

/* ---------- skeleton ---------- */
function showSkel() {
  $("#rating").style.display = "none";
  $("#ratingSkel").classList.remove("hidden");
  $("#summary").style.display = "none";
  $("#summarySkel").classList.remove("hidden");
  $("#metricsArea").style.display = "none";
  $("#metricsSkel").classList.remove("hidden");
  $("#thesis").style.display = "none";
  $("#thesisSkel").classList.remove("hidden");
  $("#riskWarning").style.display = "none";
  $("#riskSkel").classList.remove("hidden");
}

function hideSkel() {
  $("#rating").style.display = "";
  $("#ratingSkel").classList.add("hidden");
  $("#summary").style.display = "";
  $("#summarySkel").classList.add("hidden");
  $("#metricsArea").style.display = "";
  $("#metricsSkel").classList.add("hidden");
  $("#thesis").style.display = "";
  $("#thesisSkel").classList.add("hidden");
  $("#riskWarning").style.display = "";
  $("#riskSkel").classList.add("hidden");
}

/* ---------- render ---------- */
function renderResult(data) {
  const dec = data.final_decision || {};
  const rt = data.raw_data?.realtime || {};
  const res = data.research_plan || {};
  const tr = data.trade_proposal || {};

  const r = $("#rating");
  r.textContent = (dec.rating_cn || "未生成") + (dec.rating ? " (" + dec.rating + ")" : "");
  r.style.color = ratingColor(dec.rating);
  $("#summary").textContent = dec.executive_summary || "暂无摘要。";

  const meta = (data.ticker || "--") + " " + (data.ticker_name || "");
  const si = data.search_input;
  $("#tickerMeta").textContent = (si && si !== data.ticker) ? si + " → " + meta : meta;

  $("#currentPrice").textContent = fmtVal(rt.current);
  const cp = $("#changePct");
  cp.textContent = fmtPct(rt.change_pct);
  cp.style.color = (rt.change_pct || 0) >= 0 ? "var(--good)" : "var(--bad)";
  $("#targetPrice").textContent = dec.price_target || tr.target_price || "--";
  $("#horizon").textContent = dec.time_horizon || res.time_horizon || "--";
  $("#thesis").textContent = dec.investment_thesis || "暂无内容。";
  $("#riskWarning").textContent = dec.risk_warning || "暂无内容。";
  $("#newsCount").textContent = (data.raw_data?.news?.length || 0) + " 条新闻";

  renderKV("#researchList", [
    ["推荐", res.recommendation],
    ["置信度", res.confidence == null ? "" : Math.round(res.confidence * 100) + "%"],
    ["周期", res.time_horizon],
    ["理由", res.rationale],
    ["关键风险", Array.isArray(res.key_risks) ? res.key_risks.join(" / ") : ""],
  ]);

  renderKV("#tradeList", [
    ["操作", tr.action],
    ["入场区间", tr.entry_price_range],
    ["建议仓位", tr.position_sizing],
    ["止损", tr.stop_loss],
    ["目标位", tr.target_price],
    ["理由", tr.reasoning],
  ]);

  renderReport();
}

function ratingColor(r) {
  return ({ Buy:"var(--good)", Overweight:"var(--good)", Hold:"var(--warn)", Underweight:"var(--bad)", Sell:"var(--bad)" })[r] || "var(--text)";
}

function renderKV(sel, rows) {
  const node = $(sel);
  node.innerHTML = "";
  rows.forEach(([label, value]) => {
    node.append(
      Object.assign(document.createElement("dt"), { textContent: label }),
      Object.assign(document.createElement("dd"), { textContent: value || "--" })
    );
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
    risk: risk.map(i => "【" + i.agent + "】\n" + i.assessment).join("\n\n"),
    logs: latest.logs,
  }[activeTab];
  reportEl.textContent = content || "暂无内容。";
  reportEl.classList.remove("live");
}

/* ---------- tabs ---------- */
tabs.addEventListener("click", e => {
  const b = e.target.closest("button[data-tab]");
  if (!b) return;
  activeTab = b.dataset.tab;
  $$("button", tabs).forEach(el => el.classList.toggle("active", el === b));
  renderReport();
});

/* ---------- copy ---------- */
copyBtn.addEventListener("click", () => {
  if (!latest || latest.error) { showToast("无内容可复制", "warn"); return; }
  const dec = latest.final_decision || {};
  const parts = [
    "=".repeat(36),
    "Trading Agent 分析报告",
    "=".repeat(36), "",
    "股票: " + latest.ticker + " " + (latest.ticker_name || ""),
    "评级: " + (dec.rating_cn || "") + " (" + (dec.rating || "") + ")",
    "摘要: " + (dec.executive_summary || ""), "",
    "当前价: " + fmtVal(latest.raw_data?.realtime?.current),
    "涨跌幅: " + fmtPct(latest.raw_data?.realtime?.change_pct),
    "目标价: " + (dec.price_target || "--"),
    "持有周期: " + (dec.time_horizon || "--"), "",
    "投资论点:", dec.investment_thesis || "", "",
    "风险提示:", dec.risk_warning || "",
  ];
  if (latest.research_plan) {
    const r = latest.research_plan;
    parts.push("", "研究推荐: " + r.recommendation + " (" + Math.round((r.confidence||0)*100) + "%)");
    if (r.rationale) parts.push("理由: " + r.rationale);
  }
  if (latest.trade_proposal) {
    const t = latest.trade_proposal;
    parts.push("", "操作: " + (t.action || ""));
    if (t.entry_price_range) parts.push("入场: " + t.entry_price_range);
    if (t.position_sizing) parts.push("仓位: " + t.position_sizing);
    if (t.stop_loss) parts.push("止损: " + t.stop_loss);
    if (t.target_price) parts.push("目标: " + t.target_price);
  }
  parts.push("", "=".repeat(36));
  navigator.clipboard.writeText(parts.join("\n")).then(
    () => showToast("已复制", "succ"),
    () => showToast("复制失败", "err")
  );
});

/* ---------- toast ---------- */
function showToast(msg, type) {
  toast.className = "toast " + type;
  toast.textContent = msg;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.add("hidden"), 3000);
}

function showErr(msg) {
  setBadge("出错", "err");
  statusDot.className = "dot err";
  statusText.textContent = "出错";
  latest = { error: msg };
  reportEl.textContent = "❌ " + msg;
  showToast(msg, "err");
}

/* ---------- format ---------- */
function fmtVal(v) {
  if (v == null || v === "") return "--";
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(2) : String(v);
}
function fmtPct(v) {
  if (v == null || v === "") return "--";
  const n = Number(v);
  return Number.isFinite(n) ? (n > 0 ? "+" : "") + n.toFixed(2) + "%" : String(v);
}

/* ---------- recent ---------- */
function addRecent(input) {
  let recents = JSON.parse(localStorage.getItem("ta_rc") || "[]");
  recents = [input, ...recents.filter(t => t !== input)].slice(0, 5);
  localStorage.setItem("ta_rc", JSON.stringify(recents));
  renderRecent();
}

function renderRecent() {
  const recents = JSON.parse(localStorage.getItem("ta_rc") || "[]");
  if (!recents.length) { recentContainer.classList.add("hidden"); return; }
  recentContainer.classList.remove("hidden");
  recentList.innerHTML = "";
  recents.forEach(r => {
    const tag = Object.assign(document.createElement("button"), { className:"recent-tag", textContent:r });
    tag.addEventListener("click", () => { input.value = r; form.requestSubmit(); });
    recentList.appendChild(tag);
  });
}
renderRecent();

/* ---------- history ---------- */
historyBtn.addEventListener("click", async () => {
  if (historyBtn.textContent === "展开") {
    historyBtn.textContent = "加载中...";
    historyBtn.disabled = true;
    await loadHistory();
    historyBtn.textContent = "收起";
    historyBtn.disabled = false;
    historyPanel.classList.remove("hidden");
  } else {
    historyPanel.classList.add("hidden");
    historyBtn.textContent = "展开";
  }
});

async function loadHistory() {
  try {
    const r = await fetch("/api/history", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({limit:20}) });
    if (!r.ok) throw Error();
    const d = await r.json();
    const items = d.history || [];
    if (!items.length) { historyPanel.innerHTML = '<div class="hint">暂无记录</div>'; return; }
    historyPanel.innerHTML = "";
    items.forEach(item => {
      const div = document.createElement("div");
      div.className = "history-item";
      div.innerHTML = '<span class="history-item-code">' + item.ticker + '</span><span class="history-item-name">' + (item.ticker_name || "") + '</span><span class="history-item-time">' + (item.created_at ? item.created_at.slice(0,16) : "") + '</span>';
      div.addEventListener("click", () => loadDetail(item.id));
      historyPanel.appendChild(div);
    });
  } catch { historyPanel.innerHTML = '<div class="hint">加载失败</div>'; }
}

async function loadDetail(id) {
  try {
    const r = await fetch("/api/history/" + id, { method:"POST" });
    if (!r.ok) return;
    const d = await r.json();
    if (d.state) {
      renderResult(d.state);
      setBadge("完成", "done");
      statusDot.className = "dot";
      statusText.textContent = "就绪";
      showToast("已加载历史", "succ");
      hideSkel();
      setBusy(false);
      showResult();
    }
  } catch { showToast("加载失败", "err"); }
}

/* ---------- settings ---------- */
const settingsBtn = $("#settingsBtn");
const settingsPanel = $("#settingsPanel");
const sBaseUrl = $("#sBaseUrl");
const sModel = $("#sModel");
const sQuick = $("#sQuick");
const sApiKey = $("#sApiKey");
const saveSettings = $("#saveSettings");
const settingsStatus = $("#settingsStatus");

settingsBtn.addEventListener("click", async () => {
  if (settingsBtn.textContent === "展开") {
    settingsBtn.textContent = "加载中...";
    settingsBtn.disabled = true;
    try {
      const r = await fetch("/api/settings");
      const d = await r.json();
      sBaseUrl.value = d.file_config.base_url || "";
      sModel.value = d.file_config.model || "";
      sQuick.value = d.file_config.quick_model || "";
      sApiKey.value = d.file_config.api_key || "";
      settingsStatus.textContent = "当前: " + d.model + " | " + d.base_url;
    } catch { settingsStatus.textContent = "加载失败"; }
    settingsBtn.textContent = "收起";
    settingsBtn.disabled = false;
    settingsPanel.classList.remove("hidden");
  } else {
    settingsPanel.classList.add("hidden");
    settingsBtn.textContent = "展开";
  }
});

saveSettings.addEventListener("click", async () => {
  const body = {};
  if (sBaseUrl.value.trim()) body.base_url = sBaseUrl.value.trim();
  if (sModel.value.trim()) body.model = sModel.value.trim();
  if (sQuick.value.trim()) body.quick_model = sQuick.value.trim();
  if (sApiKey.value.trim()) body.api_key = sApiKey.value.trim();
  try {
    const r = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    settingsStatus.textContent = d.status === "saved"
      ? "✅ 已保存，正在重启..." : "❌ " + (d.error || "保存失败");
    if (d.status === "saved") {
      // Trigger server restart
      setTimeout(() => location.reload(), 2000);
    }
  } catch (e) {
    settingsStatus.textContent = "❌ " + e.message;
  }
});

/* ---------- init ---------- */
hideResult();
