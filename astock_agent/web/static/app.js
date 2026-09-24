/* A股选股 Agent 前端逻辑（原生 JS，无框架） */
"use strict";

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

let modes = [];
let selMode = null;        // 模式管理页当前选中模式
let caseCache = [];        // 当前模式的案例缓存
let verifiers = {};        // compute -> {desc, params}
let draftState = null;     // {mode_id, draft}
let draftConds = [];       // 草案编辑器中的条件数组（与 DOM 一一对应）

// ---------------- 基础工具 ----------------

async function api(url, opts = {}) {
  const resp = await fetch(url, opts);
  let j = null;
  try { j = await resp.json(); } catch (e) { /* 非 JSON 响应 */ }
  if (!resp.ok) {
    const detail = j && j.detail
      ? (typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail))
      : ("HTTP " + resp.status);
    throw new Error(detail);
  }
  return j;
}

let toastTm = null;
function toast(msg, isErr = false, ms = 3200) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (isErr ? " err" : "");
  clearTimeout(toastTm);
  toastTm = setTimeout(() => { t.className = "toast"; }, ms);
}

function pctClass(p) {
  const v = parseFloat(p);
  if (isNaN(v)) return "flat";
  return v > 0 ? "up" : v < 0 ? "down" : "flat";
}

// ---------------- Tab / 时钟 / 健康 ----------------

function initTabs() {
  document.querySelectorAll("#tabs button").forEach(b => {
    b.addEventListener("click", () => {
      document.querySelectorAll("#tabs button").forEach(x => x.classList.remove("active"));
      document.querySelectorAll(".panel").forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      $("#" + b.dataset.p).classList.add("active");
      if (b.dataset.p === "pn-confirm") fillConfirmSelect();
      if (b.dataset.p === "pn-run") fillRunSelect();
      if (b.dataset.p === "pn-history") loadRuns();
    });
  });
}

function switchTab(p) {
  document.querySelectorAll("#tabs button").forEach(b => {
    if (b.dataset.p === p) b.click();
  });
}

function tick() {
  $("#clock").textContent = new Date().toLocaleString("zh-CN", {hour12: false});
}

async function checkHealth() {
  try {
    const h = await api("/api/health");
    const a = $("#hAst"), l = $("#hLlm");
    a.textContent = "astock: " + (h.astock ? "已连接" : "未启动");
    a.className = "status " + (h.astock ? "ok" : "bad");
    l.textContent = "LLM: " + (h.llm ? "已配置Key" : "未配置Key");
    l.className = "status " + (h.llm ? "ok" : "bad");
  } catch (e) { /* 后端未启动时保持原状 */ }
}

// ---------------- 任务轮询（学习/运行共用） ----------------

function pollJob(jobId, opts) {
  // opts: {wrap, bar, stage, log, onEnd}
  opts.wrap.style.display = "block";
  const timer = setInterval(async () => {
    let job;
    try { job = await api("/api/jobs/" + jobId); } catch (e) { return; }
    opts.bar.style.width = job.progress + "%";
    opts.stage.textContent = job.stage + "（" + job.progress + "%）";
    opts.log.innerHTML = job.logs.slice(-40).map(l => `<div>${esc(l)}</div>`).join("");
    opts.log.scrollTop = opts.log.scrollHeight;
    if (job.status === "done" || job.status === "failed") {
      clearInterval(timer);
      if (job.status === "failed") {
        opts.stage.textContent = "任务失败";
        toast(job.error || "任务失败", true, 8000);
        if (opts.onEnd) opts.onEnd(job, false);
      } else {
        opts.stage.textContent = job.stage;
        if (opts.onEnd) opts.onEnd(job, true);
      }
    }
  }, 800);
}

// ---------------- 模式管理 ----------------

async function loadModes() {
  modes = await api("/api/modes");
  renderModeList();
  fillConfirmSelect();
  fillRunSelect();
}

