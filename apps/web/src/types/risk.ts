export interface ReviewCluster {
  cluster_key: string;
  severity: string;
  status: string;
  signal_count: number;
  representative_text: string;
  chapter_indices: number[];
}

export interface ReviewClusterSummary {
  total_clusters: number;
  severity_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  risk_level: string;
}

export interface RiskSignal {
  id: string;
  signal_type: string;
  raw_text: string;
  canonical_label: string;
  canonical_group: string;
  confidence: number;
  status: string;
}

export interface RiskAuditResult {
  branch_id: string;
  chapter_index: number;
  overall_risk_level: string;
  checker_results: Record<string, any>;
}

export interface ChapterBundle {
  branch_id: string;
  chapter_index: number;
  title: string;
  characters: Array<{ label: string; role: string }>;
  events: Array<{ label: string; chapter_index: number }>;
  threads: Array<{ label: string; status: string }>;
  risk_signals: Array<{ type: string; text: string; severity: string }>;
}

export interface ChapterSource {
  branch_id: string;
  chapter_index: number;
  title: string;
  text: string;
  char_count: number;
}

export interface SearchHit {
  chunk_text: string;
  chapter_index: number;
  score: number;
}
