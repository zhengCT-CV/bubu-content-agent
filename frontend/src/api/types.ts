export type ProjectStatus = "draft" | "running" | "waiting_approval" | "ready_to_publish" | "published" | "waiting_metrics" | "completed" | "failed";

export interface Project {
  id: string;
  name: string;
  inspiration: string;
  target_audience: string;
  status: ProjectStatus;
  active_thread_id: string | null;
  publication: Publication | null;
  created_at: string;
  updated_at: string;
}

export interface Publication {
  title: string;
  published_at: string;
  article_id?: string | null;
  article_url?: string | null;
}

export interface Evidence {
  id: string;
  source_type: string;
  title: string;
  source_path: string;
  excerpt: string;
  score: number;
  retrieval_mode: string;
}

export interface TopicCandidate {
  id: string;
  title: string;
  core_conflict: string;
  narrative_mechanism: string;
  audience_value: string;
  hook: string;
  predicted_strength: number;
  duplicate_risk: number;
  evidence_ids: string[];
}

export interface StoryboardPanel {
  index: number;
  purpose: string;
  scene: string;
  action: string;
  emotion: string;
  dialogue: string;
  dialogue_items?: DialogueItem[];
  camera: string;
  time_of_day: string;
  props: string[];
}

export interface DialogueItem {
  kind: "speech" | "narration" | "inner_thought";
  speaker?: "一二" | "布布" | "Yier" | "Bubu" | null;
  exact_text: string;
}

export interface TimelineItem {
  panel_index: number;
  time_of_day: string;
  lighting?: string;
}

export interface VisualHandoffCard {
  time_anchor: string;
  environment_baseline: string;
  fixed_props: string[];
  time_object_strategy: string;
  timeline: TimelineItem[];
  emotional_peak_panel?: number | null;
  comedy_peak_panel?: number | null;
  narrative_mechanism: string;
  cover_brief: string;
  inferred_notes: string[];
  conflicts: string[];
}

export interface Storyboard {
  title: string;
  summary: string;
  interaction_question: string;
  characters: Array<{ name: string; identity: string; visual_anchor: string }>;
  cover_brief: string;
  panels: StoryboardPanel[];
  ending: string;
  panel_aspect_ratio?: "4:3" | "1:1";
  handoff_card?: VisualHandoffCard | null;
}

export interface PanelPrompt {
  panel_index: number;
  description_zh?: string;
  time_lighting?: string;
  camera?: string;
  subject_ratio?: string;
  core_action?: string;
  comic_symbols?: string[];
  dialogue_items?: DialogueItem[];
  background_objects?: string[];
  aspect_ratio?: "4:3" | "1:1";
  prompt_en: string;
  negative_prompt_en: string;
  continuity_notes: string;
}

export interface VisualPrompts {
  style_prefix: string;
  character_bible: string;
  core_props?: string[];
  allowed_background_objects?: string[];
  global_space?: {
    environment_en: string;
    main_palette: string;
    costumes: string;
    prop_consistency: string;
  };
  reference_reminders?: string[];
  timeline_check?: {
    items: TimelineItem[];
    monotonic: boolean;
    time_object_strategy: string;
    notes: string[];
  };
  cover_type?: string;
  cover_background_mode?: string;
  cover_description_zh?: {
    composition_focus: string;
    character_action: string;
    emotional_hook: string;
    key_prop: string;
    storyboard_relation: string;
    crop_safety: string;
  };
  cover_crop_safety?: string;
  cover_prompt_en: string;
  cover_negative_prompt_en: string;
  panels: PanelPrompt[];
}

export interface ReviewIssue {
  code?: string;
  severity?: "info" | "warning" | "blocking";
  message: string;
  suggestion?: string;
  source?: "llm" | "deterministic";
}

export interface ReviewSummary {
  passed: boolean;
  score: number;
  issues: ReviewIssue[];
  rewrite_instruction?: string;
}

