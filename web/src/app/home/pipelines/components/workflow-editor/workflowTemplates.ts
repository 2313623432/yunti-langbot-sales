import {
  PipelineWorkflow,
  PipelineWorkflowEdge,
  PipelineWorkflowNode,
  WorkflowNodeType,
} from './types';

const nodeDefaults: Record<
  WorkflowNodeType,
  Pick<PipelineWorkflowNode, 'title' | 'description' | 'config'>
> = {
  start: {
    title: '收到客户消息',
    description: '会话入口',
    config: { trigger: 'message' },
  },
  channel: {
    title: '渠道接入',
    description: '统一接收网页、微信、企微、飞书等渠道消息',
    config: { channels: ['web', 'wechat', 'wecom', 'lark'], keep_session: true },
  },
  media: {
    title: '消息类型判断',
    description: '区分文字、图片、语音和文件',
    config: {
      routes: [
        { when: 'has_text', target: 'text_input' },
        { when: 'has_image', target: 'vision' },
        { when: 'has_voice', target: 'asr' },
      ],
    },
  },
  asr: {
    title: '语音输入处理',
    description: '把语音消息转成可理解的文本上下文',
    config: {
      provider: 'bailian',
      fallback_text: '用户发来一条语音咨询，请用短句回复。',
    },
  },
  intent: {
    title: '意图识别',
    description: '识别咨询、报价、售后、投诉、转人工等意图',
    config: {
      intents: ['咨询产品', '询价报价', '售后问题', '投诉不满', '转人工'],
      image_intents: ['询价报价', '咨询产品'],
      confidence_threshold: 0.72,
    },
  },
  router: {
    title: '意图路由',
    description: '按意图或条件把会话送到不同节点',
    config: { rules: ['intent == task_overview -> step_1'] },
  },
  knowledge: {
    title: '查询知识库',
    description: '按问题检索资料',
    config: { knowledge_base_uuids: [], top_k: 5 },
  },
  product: {
    title: '匹配产品',
    description: '结合产品库推荐合适方案',
    config: { product_uuids: [], match_by: 'selling_points' },
  },
  task: {
    title: '任务步骤',
    description: '配置任务拆解、完成条件和步骤说明',
    config: { steps: [], completion_check: '' },
  },
  vision: {
    title: '截图识别',
    description: '识别用户截图所在步骤并给出下一步',
    config: { model_uuid: '', target_steps: [] },
  },
  llm: {
    title: '生成回复',
    description: '按销售/客服话术组织回复',
    config: {
      tone: 'professional',
      prompt: '根据客户意图、知识库结果和产品资料，生成一句自然、具体、有下一步动作的回复。',
    },
  },
  condition: {
    title: '条件分流',
    description: '按意图、置信度、客户阶段分支',
    config: { rules: ['requires_handoff == true', 'intent in image_intents'] },
  },
  lead: {
    title: '收集线索',
    description: '记录姓名、电话、预算、需求',
    config: { fields: ['姓名', '电话', '预算', '需求'], required_fields: ['电话'] },
  },
  image: {
    title: '发送图片/素材',
    description: '按意图发送产品图、报价图、二维码或海报',
    config: {
      trigger_intents: ['咨询产品', '询价报价'],
      caption: '',
      file_key: '',
      image_url: '',
    },
  },
  memory: {
    title: '更新客户记忆',
    description: '沉淀客户阶段、兴趣产品和摘要',
    config: { stage: 'new', tags: ['高意向', '待跟进'] },
  },
  outreach: {
    title: '定时跟进',
    description: '创建销售触达计划',
    config: { delay_minutes: 1440, message_template: '您好，给您同步一下上次关注的产品资料。' },
  },
  handoff: {
    title: '人工介入',
    description: '进入人工接待队列',
    config: { reason: '客户需要人工协助', assigned_to: '' },
  },
  http: {
    title: 'HTTP 请求',
    description: '调用外部 CRM、订单或线索系统',
    config: { method: 'POST', url: '', body_template: '{}' },
  },
  plugin: {
    title: '插件工具',
    description: '调用已安装插件能力',
    config: { plugin: '', tool: '', params: '{}' },
  },
  mcp: {
    title: 'MCP 工具',
    description: '调用已配置 MCP 服务',
    config: { server: '', tool: '', params: '{}' },
  },
  voice: {
    title: '语音回复',
    description: '把文字回复转换成语音消息',
    config: {
      provider: 'volcengine',
      enabled: true,
      voice_type: 'zh_female_yuanqinvyou_moon_bigtts',
      encoding: 'ogg_opus',
    },
  },
  custom: {
    title: '自定义动作',
    description: '无代码参数化节点',
    config: { output_key: '', params: '{}' },
  },
  end: {
    title: '回复客户',
    description: '发送最终消息',
    config: { close_conversation: false },
  },
};