function renderModeList() {
  const el = $("#modeList");
  if (!modes.length) {
    el.innerHTML = '<div class="empty">还没有模式<br>在上方输入模式名新建</div>';
    return;
  }
  el.innerHTML = modes.map(m => `
    <div class="mode-item ${m.mode_id === selMode ? "sel" : ""}" onclick="selectMode('${esc(m.mode_id)}')">
      <div class="m-name">${esc(m.name)}</div>
      <div class="m-meta">
        <span>案例 ${m.case_count} 个</span>
        ${m.has_rule ? '<span class="badge rule">已有规则</span>'
                     : '<span class="badge none">无规则</span>'}
        ${m.has_draft ? '<span class="badge draft">待确认草案</span>' : ""}
      </div>
    </div>`).join("");
}

async function createMode() {
  const name = $("#newModeName").value.trim();
  if (!name) { toast("请输入模式名", true); return; }
  try {
    const r = await api("/api/modes", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({name}),
    });
    $("#newModeName").value = "";
    toast("模式已创建: " + r.mode_id);
    await loadModes();
    await selectMode(r.mode_id);
  } catch (e) { toast(e.message, true); }
}

async function delMode() {
  if (!selMode) return;
  if (!confirm("确定删除模式「" + selMode + "」？\n其案例文件夹、规则、草案将一并删除，运行记录保留。")) return;
  try {
    await api("/api/modes/" + encodeURIComponent(selMode), {method: "DELETE"});
    selMode = null;
    caseCache = [];
    $("#selModeName").textContent = "未选择模式";
    $("#btnLearn").disabled = true;
    $("#btnDelMode").disabled = true;
    $("#modeStatusHint").textContent = "";
    $("#caseList").innerHTML = '<div class="empty">请先选择模式</div>';
    $("#imgPreview").style.display = "none";
    toast("模式已删除");
    await loadModes();
  } catch (e) { toast(e.message, true); }
}

async function selectMode(id) {
  selMode = id;
  renderModeList();
  const m = modes.find(x => x.mode_id === id);
  $("#selModeName").textContent = m ? m.name : id;
  $("#btnLearn").disabled = false;
  $("#btnDelMode").disabled = false;
  $("#modeStatusHint").textContent = m && m.has_rule
    ? "已有正式规则；「学习规则」会生成新草案并与旧规则对比（增量学习）"
    : "尚未学习出规则，上传案例后点「学习规则」";
  await loadCases();
}

async function loadCases() {
  const el = $("#caseList");
  const d = await api("/api/modes/" + encodeURIComponent(selMode));
  caseCache = d.cases;
  if (!caseCache.length) {
    el.innerHTML = '<div class="empty">该模式还没有案例<br>在上方上传截图 + 说明.md</div>';
    return;
  }
  el.innerHTML = caseCache.map(c => `
    <div class="case-item">
      <div class="case-hd">
        <span class="case-name" onclick="viewCase('${esc(c.case_id)}')">${esc(c.case_id)}</span>
        <span class="hint">${c.image_count} 张截图</span>
        <div class="case-img-tags">
          ${c.images.map(img =>
            `<span class="tag" onclick="viewCaseImg('${esc(c.case_id)}','${esc(img)}')">${esc(img)}</span>`).join("")}
        </div>
        <button class="btn mini del" style="margin-left:auto" onclick="delCase('${esc(c.case_id)}')">删除案例</button>
      </div>
      ${c.description
        ? `<div class="case-desc">${esc(c.description.slice(0, 600))}${c.description.length > 600 ? " …" : ""}</div>`
        : ""}
    </div>`).join("");
}

function _imgUrl(caseId, img) {
  return "/api/modes/" + encodeURIComponent(selMode) + "/cases/"
       + encodeURIComponent(caseId) + "/images/" + encodeURIComponent(img);
}

function viewCase(caseId) {
  const c = caseCache.find(x => x.case_id === caseId);
  if (!c || !c.images.length) { toast("该案例没有截图", true); return; }
  const box = $("#imgPreview");
  box.style.display = "flex";
  box.innerHTML = `<button class="btn mini" onclick="$('#imgPreview').style.display='none'">关闭预览</button>` +
    c.images.map(img =>
      `<img src="${_imgUrl(caseId, img)}" onclick="window.open(this.src)" title="点击新窗口打开大图">`).join("");
}