export interface RunState {
  values: {
    project_id: string;
    thread_id: string;
    stage: string;
    evidence?: Evidence[];
    retrieval_degraded?: boolean;
    topic_candidates?: TopicCandidate[];
    selected_topic?: TopicCandidate;
    storyboard?: Storyboard;
    storyboard_review?: ReviewSummary;
    visual_prompts?: VisualPrompts;
    prompt_review?: ReviewSummary;
    prediction?: Record<string, unknown>;
    retro?: { verdict: string; knowledge_proposals: Array<{ target: string; heading: string; markdown: string }> };
    metrics?: Metrics[];
    skill_versions?: Record<string, { version: string; prompt_hash: string }>;
  };
  next: string[];
  checkpoint_id: string;
  interrupts: Array<{ kind: string; message: string; target_hours?: number }>;
}

export interface Metrics {
  article_id: string;
  captured_at: string;
  hours_since_publish: number;
  reads: number;
  shares: number;
  likes: number;
  favorites: number;
  new_followers: number;
}

export interface DataCenterArticle {
  article_id: string;
  title: string;
  published_at: string | null;
  url: string;
  status: string;
  reads: number;
  shares: number;
  likes: number;
  favorites: number;
  new_followers: number;
  captured_at: string | null;
  hours_since_publish: number;
  share_rate: number;
  like_rate: number;
  has_details: boolean;
}

export interface DataCenterOverview {
  source: {
    state: "fresh" | "stale" | "updating";
    cached: boolean;
    warning: string | null;
    file_name: string;
    file_modified_at: string;
    last_captured_at: string | null;
    data_version: string;
  };
  summary: {
    tracked_articles: number;
    total_reads: number;
    median_reads: number;
    tracking_articles: number;
    completed_articles: number;
    sample_count: number;
    milestone_count: number;
    run_count: number;
    collector_success_rate: number;
    latest_run_samples: number;
  };
  historical_baseline: {
    article_count: number;
    total_reads: number;
    median_reads: number;
    average_completion_rate: number;
    date_from: string;
    date_to: string;
  } | null;
  daily_performance: Array<{ date: string; articles: number; reads: number; shares: number; likes: number }>;
  articles: DataCenterArticle[];
}

export interface DataCenterArticleDetail {
  article: DataCenterArticle;
  curve: Array<{
    captured_at: string | null;
    hours_since_publish: number;
    reads: number;
    shares: number | null;
    likes: number | null;
    favorites: number | null;
    new_followers: number | null;
  }>;
  exported_detail: {
    source_file: string;
    overview: Record<string, number>;
    conversion: Record<string, number>;
    daily_trend: Array<{ date: string; channel: string; reads: number; shares: number }>;
    channels: Array<{ label: string; reads: number }>;
    gender: Array<{ label: string; ratio: number }>;
    age: Array<{ label: string; ratio: number }>;
    regions: Array<{ label: string; ratio: number }>;
  } | null;
}

export interface Checkpoint {
  checkpoint_id: string;
  created_at: string;
  next: string[];
  stage: string;
  metadata: Record<string, unknown>;
}

export interface RunEvent {
  id: string;
  event: string;
  thread_id: string;
  project_id: string;
  data: Record<string, unknown>;
  created_at: string;
}

export type LlmTraceStatus = "success" | "schema_error" | "error" | "legacy";

export interface LlmTraceSummary {
  id: string;
  skill_run_id: string;
  thread_id: string;
  node_name: string;
  skill_name: string;
  skill_version: string;
  model_provider: string;
  model_name: string;
  schema_name: string;
  attempt: number;
  schema_attempt: number;
  status: LlmTraceStatus;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  latency_ms: number;
  created_at: string;
}

export interface LlmTraceRecord extends LlmTraceSummary {
  project_id: string;
  thread_id: string;
  prompt_hash: string;
  messages: Array<{ role: string; content: string }>;
  input_payload: Record<string, unknown>;
  raw_output: string | null;
  parsed_output: Record<string, unknown> | null;
  error_type: string | null;
  error_message: string | null;
}
