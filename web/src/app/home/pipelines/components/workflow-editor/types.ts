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

export interface PipelineTemplateConfig {
  name: string;
  role_prompt: string;
  opening_message: string;
  recommended_questions: string[];
  model_uuid: string;
  max_reasoning_steps: number;
  reference_rounds: number;
  response_diversity: number;
  knowledge_base_uuids: string[];
  product_uuids: string[];
  tools: Record<string, boolean>;
  memory: {
    variables_enabled: boolean;
    table_enabled: boolean;
    segments_enabled: boolean;
  };
  voice: {
    provider: string;
    enabled: boolean;
    voice_type: string;
    encoding: string;
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
  image_text_bindings: PipelineTemplateImageTextBinding[];
  course_profile?: Record<string, string>;
  resource_faqs?: Record<string, unknown>[];
  course_faqs?: Record<string, unknown>[];
  sales_links?: PipelineTemplateSalesLink[];
  radar?: PipelineTemplateRadarConfig;
  followup_sequences?: PipelineTemplateFollowupSequence[];
  long_term_broadcasts?: PipelineTemplateBroadcast[];
  stop_rules?: PipelineTemplateStopRules;
}