function viewCaseImg(caseId, img) {
  window.open(_imgUrl(caseId, img));
}

async function delCase(caseId) {
  if (!confirm("确定删除案例「" + caseId + "」？")) return;
  try {
    await api("/api/modes/" + encodeURIComponent(selMode) + "/cases/"
            + encodeURIComponent(caseId), {method: "DELETE"});
    toast("案例已删除");
    await loadModes();
    await loadCases();
  } catch (e) { toast(e.message, true); }
}

// 上传区：点击选择 + 拖拽
function initUpload() {
  const box = $("#dropBox"), input = $("#caseFiles");
  box.querySelector(".up-main").addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    $("#fileHint").textContent = input.files.length
      ? "已选择 " + input.files.length + " 个文件"
      : "未选择文件";
  });
  ["dragover", "dragenter"].forEach(ev =>
    box.addEventListener(ev, e => { e.preventDefault(); box.classList.add("drag"); }));
  ["dragleave", "drop"].forEach(ev =>
    box.addEventListener(ev, e => { e.preventDefault(); box.classList.remove("drag"); }));
  box.addEventListener("drop", e => {
    const files = [...e.dataTransfer.files].filter(f =>
      /\.(png|jpe?g|gif|webp)$/i.test(f.name));
    if (files.length) {
      const dt = new DataTransfer();
      files.forEach(f => dt.items.add(f));
      input.files = dt.files;
      $("#fileHint").textContent = "已选择 " + files.length + " 个文件";
    }
  });
}

async function uploadCase() {
  if (!selMode) { toast("请先在左侧选择模式", true); return; }
  const files = $("#caseFiles").files;
  if (!files.length) { toast("请先选择截图文件（可拖拽到上传区）", true); return; }
  const fd = new FormData();
  fd.append("case_name", $("#caseName").value.trim());
  fd.append("description", $("#caseDesc").value);
  for (const f of files) fd.append("files", f);
  toast("上传中...");
  try {
    const r = await api("/api/modes/" + encodeURIComponent(selMode) + "/cases",
      {method: "POST", body: fd});
    toast("案例已上传: " + r.case_id);
    $("#caseName").value = "";
    $("#caseDesc").value = "";
    $("#caseFiles").value = "";
    $("#fileHint").textContent = "未选择文件";
    await loadModes();
    await loadCases();
  } catch (e) { toast(e.message, true); }
}

async function startLearn() {
  if (!selMode) return;
  try {
    const r = await api("/api/modes/" + encodeURIComponent(selMode) + "/learn",
      {method: "POST"});
    toast("学习任务已启动");
    pollJob(r.job_id, {
      wrap: $("#learnProgress"), bar: $("#learnBar"),
      stage: $("#learnStage"), log: $("#learnLog"),
      onEnd: async (job, ok) => {
        if (ok) {
          toast("学习完成！请到「学习确认」页审查草案", false, 6000);
          await loadModes();
        }
      },
    });
  } catch (e) { toast(e.message, true); }
}

// ---------------- 学习确认（草案编辑器） ----------------

function fillConfirmSelect() {
  const sel = $("#cfMode");
  const cur = sel.value;
  sel.innerHTML = modes.map(m =>
    `<option value="${esc(m.mode_id)}">${esc(m.name)}${m.has_draft ? "（有待确认草案）" : ""}</option>`).join("");
  if (cur && modes.some(m => m.mode_id === cur)) sel.value = cur;
  else if (modes.length) sel.value = modes[0].mode_id;
}

async function loadDraft() {
  const mid = $("#cfMode").value;
  if (!mid) { toast("请先选择模式", true); return; }
  try {
    const draft = await api("/api/modes/" + encodeURIComponent(mid) + "/draft");
    draftState = {mode_id: mid, draft};
    draftConds = draft.rule.conditions.map(c => ({...c, params: {...(c.params || {})}}));
    renderDraftEditor();
  } catch (e) {
    draftState = null;
    $("#cfBody").innerHTML =
      `<div class="empty">${esc(e.message)}<br>
        <button class="btn" style="margin-top:10px" onclick="switchTab('pn-modes')">去模式管理上传案例并学习</button>
      </div>`;
  }
}