function makeId(prefix: string): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
  }
  return `${prefix}-${Math.random().toString(16).slice(2, 10)}`;
}

export function createWorkflowNode(
  type: WorkflowNodeType,
  position: { x: number; y: number },
): PipelineWorkflowNode {
  const defaults = nodeDefaults[type];
  return {
    id: makeId(type),
    type,
    title: defaults.title,
    description: defaults.description,
    position,
    config: structuredClone(defaults.config),
  };
}

function edge(
  source: PipelineWorkflowNode,
  target: PipelineWorkflowNode,
  label?: string,
): PipelineWorkflowEdge {
  return {
    id: makeId('edge'),
    source: source.id,
    target: target.id,
    label,
  };
}

export function createSalesWorkflowTemplate(): PipelineWorkflow {
  const start = createWorkflowNode('start', { x: 80, y: 190 });
  const intent = createWorkflowNode('intent', { x: 330, y: 190 });
  const product = createWorkflowNode('product', { x: 580, y: 90 });
  const knowledge = createWorkflowNode('knowledge', { x: 580, y: 290 });
  const llm = createWorkflowNode('llm', { x: 830, y: 190 });
  const condition = createWorkflowNode('condition', { x: 1080, y: 190 });
  const image = createWorkflowNode('image', { x: 1330, y: 80 });
  const lead = createWorkflowNode('lead', { x: 1330, y: 225 });
  const handoff = createWorkflowNode('handoff', { x: 1330, y: 370 });
  const memory = createWorkflowNode('memory', { x: 1580, y: 225 });
  const outreach = createWorkflowNode('outreach', { x: 1830, y: 225 });
  const end = createWorkflowNode('end', { x: 2080, y: 225 });

  return {
    version: 1,
    name: '销售转化工作流',
    scenario: 'sales',
    nodes: [start, intent, product, knowledge, llm, condition, image, lead, handoff, memory, outreach, end],
    edges: [
      edge(start, intent),
      edge(intent, product, '产品咨询/报价'),
      edge(intent, knowledge, '通用问题'),
      edge(product, llm),
      edge(knowledge, llm),
      edge(llm, condition),
      edge(condition, image, '需要图片素材'),
      edge(condition, lead, '高意向'),
      edge(condition, handoff, '转人工'),
      edge(image, memory),
      edge(lead, memory),
      edge(handoff, memory),
      edge(memory, outreach),
      edge(outreach, end),
    ],
    variables: {
      customer_stage: 'new',
      intent: '',
      selected_product_uuid: '',
    },
  };
}

export function createSupportWorkflowTemplate(): PipelineWorkflow {
  const start = createWorkflowNode('start', { x: 80, y: 190 });
  const intent = createWorkflowNode('intent', { x: 330, y: 190 });
  const knowledge = createWorkflowNode('knowledge', { x: 580, y: 190 });
  const llm = createWorkflowNode('llm', { x: 830, y: 190 });
  const condition = createWorkflowNode('condition', { x: 1080, y: 190 });
  const image = createWorkflowNode('image', { x: 1330, y: 95 });
  const handoff = createWorkflowNode('handoff', { x: 1330, y: 285 });
  const memory = createWorkflowNode('memory', { x: 1580, y: 190 });
  const end = createWorkflowNode('end', { x: 1830, y: 190 });

  intent.config = {
    ...intent.config,
    intents: ['使用咨询', '故障排查', '订单问题', '投诉不满', '转人工'],
    image_intents: ['使用咨询', '故障排查'],
  };
  llm.config = {
    ...llm.config,
    prompt: '根据客户问题、知识库结果和客服话术，给出清晰、克制、可执行的处理回复。',
  };

  return {
    version: 1,
    name: '客服接待工作流',
    scenario: 'support',
    nodes: [start, intent, knowledge, llm, condition, image, handoff, memory, end],
    edges: [
      edge(start, intent),
      edge(intent, knowledge),
      edge(knowledge, llm),
      edge(llm, condition),
      edge(condition, image, '需要图文说明'),
      edge(condition, handoff, '投诉/复杂问题'),
      edge(image, memory),
      edge(handoff, memory),
      edge(memory, end),
    ],
    variables: {
      customer_stage: 'supporting',
      intent: '',
    },
  };
}

export function createDefaultWorkflow(): PipelineWorkflow {
  return createSalesWorkflowTemplate();
}

export function getNodeDefaults(type: WorkflowNodeType) {
  return nodeDefaults[type];
}
