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