function renderDiff(diff) {
  if (!diff) return "";
  if (diff.is_new) {
    return `<div class="diff-summary">
      <span class="d-item added">首次学习：新规则 ${diff.added.length} 条条件</span>
      <span class="hint" style="align-self:center">与已存正式规则对比</span></div>`;
  }
  const parts = [];
  if (diff.added.length) parts.push(`<span class="d-item added">新增 ${diff.added.length} 条</span>`);
  if (diff.removed.length) parts.push(`<span class="d-item removed">删除 ${diff.removed.length} 条</span>`);
  if (diff.modified.length) parts.push(`<span class="d-item modified">修改 ${diff.modified.length} 条</span>`);
  if (diff.unchanged.length) parts.push(`<span class="d-item">不变 ${diff.unchanged.length} 条</span>`);
  const detail = (diff.added.length || diff.removed.length || diff.modified.length) ? `
    <div class="diff-detail" style="display:block">
      ${diff.added.map(c => `<div class="ad">+ 新增：${esc(c.text)}（${esc(c.type)}: ${esc(c.query || c.compute || "")}）</div>`).join("")}
      ${diff.removed.map(c => `<div class="rm">- 删除：${esc(c.text)}（${esc(c.type)}: ${esc(c.query || c.compute || "")}）</div>`).join("")}
      ${diff.modified.map(m => `<div class="md">~ 修改：${esc(m.before.text)} → ${esc(m.after.text)}</div>`).join("")}
    </div>` : "";
  return `<div class="diff-summary">${parts.join("")}
    <span class="hint" style="align-self:center">与已存正式规则的差异（增量学习对比）</span></div>${detail}`;
}

function condCardHtml(c, i, evidence) {
  const isQ = c.type === "query";
  const vfNames = Object.keys(verifiers);
  const vfOptions = vfNames.map(n =>
    `<option value="${n}" ${c.compute === n ? "selected" : ""}>${n}：${esc(verifiers[n].desc)}</option>`).join("");
  const evs = (evidence[c.id] || []).map(e => `<span class="ev-chip">${esc(e)}</span>`).join("");
  return `
  <div class="cond-card" data-idx="${i}">
    <div class="cond-hd">
      <span class="cond-id">${esc(c.id)}</span>
      <span class="cond-type">类型
        <select onchange="condTypeChange(${i}, this.value)">
          <option value="query" ${isQ ? "selected" : ""}>query（东财智能选股查询）</option>
          <option value="verify" ${!isQ ? "selected" : ""}>verify（数据工具逐只验证）</option>
        </select>
      </span>
      <span class="cond-ev">${evs || '<span class="hint">无案例证据</span>'}</span>
      <span class="cond-actions">
        <button class="btn mini" onclick="moveCond(${i},-1)">上移</button>
        <button class="btn mini" onclick="moveCond(${i},1)">下移</button>
        <button class="btn mini del" onclick="delCond(${i})">删除</button>
      </span>
    </div>
    <div class="cond-row">
      <span class="lab">条件描述</span>
      <input type="text" data-f="text" value="${esc(c.text)}" placeholder="一句话描述该条件">
    </div>
    <div class="cond-row" data-qrow ${isQ ? "" : 'style="display:none"'}>
      <span class="lab">查询语句</span>
      <input type="text" data-f="query" value="${esc(c.query || "")}" placeholder="如：MACD金叉 / 主力净流入大于0">
      <span class="vf-desc">自然语言保持简洁，一条查询一个核心条件</span>
    </div>
    <div class="cond-row" data-vrow ${isQ ? 'style="display:none"' : ""}>
      <span class="lab">验证函数</span>
      <select data-f="compute" onchange="computeChange(${i}, this.value)">${vfOptions}</select>
      <span class="lab">参数</span>
      <input type="text" class="json-in" data-f="params" value="${esc(JSON.stringify(c.params || {}))}"
             placeholder='JSON 参数，如 {"n": 20}'>
    </div>
  </div>`;
}

