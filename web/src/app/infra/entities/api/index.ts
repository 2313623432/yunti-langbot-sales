import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { PipelineConfigTab } from '@/app/infra/entities/pipeline';
import { I18nObject } from '@/app/infra/entities/common';
import { Message } from '@/app/infra/entities/message';
import { Plugin, PluginV4 } from '@/app/infra/entities/plugin';

export interface ApiResponse<T> {
  code: number;
  data: T;
  msg: string;
}

export interface AsyncTaskCreatedResp {
  task_id: number;
}

export interface ApiRespProviderRequesters {
  requesters: Requester[];
}

export interface ApiRespProviderRequester {
  requester: Requester;
}

export interface Requester {
  name: string;
  label: I18nObject;
  description: I18nObject;
  icon?: string;
  spec: {
    config: IDynamicFormItemSchema[];
    provider_category: string;
  };
}

export interface ApiRespProviderLLMModels {
  models: LLMModel[];
}

export interface ApiRespProviderLLMModel {
  model: LLMModel;
}

export interface ModelProvider {
  uuid: string;
  name: string;
  requester: string;
  base_url: string;
  api_keys: string[];
  llm_count?: number;
  embedding_count?: number;
  rerank_count?: number;
  is_builtin?: boolean;
  protocol?: 'openai' | 'claude' | 'gemini';
  api_key_required?: boolean;
  sort_order?: number;
  created_at?: string;
  updated_at?: string;
}

export interface ApiRespModelProviders {
  providers: ModelProvider[];
}

export interface ApiRespModelProvider {
  provider: ModelProvider;
}

export interface ScannedProviderModel {
  id: string;
  name: string;
  type: 'llm' | 'embedding';
  abilities?: string[];
  display_name?: string;
  description?: string;
  context_length?: number | null;
  owned_by?: string;
  input_modalities?: string[];
  output_modalities?: string[];
  already_added: boolean;
}

export interface ProviderScanDebugInfo {
  request?: {
    method?: string;
    url?: string;
    headers?: Record<string, string>;
  };
  response?: unknown;
}

export interface ApiRespScannedProviderModels {
  models: ScannedProviderModel[];
  debug?: ProviderScanDebugInfo;
}

export interface LLMModel {
  uuid: string;
  name: string;
  provider_uuid: string;
  provider?: ModelProvider;
  abilities?: string[];
  extra_args?: object;
  test_audio_base64?: string;
}

export interface TestLLMModelResult {
  transcription?: string;
}

export interface ApiRespProviderEmbeddingModels {
  models: EmbeddingModel[];
}

export interface ApiRespProviderEmbeddingModel {
  model: EmbeddingModel;
}

export interface EmbeddingModel {
  uuid: string;
  name: string;
  provider_uuid: string;
  provider?: ModelProvider;
  extra_args?: object;
}

export interface ApiRespProviderRerankModels {
  models: RerankModel[];
}

export interface ApiRespProviderRerankModel {
  model: RerankModel;
}

export interface RerankModel {
  uuid: string;
  name: string;
  provider_uuid: string;
  provider?: ModelProvider;
  extra_args?: object;
}

export interface ApiRespPipelines {
  pipelines: Pipeline[];
}

export type AutoTestTargetType = 'pipeline' | 'workflow';

export interface AutoTestTarget {
  type: AutoTestTargetType;
  uuid: string;
  name: string;
  description: string;
  folder?: string;
  is_builtin?: boolean;
}

export interface AutoTestMessage {
  role: 'user' | 'assistant';
  sender: string;
  content_type: 'text' | 'image' | 'voice' | 'file';
  content: string;
  turn: number;
}

