const importResult = document.getElementById("import-result");
const runSnapshot = document.getElementById("run-snapshot");
const branchSnapshot = document.getElementById("branch-snapshot");
const chapterBundle = document.getElementById("chapter-bundle");
const chapterQaContext = document.getElementById("chapter-qa-context");
const chapterDetailCards = document.getElementById("chapter-detail-cards");
const qaDetailCards = document.getElementById("qa-detail-cards");
const themeDetailCards = document.getElementById("theme-detail-cards");
const sourceMeta = document.getElementById("source-meta");
const chapterSource = document.getElementById("chapter-source");
const chapterList = document.getElementById("chapter-list");
const profileSelect = document.getElementById("profile-select");
const button = document.getElementById("simulate-import");
const realImportButton = document.getElementById("real-import");
const loadLiveButton = document.getElementById("load-live");
const startManualButton = document.getElementById("start-manual");
const apiBaseInput = document.getElementById("api-base");
const runIdInput = document.getElementById("run-id");
const branchIdInput = document.getElementById("branch-id");
const databaseUrlInput = document.getElementById("database-url");
const novelFileInput = document.getElementById("novel-file");
const novelTitleInput = document.getElementById("novel-title");
const maxChaptersInput = document.getElementById("max-chapters");
const recoveryResult = document.getElementById("recovery-result");
const retryFailedButton = document.getElementById("retry-failed");
const clearRunningButton = document.getElementById("clear-running");
const repairBranchButton = document.getElementById("repair-branch");
const loadExportsButton = document.getElementById("load-exports");
const exportList = document.getElementById("export-list");
const overviewState = document.getElementById("overview-state");
const overviewCompleted = document.getElementById("overview-completed");
const overviewNext = document.getElementById("overview-next");
const overviewFailed = document.getElementById("overview-failed");
const overviewActions = document.getElementById("overview-actions");
let activeChapterIndex = null;

const exampleImportResponses = {
  manual: {
    novel_id: "novel-001",
    manifest_id: "manifest-001",
    run_id: "run-001",
    branch_id: "branch-001",
    pipeline_profile: "manual",
    pipeline_state: "ready",
    existing: false
  },
  "auto-lite": {
    novel_id: "novel-001",
    manifest_id: "manifest-001",
    run_id: "run-001",
    branch_id: "branch-001",
    pipeline_profile: "auto-lite",
    pipeline_state: "auto_running",
    existing: false
  },
  "auto-full": {
    novel_id: "novel-001",
    manifest_id: "manifest-001",
    run_id: "run-001",
    branch_id: "branch-001",
    pipeline_profile: "auto-full",
    pipeline_state: "auto_running",
    existing: false
  }
};

function render(payload) {
  importResult.textContent = JSON.stringify(payload.import_result, null, 2);
  runSnapshot.textContent = JSON.stringify(payload.run_snapshot, null, 2);
  branchSnapshot.textContent = JSON.stringify(payload.branch_snapshot, null, 2);
  renderOverview(payload.run_snapshot, payload.branch_snapshot);
  renderChapterButtons(payload.branch_snapshot.chapter_rows || []);
}

async function loadFromBackend(profile) {
  const base = apiBaseInput.value.trim().replace(/\/$/, "");
  const url = `${base}/api/mock/import?profile=${encodeURIComponent(profile)}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`backend returned ${response.status}`);
  }
  return response.json();
}

async function fetchJson(path, params = {}) {
  const base = apiBaseInput.value.trim().replace(/\/$/, "");
  const search = new URLSearchParams(params);
  const response = await fetch(`${base}${path}?${search.toString()}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `backend returned ${response.status}`);
  }
  return response.json();
}

async function postForm(path, formData) {
  const base = apiBaseInput.value.trim().replace(/\/$/, "");
  const response = await fetch(`${base}${path}`, {
    method: "POST",
    body: formData
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `backend returned ${response.status}`);
  }
  return payload;
}