function renderDraftEditor() {
  const {draft} = draftState;
  const rule = draft.rule;
  $("#cfBody").innerHTML = `
  <div class="draft-box">
    <div class="draft-fields">
      <div class="row"><label>模式名称</label>
        <input type="text" id="dName" value="${esc(rule.name)}"></div>
      <div class="row"><label>模式概述</label>
        <input type="text" id="dDesc" value="${esc(rule.description)}"></div>
      <div class="row"><label>组合方式</label>
        <select id="dCombine">
          <option value="intersection" ${rule.combine === "intersection" ? "selected" : ""}>intersection（各条件取交集）</option>
          <option value="union" ${rule.combine === "union" ? "selected" : ""}>union（各条件取并集）</option>
        </select>
        <span class="hint">学习案例数：${rule.case_count || 0}</span></div>
      <div class="row"><label>备注</label>
        <input type="text" id="dNotes" value="${esc(rule.notes)}"></div>
    </div>
  </div>
  ${renderDiff(draft.diff)}
  <h3 class="sec">条件清单（审查、增删改后确认）</h3>
  <div id="condList">${draftConds.map((c, i) => condCardHtml(c, i, draft.evidence || {})).join("")}</div>
  <div class="toolbar" style="margin-top:12px">
    <button class="btn" onclick="addCondition()">添加条件</button>
    <button class="btn" onclick="saveDraft()">保存草案</button>
    <button class="btn primary" onclick="confirmDraft()">确认保存为正式规则</button>
    <button class="btn del" onclick="discardDraft()">丢弃草案</button>
  </div>`;
}

function renderConds() {
  const list = $("#condList");
  if (!list) return;
  list.innerHTML = draftConds.map((c, i) =>
    condCardHtml(c, i, (draftState.draft.evidence || {}))).join("");
}

// 把 DOM 中的文本输入同步回 draftConds（增删改前调用，避免丢失正在编辑的内容）
function syncFromDom() {
  document.querySelectorAll("#condList .cond-card").forEach(card => {
    const idx = +card.dataset.idx;
    const c = draftConds[idx];
    if (!c) return;
    c.text = card.querySelector('[data-f="text"]').value.trim();
    if (c.type === "query") {
      c.query = card.querySelector('[data-f="query"]').value.trim();
    } else {
      c.compute = card.querySelector('[data-f="compute"]').value;
      try {
        c.params = JSON.parse(card.querySelector('[data-f="params"]').value || "{}");
      } catch (e) {
        throw new Error("条件 " + c.id + " 的参数不是合法 JSON");
      }
    }
  });
}

function _nextCondId() {
  let n = 0;
  draftConds.forEach(c => {
    const m = /^c(\d+)$/.exec(c.id);
    if (m) n = Math.max(n, +m[1]);
  });
  return "c" + (n + 1);
}

function _wrapSync(fn) {
  try {
    syncFromDom();
    fn();
    renderConds();
  } catch (e) {
    toast(e.message, true);
  }
}

function addCondition() {
  _wrapSync(() => {
    draftConds.push({id: _nextCondId(), text: "", type: "query", query: ""});
  });
}

function delCond(i) {
  _wrapSync(() => { draftConds.splice(i, 1); });
}

function moveCond(i, dir) {
  _wrapSync(() => {
    const j = i + dir;
    if (j < 0 || j >= draftConds.length) return;
    [draftConds[i], draftConds[j]] = [draftConds[j], draftConds[i]];
  });
}

function condTypeChange(i, type) {
  _wrapSync(() => {
    const c = draftConds[i];
    c.type = type;
    if (type === "query") {
      delete c.compute;
      delete c.params;
      c.query = c.query || "";
    } else {
      c.compute = c.compute || Object.keys(verifiers)[0] || "";
      c.params = c.params || (verifiers[c.compute]
        ? {...verifiers[c.compute].params} : {});
    }
  });
}

