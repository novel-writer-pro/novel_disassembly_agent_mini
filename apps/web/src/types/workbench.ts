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
}

export interface BranchSnapshot {
  branch_id: string;
  pipeline_state: string;
  allowed_actions: string[];
  chapter_rows: ChapterRow[];
  failed_summary: Array<{ chapter_index: number; error: string }>;
}

export interface ChapterBundle {
  chapter_index: number;
  artifact: Record<string, any>;
  facts: Array<{ fact_type: string; label: string; confidence: number; evidence_list?: string[] }>;
  retrieval: Record<string, any>;
  reasoning_graph: Record<string, any>;
  state_summary: Record<string, any>;
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

export interface WorkbenchState {
  title?: string;
  apiBase: string;
  databaseUrl: string;
  runId: string;
  branchId: string;
  profile: PipelineProfile;
  maxChapters: string;
  lastChapterIndex?: number | null;
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
}