function renderChapterButtons(rows) {
  chapterList.innerHTML = "";
  rows.forEach((row) => {
    const button = document.createElement("button");
    button.type = "button";
    const reviewChip = row.needs_human_review
      ? `<span class="mini-chip warn">review</span>`
      : "";
    const jobClass = row.job_status === "failed" ? "danger" : row.has_artifact ? "ok" : "";
    const hook =
      row.hook_score !== null && row.hook_score !== undefined
        ? `<span class="mini-chip">hook ${row.hook_score}</span>`
        : "";
    button.innerHTML = `
      <span class="chapter-label">第${row.chapter_index}章 ${row.title || ""}</span>
      <span class="chapter-meta">
        <span class="mini-chip ${jobClass}">${row.job_status}</span>
        ${hook}
        ${reviewChip}
      </span>
    `;
    button.className = activeChapterIndex === row.chapter_index ? "active" : "";
    button.addEventListener("click", () => loadChapterDetails(row.chapter_index));
    chapterList.appendChild(button);
  });
}

async function loadChapterDetails(chapterIndex) {
  activeChapterIndex = chapterIndex;
  const branchId = branchIdInput.value.trim();
  const databaseUrl = databaseUrlInput.value.trim();
  const query = {
    branch_id: branchId,
    chapter_index: String(chapterIndex)
  };
  if (databaseUrl) {
    query.database_url = databaseUrl;
  }
  const [bundle, qa, source] = await Promise.all([
    fetchJson("/api/chapter-bundle", query),
    fetchJson("/api/chapter-qa-context", query),
    fetchJson("/api/chapter-source", query)
  ]);
  renderChapterButtons(
    JSON.parse(branchSnapshot.textContent || "{}").chapter_rows || []
  );
  chapterBundle.textContent = JSON.stringify(bundle, null, 2);
  chapterQaContext.textContent = JSON.stringify(qa, null, 2);
  renderChapterDetails(bundle, qa, source);
}

function renderList(items) {
  if (!items || !items.length) {
    return "<p>暂无</p>";
  }
  return `<ul>${items.map((item) => `<li>${item}</li>`).join("")}</ul>`;
}

function makeChapterLink(text) {
  return String(text).replace(/第(\d+)章/g, (_, index) => {
    return `<a href="#" data-jump-chapter="${index}">第${index}章</a>`;
  });
}

function renderLinkedList(items) {
  if (!items || !items.length) {
    return "<p>暂无</p>";
  }
  return `<ul>${items.map((item) => `<li>${makeChapterLink(item)}</li>`).join("")}</ul>`;
}

function renderPills(items) {
  if (!items || !items.length) {
    return "<p>暂无</p>";
  }
  return `<div class="pill-list">${items.map((item) => `<span class="pill">${item}</span>`).join("")}</div>`;
}

function renderOverview(runData, branchData) {
  overviewState.textContent = runData.pipeline_state || "未知";
  overviewCompleted.textContent = String(runData.completed_chapters ?? "-");
  overviewNext.textContent = runData.next_chapter ?? "已完成";
  overviewFailed.textContent = String(runData.failed_jobs ?? 0);
  overviewActions.textContent = (branchData.allowed_actions || []).join(" / ") || "-";
}

function toSummaryLines(stateSummary) {
  return Object.entries(stateSummary || {}).flatMap(([key, value]) =>
    Array.isArray(value) ? value.map((item) => `${key}: ${item}`) : [`${key}: ${value}`]
  );
}

