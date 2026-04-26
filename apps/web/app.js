const importResult = document.getElementById("import-result");
const runSnapshot = document.getElementById("run-snapshot");
const branchSnapshot = document.getElementById("branch-snapshot");
const profileSelect = document.getElementById("profile-select");
const button = document.getElementById("simulate-import");
const apiBaseInput = document.getElementById("api-base");

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

button.addEventListener("click", async () => {
  const profile = profileSelect.value;
  try {
    const payload = await loadFromBackend(profile);
    render(payload);
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