function computeChange(i, name) {
  _wrapSync(() => {
    const c = draftConds[i];
    c.compute = name;
    if (verifiers[name]) c.params = {...verifiers[name].params};
  });
}

function collectRule() {
  const rule = {
    mode_id: draftState.mode_id,
    name: $("#dName").value.trim() || draftState.mode_id,
    description: $("#dDesc").value.trim(),
    combine: $("#dCombine").value,
    notes: $("#dNotes").value.trim(),
    case_count: draftState.draft.rule.case_count || 0,
    conditions: draftConds.map(c => {
      const out = {id: c.id, text: c.text, type: c.type};
      if (c.type === "query") out.query = c.query || "";
      else { out.compute = c.compute; out.params = c.params || {}; }
      return out;
    }),
  };
  if (!rule.conditions.length) throw new Error("至少保留一条条件");
  if (rule.conditions.some(c => !c.text)) throw new Error("存在未填写描述的条件");
  if (rule.conditions.some(c => c.type === "query" && !c.query))
    throw new Error("存在 query 条件未填写查询语句");
  if (rule.conditions.some(c => c.type === "verify" && !c.compute))
    throw new Error("存在 verify 条件未选择验证函数");
  return rule;
}

async function saveDraft() {
  try {
    syncFromDom();
    const rule = collectRule();
    const draft = await api("/api/modes/" + encodeURIComponent(draftState.mode_id) + "/draft", {
      method: "PUT",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({rule}),
    });
    draftState.draft = draft;
    toast("草案已保存（尚未成为正式规则）");
  } catch (e) { toast(e.message, true); }
}

async function confirmDraft() {
  try {
    syncFromDom();
    const rule = collectRule();
    if (!confirm("确认将草案保存为正式规则？\n确认后「选股运行」页即可运行该模式。")) return;
    const draft = await api("/api/modes/" + encodeURIComponent(draftState.mode_id) + "/draft", {
      method: "PUT",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({rule}),
    });
    draftState.draft = draft;
    await api("/api/modes/" + encodeURIComponent(draftState.mode_id) + "/confirm",
      {method: "POST"});
    toast("已确认为正式规则！可到「选股运行」页运行", false, 5000);
    draftState = null;
    $("#cfBody").innerHTML = '<div class="empty">规则已确认保存<br>可重新选择模式继续</div>';
    await loadModes();
  } catch (e) { toast(e.message, true); }
}

async function discardDraft() {
  if (!confirm("确定丢弃该草案？重新学习后才能再次生成。")) return;
  try {
    await api("/api/modes/" + encodeURIComponent(draftState.mode_id) + "/draft",
      {method: "DELETE"});
    draftState = null;
    $("#cfBody").innerHTML = '<div class="empty">草案已丢弃<br>可在「模式管理」页重新学习</div>';
    await loadModes();
    toast("草案已丢弃");
  } catch (e) { toast(e.message, true); }
}

// ---------------- 选股运行 ----------------

function fillRunSelect() {
  const sel = $("#runMode");
  const cur = sel.value;
  const runnable = modes.filter(m => m.has_rule);
  if (!runnable.length) {
    sel.innerHTML = '<option value="">（无已确认规则的模式）</option>';
  } else {
    sel.innerHTML = runnable.map(m =>
      `<option value="${esc(m.mode_id)}">${esc(m.name)}</option>`).join("");
    if (cur && runnable.some(m => m.mode_id === cur)) sel.value = cur;
    else sel.value = runnable[0].mode_id;
  }
  $("#btnRun").disabled = !runnable.length;
}

async function startRun() {
  const mid = $("#runMode").value;
  if (!mid) return;
  $("#btnRun").disabled = true;
  $("#runResult").innerHTML = "";
  try {
    const r = await api("/api/modes/" + encodeURIComponent(mid) + "/run",
      {method: "POST"});
    pollJob(r.job_id, {
      wrap: $("#runProgress"), bar: $("#runBar"),
      stage: $("#runStage"), log: $("#runLog"),
      onEnd: async (job, ok) => {
        $("#btnRun").disabled = false;
        if (ok && job.result) {
          await viewRun(job.result.run_id, "#runResult");
          toast("选股完成", false, 4000);
        }
      },
    });
  } catch (e) {
    $("#btnRun").disabled = false;
    toast(e.message, true);
  }
}

