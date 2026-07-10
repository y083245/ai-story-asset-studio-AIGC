// Shared TypeScript types for Story Asset Studio.

export interface ApiErrorDetail {
  code: string;
  message: string;
  retryable: boolean;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export type ProjectStatus =
  | "draft"
  | "uploaded"
  | "novel_uploaded"
  | "analyzing"
  | "analysis_confirmed"
  | "generating_assets"
  | "generating_images"
  | "completed"
  | "failed"
  | "running"
  | "cancelled"
  | "archived";

export type AspectRatio = "9:16" | "16:9";
export type StyleMode = "auto" | "manual";
export type GenerationMode = "fast_preview" | "high_quality";

export interface ProjectCreateRequest {
  title: string;
  aspect_ratio: AspectRatio;
  style_mode: StyleMode;
  manual_style?: string;
  generation_mode: GenerationMode;
}

export interface ProjectUpdateRequest {
  title?: string;
  aspect_ratio?: AspectRatio;
  style_mode?: StyleMode;
  manual_style?: string;
  generation_mode?: GenerationMode;
}

export interface ProjectResponse {
  project_id: string;
  user_id: string;
  title: string;
  status: ProjectStatus;
  aspect_ratio: AspectRatio;
  style_mode: StyleMode;
  manual_style?: string;
  generation_mode: GenerationMode;
  progress: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  purge_after?: string | null;
}

export interface ProjectListResponse {
  items: ProjectResponse[];
  total: number;
}

export type TaskState = "pending" | "running" | "success" | "failed" | "retrying" | "needs_review";

export interface TaskStatus {
  task_id: string;
  name: string;
  state: TaskState;
  progress: number;
  retry_count: number;
  max_retries: number;
  error_message?: string;
  result_summary?: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
}

export interface ProjectStatusResponse {
  project_id: string;
  status: ProjectStatus;
  progress: number;
  current_stage?: string;
  message?: string;
  stage_index: number;
  total_stages: number;
  tasks: TaskStatus[];
  error_message?: string;
}

export interface ProjectCopyResponse {
  original_id: string;
  new_project: ProjectResponse;
}

export type NovelInputType = "text" | "txt" | "docx";

export interface NovelIntakeRequest {
  input_type: NovelInputType;
  text?: string;
  file_url?: string;
}

export interface NovelIntakeResponse {
  novel_id: string;
  title: string;
  clean_text: string;
  word_count: number;
  chapter_list: ChapterItem[];
  paragraph_list: string[];
  text_chunks: TextChunkItem[];
  preprocess_report: PreprocessReportItem;
}

export interface NovelDetailResponse {
  id: string;
  project_id: string;
  title: string;
  word_count: number;
  clean_text: string;
  chapter_list: Record<string, unknown>;
  paragraph_list: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ChapterItem {
  title: string;
  start: number;
}

export interface TextChunkItem {
  id: string;
  chunk_index: number;
  content: string;
  start_char: number;
  end_char: number;
  word_count: number;
  context_before?: string;
}

export interface PreprocessReportItem {
  original_word_count: number;
  clean_word_count: number;
  ads_removed: number;
  page_numbers_removed: number;
  garbled_lines_removed: number;
  blank_lines_removed: number;
  encoding_detected: string;
  input_type: string;
}

export interface NovelChunkListResponse {
  novel_id: string;
  chunks: TextChunkItem[];
  total: number;
}

export interface CharacterReference {
  character_id: string;
  name: string;
  description: string;
  role: string;
  gender?: string;
  age_range?: string;
}

export interface SceneReference {
  scene_id: string;
  name: string;
  description: string;
  time_period?: string;
  mood?: string;
  fixed_anchors: string[];
}

export interface PropReference {
  prop_id: string;
  name: string;
  description: string;
  function: string;
  state_timeline: string[];
}

export interface NegativePromptRule {
  category: string;
  terms: string[];
  reason: string;
}

export interface StoryBibleData {
  project_id: string;
  version: number;
  title: string;
  genre: string;
  visual_style: string;
  aspect_ratio: string;
  story_summary: string;
  main_conflict: string;
  emotional_tone: string;
  world_setting: string;
  time_period: string;
  color_palette: string[];
  composition_language: string[];
  characters: CharacterReference[];
  scenes: SceneReference[];
  props: PropReference[];
  negative_prompt_rules: NegativePromptRule[];
}

export interface StoryBibleResponse extends StoryBibleData {
  created_at: string;
  updated_at: string;
}

export interface StoryBiblePatchRequest {
  genre?: string;
  visual_style?: string;
  story_summary?: string;
  main_conflict?: string;
  emotional_tone?: string;
  world_setting?: string;
  time_period?: string;
  color_palette?: string[];
  composition_language?: string[];
}

export interface StyleCandidate {
  style_name: string;
  description: string;
  confidence: number;
  example_keywords: string[];
}

export interface AnalysisResponse {
  project_id: string;
  genre: string;
  visual_style: string;
  style_confidence: number;
  style_candidates?: StyleCandidate[];
  story_summary: string;
  main_conflict: string;
  protagonist?: CharacterReference;
  emotional_tone: string;
  world_setting: string;
  time_period: string;
  characters: CharacterReference[];
  scenes: SceneReference[];
  props: PropReference[];
  color_palette: string[];
  composition_language: string[];
}

export interface StoryBibleErrorResponse {
  code: string;
  message: string;
  retryable: boolean;
}

export interface StoryBibleVersionItem {
  version: number;
  created_at: string;
  title: string;
}

export interface StoryBibleVersionListResponse {
  project_id: string;
  versions: StoryBibleVersionItem[];
}

export interface StoryBibleVersionSnapshot {
  project_id: string;
  version: number;
  created_at: string;
  data: StoryBibleData;
}

export interface CharacterResponse {
  id: string;
  project_id: string;
  character_id: string;
  name: string;
  description: string;
  role: string;
  gender?: string;
  age_range?: string;
  outfit?: string;
  front_image_prompt?: string;
  turnaround_prompt?: string;
  reference_image_plan?: CharacterReferenceImagePlanItem[];
  expression_setting?: string;
  avatar_url?: string;
  reference_asset_ids: string[];
  reference_image_urls: string[];
  is_locked: boolean;
  generated_at?: string;
  created_at: string;
  updated_at: string;
}

export interface CharacterListResponse {
  characters: CharacterResponse[];
  total: number;
}

export interface CharacterUpdateRequest {
  name?: string;
  description?: string;
  outfit?: string;
  front_image_prompt?: string;
  turnaround_prompt?: string;
  reference_image_plan?: CharacterReferenceImagePlanItem[];
  expression_setting?: string;
  is_locked?: boolean;
}

export interface CharacterReferenceImagePlanItem {
  category?: string;
  description?: string;
  priority?: string;
  style_id?: string;
}

export interface CharacterRegenerateResponse {
  character_id: string;
  status: string;
  message: string;
}

export interface SceneResponse {
  id: string;
  project_id: string;
  scene_id: string;
  name: string;
  description: string;
  time_period?: string;
  mood?: string;
  location?: string;
  scene_prompt?: string;
  empty_scene_prompt?: string;
  fixed_anchors: string[];
  thumbnail_url?: string;
  is_locked: boolean;
  created_at: string;
  updated_at: string;
}

export interface SceneListResponse {
  scenes: SceneResponse[];
  total: number;
}

export interface SceneUpdateRequest {
  name?: string;
  description?: string;
  time_period?: string;
  mood?: string;
  location?: string;
  scene_prompt?: string;
  empty_scene_prompt?: string;
  is_locked?: boolean;
}

export interface SceneRegenerateResponse {
  scene_id: string;
  status: string;
  message: string;
}

export interface PropResponse {
  id: string;
  project_id: string;
  prop_id: string;
  name: string;
  description: string;
  function: string;
  state_timeline: string[];
  prop_prompt?: string;
  usage_prompt?: string;
  thumbnail_url?: string;
  is_locked: boolean;
  created_at: string;
  updated_at: string;
}

export interface PropListResponse {
  props: PropResponse[];
  total: number;
}

export interface PropUpdateRequest {
  name?: string;
  description?: string;
  function?: string;
  state_timeline?: string[];
  prop_prompt?: string;
  usage_prompt?: string;
  is_locked?: boolean;
}

export interface PropRegenerateResponse {
  prop_id: string;
  status: string;
  message: string;
}
