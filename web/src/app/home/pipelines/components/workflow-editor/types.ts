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

export interface PipelineTemplateConfig {
  name: string;
  role_prompt: string;
  opening_message: string;
  recommended_questions: string[];
  model_uuid: string;
  max_reasoning_steps: number;
  reference_rounds: number;
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
  image_text_bindings: PipelineTemplateImageTextBinding[];
}