function renderCondResults(run) {
  const crs = run.condition_results || [];
  if (!crs.length) return "";
  return `<div class="cr-cards">` + crs.map(c => `
    <div class="cr-card ${c.ok ? "" : "fail"}">
      <div class="nm">${esc(c.text)}</div>
      <div class="pr">${c.ok ? c.total + " 只" : "查询失败"}</div>
      <div class="nm">${c.ok ? "查询命中" : esc((c.error || "").slice(0, 60))}</div>
    </div>`).join("") + `</div>`;
}

function renderStockTable(run) {
  const stocks = run.stocks || [];
  if (!stocks.length) return '<div class="empty">无候选股票</div>';
  const rows = stocks.map(s => `
    <tr>
      <td>${esc(s.code)} ${esc(s.name)}</td>
      <td>${esc(s.price)}</td>
      <td class="${pctClass(s.pct)}">${esc(s.pct)}${s.pct !== "-" ? "%" : ""}</td>
      <td style="text-align:left">
        ${s.matched.map(m => `<span class="tag ok">${esc(m)}</span>`).join("")}
        ${s.failed.map(m => `<span class="tag no">${esc(m)}</span>`).join("")}
        ${s.unverified.map(m => `<span class="tag">${esc(m)}</span>`).join("")}
      </td>
      <td class="note">${esc(s.note)}</td>
    </tr>`).join("");
  return `<div class="tbl-wrap"><table>
    <thead><tr><th>股票</th><th>现价</th><th>涨跌</th><th>命中条件（绿=命中 / 红=未过 / 灰=未验证）</th><th>说明</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

async function viewRun(runId, target = "#runDetail") {
  const run = await api("/api/runs/" + runId);
  const el = $(target);
  if (run.status === "failed") {
    el.innerHTML = `<div class="error-msg">运行失败：${esc(run.error)}</div>`;
    return;
  }
  let html = `<h3 class="sec">运行时间 ${esc(run.time)} · 模式《${esc(run.mode_name)}》 · 命中 ${run.stocks.length} 只</h3>`;
  html += renderCondResults(run);
  if (run.empty_reason) {
    html += `<div class="empty-warn">${esc(run.empty_reason)}</div>`;
  } else {
    html += renderStockTable(run);
  }
  el.innerHTML = html;
}

// ---------------- 历史记录 ----------------

async function loadRuns() {
  const el = $("#runTblWrap");
  try {
    const runs = await api("/api/runs");
    if (!runs.length) {
      el.innerHTML = '<div class="empty">暂无运行记录<br>到「选股运行」页运行一次</div>';
      return;
    }
    el.innerHTML = `<div class="tbl-wrap" style="max-height:420px"><table>
      <thead><tr><th>时间</th><th>模式</th><th>状态</th><th>命中数</th><th></th></tr></thead>
      <tbody>${runs.map(r => `
        <tr onclick="viewRun('${esc(r.run_id)}','#runDetail')" style="cursor:pointer">
          <td>${esc(r.time)}</td>
          <td>${esc(r.mode_name)}</td>
          <td>${r.status === "done"
            ? '<span class="tag ok">完成</span>'
            : '<span class="tag no">失败</span>'}</td>
          <td>${r.stock_count}</td>
          <td><span class="hint">点击查看详情</span></td>
        </tr>`).join("")}</tbody></table></div>`;
    $("#runDetail").innerHTML = "";
  } catch (e) { el.innerHTML = `<div class="error-msg">${esc(e.message)}</div>`; }
}

// ---------------- 初始化 ----------------

async function init() {
  initTabs();
  initUpload();
  tick();
  setInterval(tick, 1000);
  await checkHealth();
  setInterval(checkHealth, 30000);
  try {
    verifiers = await api("/api/verifiers");
    await loadModes();
  } catch (e) {
    toast("后端连接失败: " + e.message, true, 6000);
  }
}

init();