function renderChapterDetails(bundle, qa, source) {
  const artifact = bundle.artifact || {};
  const stateSummary = bundle.state_summary || {};
  const qaReasoning =
    (qa.reasoning_graph && qa.reasoning_graph.reasoning_paths) || [];
  const unresolvedThreads = qa.unresolved_threads || [];
  const transitionNotes = qa.state_transition_notes || [];
  const recommendedQuestions = qa.recommended_questions || [];
  const resolutions = qa.evidence_backed_resolutions || artifact.evidence_backed_resolutions || [];
  const keyFacts = (bundle.facts || []).map((item) => `${item.fact_type}: ${item.label}`);
  const graphOverview = bundle.reasoning_graph || {};
  const confidenceBadges = [
    artifact.needs_human_review ? ["需要人工复核", "warn"] : null,
    artifact.hook_score !== undefined ? [`hook score: ${artifact.hook_score}`, "info"] : null,
    bundle.facts && bundle.facts.length ? [`facts: ${bundle.facts.length}`, "ok"] : null,
    unresolvedThreads.length ? [`未解决: ${unresolvedThreads.length}`, "danger"] : null
  ].filter(Boolean);

  chapterDetailCards.innerHTML = `
    <section class="detail-card">
      <h4>${artifact.normalized_title || `第${bundle.chapter_index}章`}</h4>
      <p>${artifact.chapter_summary || "暂无章节摘要"}</p>
    </section>
    <section class="detail-card">
      <h4>状态标签</h4>
      <div class="status-banner">
        ${confidenceBadges.map(([label, klass]) => `<span class="status-chip ${klass}">${label}</span>`).join("")}
      </div>
    </section>
    <div class="detail-grid">
      <section class="detail-card">
        <h4>关键人物</h4>
        ${renderPills(artifact.key_entities || [])}
      </section>
      <section class="detail-card">
        <h4>关键事件</h4>
        ${renderLinkedList(artifact.key_events || [])}
      </section>
      <section class="detail-card">
        <h4>Continuity / 衔接</h4>
        ${renderLinkedList(artifact.continuity_notes || [])}
      </section>
      <section class="detail-card">
        <h4>状态摘要</h4>
        ${renderLinkedList(toSummaryLines(stateSummary))}
      </section>
      <section class="detail-card">
        <h4>已解决内容</h4>
        ${renderLinkedList(resolutions)}
      </section>
    </div>
  `;

  qaDetailCards.innerHTML = `
    <div class="detail-grid">
      <section class="detail-card">
        <h4>推荐问题</h4>
        ${renderLinkedList(recommendedQuestions)}
      </section>
      <section class="detail-card">
        <h4>State Transition Notes</h4>
        ${renderLinkedList(transitionNotes)}
      </section>
      <section class="detail-card">
        <h4>Unresolved Threads</h4>
        ${renderLinkedList(unresolvedThreads)}
      </section>
      <section class="detail-card">
        <h4>Reasoning Paths</h4>
        ${renderLinkedList(qaReasoning)}
      </section>
    </div>
  `;

  themeDetailCards.innerHTML = `
    <div class="detail-grid-3">
      <section class="detail-card">
        <h4>人物线</h4>
        ${renderPills(artifact.key_entities || [])}
      </section>
      <section class="detail-card">
        <h4>冲突线</h4>
        ${renderLinkedList(
          toSummaryLines(stateSummary).filter((line) =>
            line.includes("conflict") || line.includes("冲突")
          )
        )}
      </section>
      <section class="detail-card">
        <h4>伏笔线</h4>
        ${renderLinkedList(
          toSummaryLines(stateSummary).filter((line) =>
            line.includes("foreshadow") || line.includes("伏笔")
          )
        )}
      </section>
      <section class="detail-card">
        <h4>世界规则</h4>
        ${renderLinkedList(
          toSummaryLines(stateSummary).filter((line) =>
            line.includes("world") || line.includes("规则")
          )
        )}
      </section>
      <section class="detail-card">
        <h4>事实层</h4>
        ${renderLinkedList(keyFacts)}
      </section>
      <section class="detail-card">
        <h4>图谱概览</h4>
        ${renderList([
          `nodes: ${(graphOverview.overview && graphOverview.overview.node_count) || 0}`,
          `edges: ${(graphOverview.overview && graphOverview.overview.edge_count) || 0}`
        ])}
      </section>
    </div>
  `;

  sourceMeta.innerHTML = `
    <section class="detail-card">
      <h4>${source.normalized_title || `第${source.chapter_index}章`}</h4>
      ${renderList([
        `raw heading: ${source.raw_heading || "无"}`,
        `offset: ${source.start_offset} - ${source.end_offset}`
      ])}
    </section>
  `;
  chapterSource.innerHTML = highlightSourceExcerpt(
    source.source_excerpt || "暂无原始正文",
    artifact,
  );
  bindJumpLinks();
  flashCurrentChapterButton();
}

