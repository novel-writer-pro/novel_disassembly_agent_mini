export type PipelineProfile = "manual" | "auto-lite" | "auto-full";

export interface ImportResult {
  novel_id: string;
  manifest_id: string;
  run_id: string | null;
  branch_id: string | null;
  chapter_count?: number;
  processed_chapters?: number;
  next_chapter?: number | null;
  pipeline_profile: string;
  pipeline_state: string;
  existing?: boolean;
  setup_status?: string;
}

export interface RunSnapshot {
  run_id: string;
  branch_id: string;
  branch_name: string;
  pipeline_state: string;
  manifest_chapter_count: number;
  completed_chapters: number;
  failed_jobs: number;
  running_jobs: number;
  next_chapter: number | null;
  allowed_actions: string[];
  setup_status: string;
}

export interface ChapterRow {
  chapter_index: number;
  title: string;
  job_status: string;
  has_artifact: boolean;
  has_retrieval: boolean;
  hook_score?: number | null;
  needs_human_review: boolean;
  summary?: string;
  risk_level?: string | null;
  risk_count?: number;
}

export interface BranchSnapshot {
  branch_id: string;
  pipeline_state: string;
  allowed_actions: string[];
  chapter_rows: ChapterRow[];
  failed_summary: Array<{ chapter_index: number; error: string; failure_class?: string | null; failure_code?: string | null }>;
  risk_summary?: BranchRiskSummary;
}

export interface ChapterBundle {
  chapter_index: number;
  artifact: Record<string, any>;
  facts: Array<{ fact_type: string; label: string; confidence: number; evidence_list?: string[] }>;
  retrieval: Record<string, any>;
  reasoning_graph: Record<string, any>;
  state_summary: Record<string, any>;
  risk_card?: ChapterRiskCard | null;
}

export interface ChapterQaContext {
  chapter_index: number;
  title?: string;
  chapter_summary?: string;
  key_events?: string[];
  state_transition_notes?: string[];
  evidence_backed_resolutions?: string[];
  unresolved_threads?: string[];
  facts?: any[];
  retrieval?: Record<string, any>;
  query_hints?: string[];
  recommended_questions?: string[];
  reasoning_graph?: Record<string, any>;
  state_summary?: Record<string, any>;
}

export interface ChapterSource {
  chapter_index: number;
  raw_heading: string;
  normalized_title: string;
  start_offset: number;
  end_offset: number;
  source_excerpt: string;
}

export interface RecoveryResult {
  branch_id: string;
  accepted_action: string;
  pipeline_state: string;
  message: string;
}

export interface BranchExports {
  branch_bundle: { download_ref: string; content_type: string };
  branch_qa_context: { download_ref: string; content_type: string };
  branch_report: { download_ref: string; content_type: string };
}

export interface GateRiskItem {
  checker_name: string;
  risk_domain: string;
  risk_type: string;
  severity: string;
  confidence: number;
  summary: string;
  supporting_evidence: string[];
  counter_evidence: string[];
  related_entities: string[];
  related_chapters: number[];
  needs_human_review: boolean;
  risk_key: string;
}

export interface ChapterRiskCard {
  branch_id: string;
  chapter_index: number;
  overall_risk_level: string;
  top_risks: GateRiskItem[];
  risk_counts_by_domain: Record<string, number>;
  risk_counts_by_severity: Record<string, number>;
  review_status: string;
  generated_at?: string | null;
  checker_statuses: Record<string, string>;
  coverage_gaps: string[];
}

export interface BranchRiskSummary {
  risk_card_count: number;
  checker_result_count: number;
  high_risk_chapters: number[];
  risk_counts_by_domain: Record<string, number>;
  risk_counts_by_severity: Record<string, number>;
}

export interface WorkbenchState {
  title?: string;
  apiBase: string;
  databaseUrl: string;
  runId: string;
  branchId: string;
  profile: PipelineProfile;
  maxChapters: string;
  lastChapterIndex?: number | null;
  lastChapterIndexByBranch?: Record<string, number | null>;
}

export interface LibraryItem {
  novel_id: string;
  title: string;
  run_id: string;
  branch_id: string;
  branch_name: string;
  pipeline_state: string;
  completed_chapters: number;
  manifest_chapter_count: number;
  next_chapter: number | null;
  failed_jobs?: number;
  running_jobs?: number;
  setup_status?: string;
  updated_at?: string | null;
  priority_score?: number;
  priority_reason?: string;
}


export interface RetrievalHit {
  chapter_index: number;
  title: string;
  summary_text: string;
  score: number;
  keyword_list: string[];
}

export interface BranchAskResult {
  answer: string;
  used_chapters: number[];
  evidence: string[];
  reasoning_paths: string[];
  graph_signals: string[];
  confidence: number;
  insufficient_context: boolean;
  answer_mode?: "normal" | "degraded";
  degraded_reason?: string | null;
}

export interface BranchAskStreamEvent {
  type: "status" | "retrieval" | "delta" | "final" | "error";
  message?: string;
  delta?: string;
  error?: string;
  hits?: RetrievalHit[];
  result?: BranchAskResult;
}

export interface RuntimeHealth {
  cache_root: string;
  legacy_root: string;
  cache_upload_files: number;
  cache_export_files: number;
  legacy_upload_files: number;
  legacy_export_files: number;
  missing_from_cache: number;
  migrated_this_run: number;
}

export interface ProviderHealth {
  provider_name: string;
  model_name: string;
  last_status: "unknown" | "ok" | "degraded" | string;
  degraded_events: number;
  success_events: number;
  last_error?: string | null;
  last_updated_at?: string | null;
}

export interface PipelineRunSnapshot {
  id: string;
  run_id: string;
  branch_id: string;
  status: "pending" | "running" | "paused" | "completed" | "failed" | "cancelled" | string;
  target_from_chapter: number | null;
  target_to_chapter: number | null;
  concurrency: number;
  provider_profile?: string | null;
  summary_json: Record<string, any>;
  started_at?: string | null;
  finished_at?: string | null;
  paused_at?: string | null;
  cancelled_at?: string | null;
}

export interface JobEventItem {
  id: string;
  run_id: string;
  branch_id: string;
  chapter_index: number;
  event_type: string;
  stage?: string | null;
  level: "info" | "warning" | "error" | string;
  message: string;
  payload_json: Record<string, any>;
  created_at: string;
}

export interface ChapterJobRow {
  chapter_index: number;
  title: string;
  status: string;
  current_stage?: string | null;
  progress_percent: number;
  attempts: number;
  heartbeat_at?: string | null;
  failure_class?: string | null;
  failure_code?: string | null;
  last_error?: string | null;
  has_artifact: boolean;
}
