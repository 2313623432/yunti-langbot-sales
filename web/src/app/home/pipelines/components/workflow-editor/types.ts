export type WorkflowNodeType =
  | 'start'
  | 'channel'
  | 'media'
  | 'asr'
  | 'intent'
  | 'router'
  | 'knowledge'
  | 'product'
  | 'task'
  | 'vision'
  | 'llm'
  | 'condition'
  | 'lead'
  | 'image'
  | 'memory'
  | 'radar'
  | 'outreach'
  | 'handoff'
  | 'http'
  | 'plugin'
  | 'mcp'
  | 'voice'
  | 'custom'
  | 'end';

export interface WorkflowNodePosition {
  x: number;
  y: number;
}

export interface PipelineWorkflowNode {
  id: string;
  type: WorkflowNodeType;
  title: string;
  description?: string;
  position: WorkflowNodePosition;
  config: Record<string, unknown>;
}

export interface PipelineWorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export interface PipelineWorkflow {
  version: 1;
  name: string;
  scenario: 'sales' | 'support' | 'task' | 'custom';
  metadata?: Record<string, unknown>;
  voice?: Record<string, unknown>;
  memes?: PipelineTemplateMemeConfig;
  special_cases?: PipelineTemplateSpecialCase[];
  nodes: PipelineWorkflowNode[];
  edges: PipelineWorkflowEdge[];
  variables: Record<string, unknown>;
}

export interface PipelineTemplateImageTextBinding {
  step_id: string;
  title: string;
  text: string;
  file_key: string;
  image_url?: string;
  trigger_intents?: string[];
  enabled?: boolean;
}

export interface PipelineTemplateSalesLink {
  id: string;
  title: string;
  url: string;
  description?: string;
  radar_enabled?: boolean;
}

export interface PipelineTemplateRadarRule {
  event: string;
  delay_minutes: number;
  message: string;
  min_browse_seconds?: number;
}

export interface PipelineTemplateRadarConfig {
  enabled: boolean;
  link_title: string;
  link_url: string;
  tracking_fields: string[];
  rules: PipelineTemplateRadarRule[];
}

export interface PipelineTemplateFollowupMessage {
  delay_minutes: number;
  message: string;
  schedule_time?: string;
  voice_optional?: boolean;
  link_id?: string;
  send_link_card?: boolean;
  image_key?: string;
  image_url?: string;
  action?: string;
}

export interface PipelineTemplateFollowupSequence {
  stage: string;
  label: string;
  messages: PipelineTemplateFollowupMessage[];
}

export interface PipelineTemplateBroadcast {
  day: number;
  title: string;
  time: string;
  message: string;
  image_key?: string;
}

export interface PipelineTemplateStopRules {
  stop_keywords: string[];
  stop_tags: string[];
  message: string;
}

export interface PipelineTemplateCourseProfile {
  key: string;
  product_uuid: string;
  name: string;
  keywords?: string[];
  facts: Record<string, string>;
}

export interface PipelineTemplateStopPolicy {
  explicit_rejection_threshold: number;
  explicit_rejection_keywords: string[];
  immediate_stop_keywords: string[];
}

export interface PipelineTemplateHumanHandoffTrigger {
  id: string;
  label: string;
  description: string;
  enabled?: boolean;
}

export interface PipelineTemplateHumanHandoff {
  enabled: boolean;
  keywords: string[];
  semantic_triggers: PipelineTemplateHumanHandoffTrigger[];
  stop_ai_reply: boolean;
  stop_outreach: boolean;
  notify_message: string;
}

export interface PipelineTemplateSpecialCase {
  id: string;
  enabled: boolean;
  condition: string;
  reply: string;
  ai_rewrite: boolean;
  file_key?: string;
  image_url?: string;
}

export interface PipelineTemplateMemeLibraryItem {
  id: string;
  enabled: boolean;
  meaning: string;
  trigger_keyword: string;
  code?: string;
  emotion?: string;
  search_keyword?: string;
  usage_scene?: string;
  usage_instruction?: string;
  feishu_emoji?: string;
  keywords?: string[];
  tags?: string[];
  file_key?: string;
  image_url?: string;
  source?: string;
}

export interface PipelineTemplateMemeConfig {
  enabled: boolean;
  large_enabled: boolean;
  feishu_native_enabled: boolean;
  smart_judge_enabled: boolean;
  small_interval_rounds: number;
  large_interval_rounds: number;
  library_enabled: boolean;
  api_fallback_enabled: boolean;
  oiapi_enabled?: boolean;
  oiapi_limit?: number;
  library: PipelineTemplateMemeLibraryItem[];
}

export interface PipelineTemplateReplyControls {
  multi_reply_enabled: boolean;
  merge_reply_enabled: boolean;
  merge_delay_seconds: number;
}

export interface PipelineTemplateKnowledgePack {
  path?: string;
  freshness_range?: string;
  answering_rule?: string;
}

export interface PipelineTemplateConfig {
  name: string;
  metadata?: {
    knowledge_pack?: PipelineTemplateKnowledgePack;
    [key: string]: unknown;
  };
  role_prompt: string;
  opening_message: string;
  recommended_questions: string[];
  model_uuid: string;
  model_extra_args?: Record<string, unknown>;
  intent_model_uuid: string;
  intent_model_extra_args?: Record<string, unknown>;
  max_reasoning_steps: number;
  reference_rounds: number;
  response_diversity: number;
  knowledge_base_uuids: string[];
  product_uuids: string[];
  tools: Record<string, boolean>;
  reply_controls: PipelineTemplateReplyControls;
  memory: {
    variables_enabled: boolean;
    table_enabled: boolean;
    segments_enabled: boolean;
  };
  voice: {
    model_uuid?: string;
    provider: string;
    enabled: boolean;
    voice_type: string;
    encoding: string;
  };
  asr: {
    model_uuid?: string;
    provider: string;
    fallback_text: string;
  };
  scheduled_push: {
    enabled: boolean;
    mode: 'daily' | 'single_day';
    time: string;
    single_date: string;
    message: string;
    push_message?: string;
  };
  interaction_radar: {
    enabled: boolean;
    link_url: string;
    click_reply: string;
  };
  human_handoff: PipelineTemplateHumanHandoff;
  memes?: PipelineTemplateMemeConfig;
  special_cases: PipelineTemplateSpecialCase[];
  image_text_bindings: PipelineTemplateImageTextBinding[];
  course_profile?: Record<string, string>;
  course_profiles?: PipelineTemplateCourseProfile[];
  source_materials?: string[];
  resource_faqs?: Record<string, unknown>[];
  course_faqs?: Record<string, unknown>[];
  sales_links?: PipelineTemplateSalesLink[];
  radar?: PipelineTemplateRadarConfig;
  followup_sequences?: PipelineTemplateFollowupSequence[];
  long_term_broadcasts?: PipelineTemplateBroadcast[];
  stop_rules?: PipelineTemplateStopRules;
  stop_policy?: PipelineTemplateStopPolicy;
}