function bindJumpLinks() {
  document.querySelectorAll("[data-jump-chapter]").forEach((node) => {
    node.addEventListener("click", (event) => {
      event.preventDefault();
      const chapterIndex = Number(node.getAttribute("data-jump-chapter"));
      if (chapterIndex) {
        loadChapterDetails(chapterIndex);
      }
    });
  });
}

function flashCurrentChapterButton() {
  const active = chapterList.querySelector("button.active");
  if (!active) {
    return;
  }
  active.classList.remove("flash-focus");
  void active.offsetWidth;
  active.classList.add("flash-focus");
  active.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function highlightWords(text, words, cssClass) {
  let result = text;
  (words || [])
    .filter(Boolean)
    .sort((a, b) => String(b).length - String(a).length)
    .forEach((word) => {
      const safe = String(word).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      result = result.replace(
        new RegExp(safe, "g"),
        `<span class="source-highlight ${cssClass}">${word}</span>`
      );
    });
  return result;
}

function highlightSourceExcerpt(text, artifact) {
  let html = String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  html = highlightWords(html, artifact.key_entities || [], "entity");
  html = highlightWords(html, artifact.key_events || [], "event");
  html = highlightWords(html, artifact.continuity_notes || [], "continuity");
  return html;
}

function syncIds(importPayload) {
  if (!importPayload) {
    return;
  }
  if (importPayload.run_id) {
    runIdInput.value = importPayload.run_id;
  }
  if (importPayload.branch_id) {
    branchIdInput.value = importPayload.branch_id;
  }
}

loadLiveButton.addEventListener("click", async () => {
  const runId = runIdInput.value.trim();
  const branchId = branchIdInput.value.trim();
  const databaseUrl = databaseUrlInput.value.trim();
  const query = { run_id: runId, branch_id: branchId };
  if (databaseUrl) {
    query.database_url = databaseUrl;
  }
  try {
    const [runData, branchData] = await Promise.all([
      fetchJson("/api/run-snapshot", query),
      fetchJson("/api/branch-snapshot", query)
    ]);
    runSnapshot.textContent = JSON.stringify(runData, null, 2);
    branchSnapshot.textContent = JSON.stringify(branchData, null, 2);
    renderOverview(runData, branchData);
    renderChapterButtons(branchData.chapter_rows || []);
    importResult.textContent = "[live data loaded from backend]";
  } catch (error) {
    importResult.textContent = `[load-live failed] ${error.message}`;
  }
});

startManualButton.addEventListener("click", async () => {
  const formData = new FormData();
  formData.set("run_id", runIdInput.value.trim());
  formData.set("branch_id", branchIdInput.value.trim());
  formData.set("pipeline_profile", profileSelect.value);
  if (databaseUrlInput.value.trim()) {
    formData.set("database_url", databaseUrlInput.value.trim());
  }
  if (maxChaptersInput.value.trim()) {
    formData.set("max_chapters", maxChaptersInput.value.trim());
  }
  try {
    const payload = await postForm("/api/start", formData);
    importResult.textContent = JSON.stringify(payload, null, 2);
    await loadLiveButton.click();
  } catch (error) {
    importResult.textContent = `[start-manual failed] ${error.message}`;
  }
});

realImportButton.addEventListener("click", async () => {
  const file = novelFileInput.files[0];
  if (!file) {
    importResult.textContent = "[import failed] 请先选择小说文件";
    return;
  }
  const formData = new FormData();
  formData.set("file", file);
  formData.set("title", novelTitleInput.value.trim());
  formData.set("pipeline_profile", profileSelect.value);
  if (databaseUrlInput.value.trim()) {
    formData.set("database_url", databaseUrlInput.value.trim());
  }
  if (maxChaptersInput.value.trim()) {
    formData.set("max_chapters", maxChaptersInput.value.trim());
  }
  try {
    const payload = await postForm("/api/import", formData);
    render(payload);
    syncIds(payload.import_result);
  } catch (error) {
    importResult.textContent = `[real-import failed] ${error.message}`;
  }
});

async function runRecovery(action) {
  const formData = new FormData();
  formData.set("run_id", runIdInput.value.trim());
  formData.set("branch_id", branchIdInput.value.trim());
  formData.set("action", action);
  if (databaseUrlInput.value.trim()) {
    formData.set("database_url", databaseUrlInput.value.trim());
  }
  try {
    const payload = await postForm("/api/recovery", formData);
    recoveryResult.textContent = JSON.stringify(payload, null, 2);
    await loadLiveButton.click();
  } catch (error) {
    recoveryResult.textContent = `[recovery failed] ${error.message}`;
  }
}

retryFailedButton.addEventListener("click", () => runRecovery("retry-failed"));
clearRunningButton.addEventListener("click", () => runRecovery("clear-running"));
repairBranchButton.addEventListener("click", () => runRecovery("repair"));

loadExportsButton.addEventListener("click", async () => {
  const runId = runIdInput.value.trim();
  const branchId = branchIdInput.value.trim();
  const databaseUrl = databaseUrlInput.value.trim();
  const query = { run_id: runId, branch_id: branchId };
  if (databaseUrl) {
    query.database_url = databaseUrl;
  }
  try {
    const payload = await fetchJson("/api/branch-exports", query);
    exportList.innerHTML = `
      <div class="export-item">
        <strong>branch-bundle</strong>
        <a href="${apiBaseInput.value.trim().replace(/\/$/, "")}${payload.branch_bundle.download_ref}" target="_blank">下载</a>
      </div>
      <div class="export-item">
        <strong>branch-qa-context</strong>
        <a href="${apiBaseInput.value.trim().replace(/\/$/, "")}${payload.branch_qa_context.download_ref}" target="_blank">下载</a>
      </div>
      <div class="export-item">
        <strong>branch-report</strong>
        <a href="${apiBaseInput.value.trim().replace(/\/$/, "")}${payload.branch_report.download_ref}" target="_blank">下载</a>
      </div>
    `;
  } catch (error) {
    exportList.innerHTML = `<div class="export-item"><strong>导出失败</strong><span>${error.message}</span></div>`;
  }
});

button.addEventListener("click", async () => {
  const profile = profileSelect.value;
  try {
    const payload = await loadFromBackend(profile);
    render(payload);
    syncIds(payload.import_result);
  } catch (error) {
    render({
      import_result: exampleImportResponses[profile],
      run_snapshot: {
        run_id: "run-001",
        branch_id: "branch-001",
        branch_name: "main",
        pipeline_state: profile === "manual" ? "ready" : "auto_running",
        manifest_chapter_count: 120,
        completed_chapters: profile === "manual" ? 0 : 3,
        failed_jobs: 0,
        running_jobs: profile === "manual" ? 0 : 1,
        next_chapter: profile === "manual" ? 1 : 4,
        allowed_actions: profile === "manual" ? ["start", "refresh"] : ["refresh"],
        setup_status: "ok"
      },
      branch_snapshot: {
        branch_id: "branch-001",
        pipeline_state: profile === "manual" ? "ready" : "auto_running",
        allowed_actions: profile === "manual" ? ["start", "refresh", "export-basic"] : ["refresh"],
        chapter_rows: [
          {
            chapter_index: 1,
            title: "第1章",
            job_status: "validated",
            has_artifact: true,
            has_retrieval: true,
            hook_score: 0.82,
            needs_human_review: false
          }
        ],
        failed_summary: []
      }
    });
    importResult.textContent += `\n\n[backend unavailable, fallback to local mock: ${error.message}]`;
  }
});