export interface AutoTestRun {
  uuid: string;
  target_type: AutoTestTargetType;
  target_uuid: string;
  target_name: string;
  status: string;
  scenario: string;
  messages: AutoTestMessage[];
  evaluation: {
    score?: number;
    max_score?: number;
    checks?: Record<string, boolean>;
    suggestions?: string[];
  };
  user_feedback: '' | 'satisfied' | 'unsatisfied';
  feedback_reason: string;
  optimization_summary: string;
  optimization_patch: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface ApiRespAutoTestTargets {
  pipelines: AutoTestTarget[];
  workflows: AutoTestTarget[];
}

export interface ApiRespAutoTestRuns {
  runs: AutoTestRun[];
}

export interface ApiRespAutoTestRun {
  run: AutoTestRun;
}

export interface WorkflowProject {
  uuid: string;
  folder: string;
  name: string;
  description: string;
  workflow: object;
  is_builtin?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ApiRespWorkflows {
  folders: string[];
  workflows: WorkflowProject[];
}

export interface Pipeline {
  uuid?: string;
  name: string;
  description: string;
  for_version?: string;
  config: object;
  stages?: string[];
  is_default?: boolean;
  is_builtin?: boolean;
  created_at?: string;
  updated_at?: string;
  emoji?: string;
}

export interface ApiRespPlatformAdapters {
  adapters: Adapter[];
}

export interface ApiRespPlatformAdapter {
  adapter: Adapter;
}

export interface Adapter {
  name: string;
  label: I18nObject;
  description: I18nObject;
  icon?: string;
  spec: {
    categories?: string[];
    help_links?: Record<string, string>;
    config: IDynamicFormItemSchema[];
  };
}

export interface ApiRespPlatformBots {
  bots: Bot[];
}

export interface ApiRespPlatformBot {
  bot: Bot;
}

export interface Bot {
  uuid?: string;
  name: string;
  description: string;
  enable?: boolean;
  adapter: string;
  adapter_config: object;
  use_pipeline_name?: string;
  use_pipeline_uuid?: string;
  pipeline_routing_rules?: PipelineRoutingRule[];
  created_at?: string;
  updated_at?: string;
  adapter_runtime_values?: object;
}

export type RoutingRuleOperator =
  | 'eq'
  | 'neq'
  | 'contains'
  | 'not_contains'
  | 'starts_with'
  | 'regex';

export interface PipelineRoutingRule {
  type:
    | 'launcher_type'
    | 'launcher_id'
    | 'message_content'
    | 'message_has_element';
  operator: RoutingRuleOperator;
  value: string;
  pipeline_uuid: string;
}

export interface ApiRespKnowledgeBases {
  bases: KnowledgeBase[];
}

export interface ApiRespKnowledgeBase {
  base: KnowledgeBase;
}

export interface KnowledgeBase {
  uuid?: string;
  name: string;
  description: string;
  created_at?: string;
  updated_at?: string;
  emoji?: string;
  // New unified fields
  knowledge_engine_plugin_id?: string;
  creation_settings?: Record<string, unknown>;
  retrieval_settings?: Record<string, unknown>;
  knowledge_engine?: KnowledgeEngineInfo;
  file_count?: number;
}

// Knowledge Engine types
export interface KnowledgeEngineInfo {
  plugin_id: string | null;
  name: I18nObject;
  capabilities: string[];
}

export interface KnowledgeEngine {
  plugin_id: string;
  name: I18nObject;
  description?: I18nObject;
  capabilities: string[];
  // Schema format: Array of form field definitions (IDynamicFormItemSchema-like)
  // Each item: { name, label, type, required, default, description?, options? }
  creation_schema?: unknown[];
  retrieval_schema?: unknown[];
}

export interface ApiRespKnowledgeEngines {
  engines: KnowledgeEngine[];
}

export interface ParserInfo {
  plugin_id: string;
  name: I18nObject;
  description?: I18nObject;
  supported_mime_types: string[];
}

export interface ApiRespParsers {
  parsers: ParserInfo[];
}

export interface ApiRespKnowledgeBaseFiles {
  files: KnowledgeBaseFile[];
}

export interface KnowledgeBaseFile {
  uuid: string;
  file_name: string;
  status: string;
  created_at?: string;
  chunk_count?: number;
}

// plugins
export interface ApiRespPlugins {
  plugins: Plugin[];
}

export interface ApiRespPlugin {
  plugin: Plugin;
}

// export interface Plugin {
//   author: string;
//   name: string;
//   description: I18nLabel;
//   label: I18nLabel;
//   version: string;
//   enabled: boolean;
//   priority: number;
//   status: string;
//   tools: object[];
//   event_handlers: object;
//   main_file: string;
//   pkg_path: string;
//   repository: string;
//   config_schema: IDynamicFormItemSchema[];
// }

export interface ApiRespPluginConfig {
  config: object;
}

export interface PluginReorderElement {
  author: string;
  name: string;
  priority: number;
}

// system
export interface SystemLimitation {
  max_bots: number;
  max_pipelines: number;
  max_extensions: number;
}

export interface WizardProgress {
  step: number;
  selected_adapter: string | null;
  created_bot_uuid: string | null;
  bot_saved: boolean;
  selected_runner: string | null;
}

export interface ApiRespSystemInfo {
  debug: boolean;
  version: string;
  edition: string;
  cloud_service_url: string;
  enable_marketplace: boolean;
  allow_modify_login_info: boolean;
  disable_models_service: boolean;
  limitation: SystemLimitation;
  wizard_status: string; // 'none' | 'skipped' | 'completed'
  wizard_progress: WizardProgress | null;
}

export interface RagMigrationStatusResp {
  needed: boolean;
  internal_kb_count: number;
  external_kb_count: number;
}

export interface ApiRespPluginSystemStatus {
  is_enable: boolean;
  is_connected: boolean;
  plugin_connector_error: string;
}

export interface ApiRespAsyncTasks {
  tasks: AsyncTask[];
}

export interface AsyncTaskRuntimeInfo {
  done: boolean;
  exception?: string;
  result?: object;
  state: string;
}

export interface AsyncTaskTaskContext {
  current_action: string;
  log: string;
  metadata?: Record<string, unknown>;
}

export interface AsyncTask {
  id: number;
  kind: string;
  name: string;
  label: string;
  task_type: string; // system or user
  runtime: AsyncTaskRuntimeInfo;
  task_context: AsyncTaskTaskContext;
}

export interface ApiRespUserToken {
  token: string;
}

export interface ApiRespAutoLogin {
  token: string;
  user: string;
  account_type: 'local' | 'space';
}

export interface SalesIntent {
  intent: string;
  confidence: number;
  requires_handoff: boolean;
  matched_keywords?: string[];
  reason?: string;
}

export interface SalesProduct {
  uuid?: string;
  name: string;
  product_line?: string;
  profile_key?: string;
  keywords?: string[];
  category: string;
  price: string;
  link: string;
  description: string;
  selling_points: string[];
  pain_points: string[];
  objections: string[];
  audience: string[];
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface SalesCustomerMemory {
  id: number;
  session_id: string;
  platform: string;
  user_id: string;
  customer_name: string;
  summary: string;
  stage: string;
  last_intent: string;
  preferred_product_uuid: string;
  profile?: Record<string, unknown>;
  intents: Array<Record<string, unknown>>;
  last_seen_at?: string;
  updated_at?: string;
}

export interface SalesHandoff {
  id: number;
  session_id: string;
  bot_uuid: string;
  target_type: string;
  target_id: string;
  platform: string;
  user_id: string;
  status: string;
  reason: string;
  last_message: string;
  operator_reply: string;
  assigned_to: string;
  updated_at?: string;
}

export type SalesConversationStatus =
  | 'ai_hosted'
  | 'pending_manual'
  | 'manual_handling';

export type SalesMessageComponent =
  | {
      kind: 'text';
      text: string;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'image';
      url?: string;
      base64?: string;
      path?: string;
      name?: string;
      available: boolean;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'voice';
      url?: string;
      base64?: string;
      path?: string;
      length?: number;
      available: boolean;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'file';
      name: string;
      url?: string;
      path?: string;
      available: boolean;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'link';
      title: string;
      description?: string;
      url: string;
      thumb_url?: string;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'quote';
      text: string;
      raw?: Record<string, unknown>;
    }
  | {
      kind: 'attachment';
      type: string;
      label: string;
      raw?: Record<string, unknown>;
    };

export interface SalesConversationMessage {
  id: string;
  timestamp: string;
  session_id: string;
  role: string | null;
  sender_kind: 'customer' | 'assistant' | 'operator';
  sender_label: string;
  bot_id: string;
  bot_name: string;
  platform: string | null;
  user_id: string | null;
  user_name: string | null;
  runner_name: string | null;
  status: string;
  level: string;
  preview: string;
  components: SalesMessageComponent[];
  metadata: Record<string, unknown>;
  raw_message_content: string;
}

export interface SalesConversation {
  session_id: string;
  customer_name: string;
  platform: string;
  user_id: string;
  user_name: string;
  bot_id: string;
  bot_name: string;
  message_count: number;
  last_activity: string;
  latest_message: SalesConversationMessage | null;
  latest_message_preview: string;
  handoff_status: SalesConversationStatus;
  handoff: SalesHandoff | null;
  memory: SalesCustomerMemory | null;
}

export interface SalesReplySuggestionResp {
  suggestion: {
    tone: string;
    message: string;
    next_action: string;
  };
  product: SalesProduct;
  source?: 'llm' | 'fallback';
  model_uuid?: string;
  model_name?: string;
}

export interface SalesOutreachPlan {
  id?: number;
  name: string;
  product_uuid: string;
  bot_uuid: string;
  target_type: 'person' | 'group';
  target_id: string;
  segment: string;
  dedupe_key?: string;
  message_template: string;
  message_components?: Array<Record<string, unknown>>;
  scheduled_at?: string;
  interval_minutes: number;
  enabled: boolean;
  last_sent_at?: string | null;
}

export interface SalesOverview {
  products_count: number;
  customers_count: number;
  open_handoffs_count: number;
  outreach_plans_count: number;
  scheduled_push_plans_count?: number;
  followup_plans_count?: number;
  products: SalesProduct[];
  recent_memories: SalesCustomerMemory[];
  open_handoffs: SalesHandoff[];
  outreach_plans: SalesOutreachPlan[];
  followup_plans?: SalesOutreachPlan[];
}

export interface SalesPitchResp {
  pitch: {
    tone: string;
    message: string;
    next_action: string;
  };
  product: SalesProduct;
}

export interface ApiRespMarketplacePlugins {
  plugins: PluginV4[];
  total: number;
}

export interface ApiRespMarketplacePluginDetail {
  plugin: PluginV4;
}

interface GetPipelineConfig {
  ai: object;
  output: object;
  safety: object;
  trigger: object;
}

interface GetPipeline {
  config: GetPipelineConfig;
  created_at: string;
  description: string;
  for_version: string;
  is_default: boolean;
  name: string;
  stages: string[];
  updated_at: string;
  uuid: string;
  emoji?: string;
}

export interface GetPipelineResponseData {
  pipeline: GetPipeline;
}

export interface GetPipelineMetadataResponseData {
  configs: PipelineConfigTab[];
}

export interface ApiRespWebChatMessage {
  message: Message;
}

export interface ApiRespWebChatMessages {
  messages: Message[];
}

export interface RetrieveResultContent {
  type: 'text' | 'image_url' | 'image_base64' | 'file_url';
  text?: string;
  file_name?: string;
  file_url?: string;
  image_url?: string;
  image_base64?: string;
}

export interface RetrieveResult {
  id: string;
  content?: RetrieveResultContent[];
  metadata: {
    file_id?: string;
    text?: string;
    uuid?: string;
    [key: string]: unknown;
  };
  distance: number;
}

export interface ApiRespKnowledgeBaseRetrieve {
  results: RetrieveResult[];
}

// MCP
export interface ApiRespMCPServers {
  servers: MCPServer[];
}

export interface ApiRespMCPServer {
  server: MCPServer;
}

export interface MCPServerExtraArgsSSE {
  url: string;
  headers: Record<string, string>;
  timeout: number;
  ssereadtimeout: number;
}

export interface MCPServerExtraArgsStdio {
  command: string;
  args: string[];
  env: Record<string, string>;
}

export interface MCPServerExtraArgsHttp {
  url: string;
  headers: Record<string, string>;
  timeout: number;
}

export enum MCPSessionStatus {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  ERROR = 'error',
}

export interface MCPServerRuntimeInfo {
  status: MCPSessionStatus;
  error_message?: string;
  tool_count: number;
  tools: MCPTool[];
}

export type MCPServer =
  | {
      uuid?: string;
      name: string;
      mode: 'sse';
      enable: boolean;
      extra_args: MCPServerExtraArgsSSE;
      runtime_info?: MCPServerRuntimeInfo;
      created_at?: string;
      updated_at?: string;
    }
  | {
      uuid?: string;
      name: string;
      mode: 'http';
      enable: boolean;
      extra_args: MCPServerExtraArgsHttp;
      runtime_info?: MCPServerRuntimeInfo;
      created_at?: string;
      updated_at?: string;
    }
  | {
      uuid?: string;
      name: string;
      mode: 'stdio';
      enable: boolean;
      extra_args: MCPServerExtraArgsStdio;
      runtime_info?: MCPServerRuntimeInfo;
      created_at?: string;
      updated_at?: string;
    };

export interface MCPTool {
  name: string;
  description: string;
  parameters?: object;
}

export interface PluginTool {
  name: string;
  description: string;
  human_desc: string;
  parameters: object;
}

export interface ApiRespTools {
  tools: PluginTool[];
}

export interface ApiRespToolDetail {
  tool: PluginTool;
}
