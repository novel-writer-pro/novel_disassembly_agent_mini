export interface LoomStatus {
  branch_id: string;
  total_facts: number;
  active_facts: number;
  total_graph_nodes: number;
  contradiction_nodes: number;
  evolution_nodes: number;
  loom_memory_mode: string;
  tension: Record<string, any> | null;
  style: Record<string, any> | null;
  reader_sim: Record<string, any> | null;
  long_book_health: Record<string, any> | null;
}

export interface LoomSignals {
  tension?: Record<string, any>;
  style?: Record<string, any>;
  rhythm?: Record<string, any>;
  character?: Record<string, any>;
  reader_sim?: Record<string, any>;
  thread_activation?: Record<string, any>;
  reference_fidelity?: Record<string, any>;
  dialogue?: Record<string, any>;
  chapter_quality?: Record<string, any>;
}

export interface LoomAssembleResult {
  loom_version: string;
  assembled_at_chapter: number;
  working_memory: {
    active_characters: Array<{ label: string; importance_score: number; chapter_last_seen: number }>;
    active_threads: Array<{ label: string; node_type: string; importance_score: number }>;
    recent_summary: string;
  };
  episodic_anchors: Array<{ label: string; fact_type: string; effective_score: number }>;
  semantic_snapshot: {
    character_count: number;
    active_rules: string[];
    key_relationships: string[];
  };
}

export interface ReferenceEvalResult {
  branch_id: string;
  chapter_index: number;
  overall_fidelity: number;
  confidence: number;
  evaluation_method: string;
  suggestion: string;
  dimensions: Record<string, { score: number; reason: string }>;
}

export interface WriterImitateResult {
  source_chapter_index: number;
  target_goal: string;
  final_verdict: string;
  stop_reason: string;
  final_draft: {
    draft_title: string;
    draft_text: string;
  };
  chapter_quality_signal: Record<string, any>;
  dialogue_signal: Record<string, any>;
  rounds_count: number;
  action_queue_count: number;
}

export interface QualityHealth {
  branch_id: string;
  as_of_chapter: number;
  health_score: number;
  alert_level: string;
  quality_trend: string;
  recent_quality_scores: number[];
  suggestion: string;
}

export interface QualityTrend {
  branch_id: string;
  as_of_chapter: number;
  health_score: number;
  quality_trend: string;
  recent_quality_scores: number[];
  is_declining: boolean;
}

export interface PairsStats {
  total_pairs: number;
  target: number;
  progress_pct: number;
  avg_quality_score: number | null;
  unique_chapters: number;
  chapter_range: string;
  preference_distribution: Record<string, number>;
  evaluation_method_distribution: Record<string, number>;
}
