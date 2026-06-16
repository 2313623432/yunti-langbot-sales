import {
  PipelineTemplateConfig,
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
    config: {
      channels: ['web', 'wechat', 'wecom', 'lark'],
      keep_session: true,
    },
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
      prompt:
        '根据客户意图、知识库结果和产品资料，生成一句自然、具体、有下一步动作的回复。',
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
    config: {
      fields: ['姓名', '电话', '预算', '需求'],
      required_fields: ['电话'],
    },
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
  radar: {
    title: '链接点击雷达',
    description: '按链接点击、浏览时长和按钮行为触发跟进',
    config: {
      enabled: true,
      link_title: '报名通道',
      link_url: 'https://m.yuanfudao.com/primary/templates/package?pageId=6641&solutionId=27246&keyfrom=yfd-qudaohezuo-xiaoxue-9yyy-CPA-yunti9-siyu-yangzy-yingtao3class',
      tracking_fields: ['session_id', 'clicked_at', 'browse_seconds', 'clicked_apply_button'],
      rules: [
        {
          event: 'link_open',
          delay_minutes: 0,
          message: '家长，看您进入报名通道了，支付以后截图发我，我给您登记开课。',
        },
      ],
    },
  },
  outreach: {
    title: '定时跟进',
    description: '创建销售触达计划',
    config: {
      delay_minutes: 1440,
      message_template: '您好，给您同步一下上次关注的产品资料。',
    },
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
      model_uuid: '',
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
    nodes: [
      start,
      intent,
      product,
      knowledge,
      llm,
      condition,
      image,
      lead,
      handoff,
      memory,
      outreach,
      end,
    ],
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
    prompt:
      '根据客户问题、知识库结果和客服话术，给出清晰、克制、可执行的处理回复。',
  };

  return {
    version: 1,
    name: '客服接待工作流',
    scenario: 'support',
    nodes: [
      start,
      intent,
      knowledge,
      llm,
      condition,
      image,
      handoff,
      memory,
      end,
    ],
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

export function createBlankWorkflow(): PipelineWorkflow {
  const start = createWorkflowNode('start', { x: 120, y: 220 });
  const end = createWorkflowNode('end', { x: 460, y: 220 });

  start.title = '开始';
  start.description = '流程入口';
  end.title = '结束';
  end.description = '流程结束';

  return {
    version: 1,
    name: '空白工作流',
    scenario: 'custom',
    nodes: [start, end],
    edges: [edge(start, end)],
    variables: {},
  };
}

function workflowNode(
  id: string,
  type: WorkflowNodeType,
  title: string,
  description: string,
  position: { x: number; y: number },
  config: Record<string, unknown>,
): PipelineWorkflowNode {
  return {
    id,
    type,
    title,
    description,
    position,
    config,
  };
}

function workflowEdge(
  id: string,
  source: string,
  target: string,
  label?: string,
): PipelineWorkflowEdge {
  return {
    id,
    source,
    target,
    ...(label ? { label } : {}),
  };
}

const taskAssistantSteps = [
  {
    id: 'download_qr',
    title: '支付宝扫码下载蚂蚁阿福 App',
    detail: '让用户先用支付宝扫描绑定的渠道码，进入下载页面，点击“下载蚂蚁阿福App”。',
    image_key: 'task-assistant/ant-af/af_step_01.png',
    intents: ['task_overview', 'download_app', 'screenshot_help'],
  },
  {
    id: 'app_store_download',
    title: '在应用商店点击下载',
    detail: '如果跳转到应用商店，确认页面是“蚂蚁阿福”，点击下载并等待安装完成。',
    image_key: 'task-assistant/ant-af/af_step_02.png',
    intents: ['task_overview', 'download_app', 'screenshot_help'],
  },
  {
    id: 'alipay_login',
    title: '打开 App 后使用支付宝一键登录',
    detail: '进入蚂蚁阿福首页后，点击页面底部的“支付宝一键登录”。',
    image_key: 'task-assistant/ant-af/af_step_03.png',
    intents: ['task_overview', 'alipay_login', 'screenshot_help'],
  },
  {
    id: 'alipay_login_confirm',
    title: '同意支付宝授权登录',
    detail: '在支付宝授权页确认申请方是蚂蚁阿福 App，点击“同意”。',
    image_key: 'task-assistant/ant-af/af_step_04.png',
    intents: ['task_overview', 'alipay_login', 'screenshot_help'],
  },
  {
    id: 'open_profile',
    title: '登录后点击左上角头像/菜单',
    detail: '登录成功后，在首页点击左上角头像或菜单入口，进入个人中心。',
    image_key: 'task-assistant/ant-af/af_step_05.png',
    intents: ['task_overview', 'real_person_verify', 'screenshot_help'],
  },
  {
    id: 'open_settings',
    title: '进入设置',
    detail: '在个人中心页面点击用户信息区域或设置入口，进入“我的/设置”相关页面。',
    image_key: 'task-assistant/ant-af/af_step_06.png',
    intents: ['task_overview', 'real_person_verify', 'screenshot_help'],
  },
  {
    id: 'open_real_person_verify',
    title: '点击实名认证',
    detail: '在“我的”页面找到“实名认证”，点击进入。若显示“已认证”，说明这一步已完成。',
    image_key: 'task-assistant/ant-af/af_step_07.png',
    intents: ['task_overview', 'real_person_verify', 'finish', 'screenshot_help'],
  },
  {
    id: 'import_identity',
    title: '支付宝一键导入身份信息',
    detail: '在真人认证页面点击“支付宝一键导入”，按支付宝提示完成身份信息授权。',
    image_key: 'task-assistant/ant-af/af_step_08.png',
    intents: ['task_overview', 'real_person_verify', 'finish', 'screenshot_help'],
  },
];

export function createTaskAssistantWorkflowTemplate(): PipelineWorkflow {
  const templateConfig = createTaskAssistantTemplateConfig();
  const targetSteps = taskAssistantSteps.map((step) => step.id);
  const nodes: PipelineWorkflowNode[] = [
    workflowNode('start', 'start', '会话触发', '用户在网页、微信或企微发来咨询', { x: 80, y: 260 }, { trigger: 'message' }),
    workflowNode('channel', 'channel', '渠道接入', '统一接收网页、微信、企微等渠道消息', { x: 330, y: 260 }, { channels: ['web', 'wechat', 'wecom'], keep_session: true }),
    workflowNode('media_router', 'media', '消息类型判断', '区分文字、截图和语音', { x: 580, y: 260 }, {
      routes: [
        { when: 'has_text', target: 'text_input' },
        { when: 'has_voice', target: 'voice_asr' },
        { when: 'has_image', target: 'screenshot_input' },
      ],
    }),
    workflowNode('text_input', 'custom', '文字问题', '整理用户文字问题和上下文', { x: 850, y: 90 }, {
      output_key: 'user_text',
      params: '{"from": "message_chain.plain_text"}',
    }),
    workflowNode('voice_asr', 'asr', '语音输入处理', '语音消息转成适合模型理解的任务上下文，避免聊天请求失败', { x: 850, y: 260 }, {
      provider: 'bailian',
      fallback_text: '用户发来一条语音咨询，请用适合语音播报的短句回复。',
    }),
    workflowNode('screenshot_input', 'vision', '截图识别', '识别用户卡在哪个页面或步骤', { x: 850, y: 430 }, {
      model_uuid: templateConfig.model_uuid,
      target_steps: targetSteps,
    }),
    workflowNode('intent', 'intent', '意图识别', '识别下载、登录、实名认证、截图卡点、完成确认等意图', { x: 1130, y: 260 }, {
      intents: [
        'task_overview',
        'download_app',
        'alipay_login',
        'real_person_verify',
        'finish',
        'screenshot_help',
        'voice_reply',
      ],
      confidence_threshold: 0.55,
      image_intents: ['screenshot_help'],
    }),
    workflowNode('route_intent', 'router', '意图路由', '把用户问题分发到对应步骤节点', { x: 1400, y: 260 }, {
      rules: [
        'download_app -> download_qr, app_store_download',
        'alipay_login -> alipay_login, alipay_login_confirm',
        'real_person_verify -> open_profile, open_settings, open_real_person_verify, import_identity',
        'screenshot_help -> matched_step',
        'finish -> open_real_person_verify, import_identity',
      ],
    }),
    workflowNode('knowledge_fallback', 'knowledge', '知识库兜底', '不属于固定步骤的问题，查知识库后再回答', { x: 1660, y: 620 }, {
      knowledge_base_uuids: templateConfig.knowledge_base_uuids,
      top_k: 4,
    }),
    workflowNode('reply', 'llm', '真人客服式回复', '生成自然、短句、可执行的下一步指引', { x: 3030, y: 260 }, {
      model_uuid: templateConfig.model_uuid,
      tone: '真人客服、短句、具体',
      prompt: templateConfig.role_prompt,
    }),
    workflowNode('voice', 'voice', '火山语音回复', '用户发语音时，把文字回复转成语音一起发回去', { x: 3300, y: 160 }, templateConfig.voice),
    workflowNode('end', 'end', '发送给用户', '发送文字、相关步骤图和必要时的语音', { x: 3300, y: 360 }, {}),
  ];

  const stepPositions = [
    { x: 1660, y: 40 },
    { x: 1660, y: 200 },
    { x: 1940, y: 40 },
    { x: 1940, y: 200 },
    { x: 2220, y: 40 },
    { x: 2220, y: 200 },
    { x: 2500, y: 40 },
    { x: 2500, y: 200 },
  ];
  const imagePositions = [
    { x: 1660, y: 380 },
    { x: 1660, y: 500 },
    { x: 1940, y: 380 },
    { x: 1940, y: 500 },
    { x: 2220, y: 380 },
    { x: 2220, y: 500 },
    { x: 2500, y: 380 },
    { x: 2500, y: 500 },
  ];

  taskAssistantSteps.forEach((step, index) => {
    nodes.push(
      workflowNode(`step_${step.id}`, 'task', step.title, step.detail, stepPositions[index], {
        step_id: step.id,
        step_no: index + 1,
        instruction: step.detail,
        trigger_intents: step.intents,
        completion_check: '用户完成后继续下一步，最后检查是否显示已认证或任务完成。',
      }),
      workflowNode(`image_${step.id}`, 'image', `步骤图 ${index + 1}`, step.title, imagePositions[index], {
        file_key: step.image_key,
        caption: step.title,
        trigger_intents: step.intents,
        append_caption: false,
      }),
    );
  });

  const edges: PipelineWorkflowEdge[] = [
    workflowEdge('e-start-channel', 'start', 'channel'),
    workflowEdge('e-channel-media', 'channel', 'media_router'),
    workflowEdge('e-media-text', 'media_router', 'text_input', '文字'),
    workflowEdge('e-media-voice', 'media_router', 'voice_asr', '语音'),
    workflowEdge('e-media-image', 'media_router', 'screenshot_input', '截图/图片'),
    workflowEdge('e-text-intent', 'text_input', 'intent'),
    workflowEdge('e-voice-intent', 'voice_asr', 'intent'),
    workflowEdge('e-screenshot-intent', 'screenshot_input', 'intent'),
    workflowEdge('e-intent-route', 'intent', 'route_intent'),
    workflowEdge('e-route-knowledge', 'route_intent', 'knowledge_fallback', '兜底问题'),
    workflowEdge('e-knowledge-reply', 'knowledge_fallback', 'reply'),
    workflowEdge('e-reply-voice', 'reply', 'voice', '用户发语音'),
    workflowEdge('e-reply-end', 'reply', 'end', '文字/图片'),
    workflowEdge('e-voice-end', 'voice', 'end'),
  ];

  taskAssistantSteps.forEach((step) => {
    edges.push(
      workflowEdge(`e-route-${step.id}`, 'route_intent', `step_${step.id}`, step.intents.slice(0, 2).join('/')),
      workflowEdge(`e-step-image-${step.id}`, `step_${step.id}`, `image_${step.id}`),
      workflowEdge(`e-image-reply-${step.id}`, `image_${step.id}`, 'reply'),
    );
  });

  const workflow: PipelineWorkflow = {
    version: 1,
    name: '任务助手模板配置版',
    scenario: 'task',
    metadata: {
      scenario: 'task_assistant_ant_af',
      source: '蚂蚁阿福.docx',
      source_mode: 'template',
      template_name: '任务助手模板配置版',
      tts_provider: 'volcengine',
    },
    voice: templateConfig.voice,
    nodes,
    edges,
    variables: {
      opening_message: templateConfig.opening_message,
      recommended_questions: templateConfig.recommended_questions,
      scheduled_push: templateConfig.scheduled_push,
      interaction_radar: templateConfig.interaction_radar,
      image_text_bindings: templateConfig.image_text_bindings,
    },
  };

  if (workflow.nodes.length !== 28 || workflow.edges.length !== 38) {
    throw new Error('Task assistant workflow template must keep 28 nodes and 38 edges.');
  }

  return workflow;
}

const courseSalesSignupLink =
  'https://m.yuanfudao.com/primary/templates/package?pageId=6641&solutionId=27246&keyfrom=yfd-qudaohezuo-xiaoxue-9yyy-CPA-yunti9-siyu-yangzy-yingtao3class';
const courseResourceCardLink =
  'https://mp.zhizhuma.com/webappv2/videoLecture/video-tbxvm9.htm?resId=99132427&idSign=f6b025&resType=104&bookId=593223&bookIdSign=04d70c&targetId=2207977&_wxPage=teaVideo&crId=71099576&crIdSign=4f6334&entityId=593223&entityType=1&_wxId=593223&_wxType=1&_wxSrc=116&_rand=1773575505347';
const courseOpeningMessage =
  '😊 您的图书配套学习资源点击👇️下方卡片激活查看；\n也可点击➡️查看扫码记录  https://mp.bookln.cn/user/history/moment.htm\n\n✅ 搜本页答案，点击👉#小程序://教辅好帮手/la0KWwjPCx8S26C\n\n✅ 出版社内购好物群：https://d.codeup.cn/d/UVruQn\n\n家长，您这边能打开吗？';
const defaultHumanHandoff = {
  enabled: true,
  keywords: [
    '转人工',
    '人工',
    '真人客服',
    '班主任',
    '电话联系',
    '投诉',
    '退款',
    '退费',
    '支付异常',
    '看不到课',
    '骗子',
  ],
  semantic_triggers: [
    {
      id: 'manual_request',
      label: '明确要求转人工',
      description: '客户明确要求人工、真人客服、班主任或电话联系。',
      enabled: true,
    },
    {
      id: 'payment_issue',
      label: '支付订单异常',
      description: '客户已支付但看不到课程、订单异常、没收到课、要求退款或退费。',
      enabled: true,
    },
    {
      id: 'high_risk_complaint',
      label: '投诉或高风险负面',
      description: '客户表达投诉、举报、诈骗、欺骗、维权、辱骂或强烈不满。',
      enabled: true,
    },
  ],
  stop_ai_reply: true,
  stop_outreach: true,
  notify_message: '我这边帮您记录好了，稍等我看下具体情况~',
};
const courseSalesProfile = {
  course_name: '猿辅导英语自然拼读体验课/自然拼读集训营',
  price: '9元体验',
  lesson_count: '5天10节课',
  target_grade: '大班至小学4年级',
  schedule: '分两周进行：第一周五、周六；第二周五、周六、周日；晚上19:00-20:00；每天约60分钟。',
  replay: '3年内无限次回放，手机和平板都可以学习。',
  content: '5次绘本阅读实践、180次开口练习、360分钟配套视频，帮助孩子掌握自然拼读、口语发音和拼读规则。',
  selling_point: '见词能拼、听音能写；用拼读方法替代死记硬背；提升英语兴趣和发音基础。',
  gifts: '报名/完课活动可赠小猿篮球、护脊书包、小猿手办、宇航员文具盒、铅笔、转笔刀等，完课后随机发货其一。',
  after_purchase: '提醒添加指导老师/班主任，留意电话短信，下载猿辅导素养课APP查看课程和开课时间。',
};
const courseSalesProfiles = [
  {
    key: 'phonics',
    product_uuid: 'yuanfudao-phonics-course',
    name: '猿辅导自然拼读体验课',
    keywords: ['英语', '自然拼读', '拼读', '发音', '单词'],
    facts: courseSalesProfile,
  },
];
const courseResourceFaqs = [
  { question: '怎么听音频/怎么看答案', answer: '引导用户点击已推送的资源卡片，或重新扫码查看。', keywords: ['音频', '答案', '怎么看', '听力'] },
  { question: '验证码在哪里', answer: '提示验证码在书本封面或书上对应位置，主要用于验证正版，一码一书。', keywords: ['验证码', '正版', '码'] },
  { question: '扫码看答案', answer: '提示重新扫书上二维码；如果仍无法打开，引导使用答案小程序或资源卡片入口。', keywords: ['扫码', '二维码', '答案小程序'] },
  { question: '扫码后暂无资源', answer: '回复资源可能还在更新，请等待后台上传；如用户着急，收集图书二维码所在页清晰照片。', keywords: ['暂无资源', '没有资源', '打不开'] },
  { question: '资源不对', answer: '收集图书二维码所在页和有问题页面照片，记录后反馈处理。', keywords: ['资源不对', '不是这本', '错了'] },
  { question: '资料能不能下载', answer: '统一回复资料以在线查看为主，不支持直接下载；可打印资料按活动资料包说明引导。', keywords: ['下载', '打印', '保存'] },
  { question: '资源类问题是否转人工', answer: '常规资源问题不转人工，由AI直接处理；只有用户强烈投诉或AI无法判断时才转人工。', keywords: ['人工', '客服', '投诉'] },
];
const courseFaqs = [
  { intent: 'course_schedule', question: '什么时候上课', answer: '分两周上课，第一周五六、第二周五六日，晚上19点到20点；每天大概60分钟。没时间可以看回放，3年内无限次回放，手机平板都能学。', keywords: ['什么时候', '几点', '上课时间', '回放'] },
  { intent: 'course_intro', question: '这个是什么课/这是什么/你发是什么', answer: '猿辅导自然拼读课程，9元5天10节，适合大班到小学4年级，主要练自然拼读、绘本阅读和开口表达，内容会按孩子年级匹配。', keywords: ['什么课', '是什么', '自然拼读', '学什么'] },
  { intent: 'course_content', question: '学习内容', answer: '每个年级内容会按孩子情况匹配，核心是自然拼读、绘本阅读、口语发音和开口练习。可以先低成本体验一轮，看孩子适不适应。', keywords: ['学习内容', '内容', '学啥', '学什么'] },
  { intent: 'course_replay', question: '支持回放吗', answer: '支持回放的，3年内可以无限次看，手机和平板都能学。', keywords: ['回放', '没时间', '错过'] },
  { intent: 'course_conflict', question: '和其他课有冲突', answer: '不冲突的，这个更侧重教孩子拼读技巧和方法，支持回放，可以先让孩子试试看。', keywords: ['冲突', '没空', '上班', '时间'] },
  { intent: 'purchase', question: '要买/怎么买', answer: '点开报名链接，选择孩子年级，输入手机号验证，确认支付9元后把截图发我，我这边给您登记开课并发资料。', keywords: ['要买', '怎么买', '报名', '链接', '领取'] },
  { intent: 'purchased', question: '买了/已报名', answer: '谢谢支持，报名后会分配指导老师；您也可以先下载猿辅导素养课APP查看课程和开课时间，完课礼品后续联系班主任领取。', keywords: ['买了', '已报名', '支付', '付了', '截图'] },
  { intent: 'objection', question: '不买/考虑', answer: '没关系家长，这个主要是让孩子低成本体验自然拼读方法，9元压力也小。现在报名还有资料和完课礼，可以先试一轮看看是否适合。', keywords: ['考虑', '不买', '贵', '再说'] },
  { intent: 'gift', question: '赠品/资料', answer: '报名还独家赠送资料，完课后随机发实物礼品。具体礼品以班主任登记和活动规则为准。', keywords: ['赠品', '礼品', '资料', '篮球', '书包'] },
  { intent: 'grade', question: '适合几年级', answer: '这套自然拼读适合大班到小学4年级。如果孩子年级不在这个范围，我先帮您确认更适合的课程入口。', keywords: ['几年级', '大班', '一年级', '四年级', '初中'] },
  { intent: 'link_error', question: '链接打不开/页面异常', answer: '我帮您看下，麻烦截一下当前页面；也可以先退出重进，或复制链接到浏览器打开。', keywords: ['打不开', '白屏', '点不进去', '页面'] },
];
const courseSalesLinks = [
  {
    id: 'phonics_resource_card',
    title: '图书配套学习资源卡片',
    url: courseResourceCardLink,
    description: '首次打招呼发送，用于激活查看图书配套学习资源。',
    radar_enabled: false,
  },
  {
    id: 'phonics_radar_apply',
    title: '猿辅导自然拼读9元体验课报名通道',
    url: courseSalesSignupLink,
    description: '报名链接卡片：通过 tracking URL 记录打开并触发雷达跟进。',
    radar_enabled: true,
  },
];
const courseRadarConfig = {
  enabled: true,
  link_title: '猿辅导自然拼读9元体验课报名通道',
  link_url: courseSalesSignupLink,
  tracking_fields: ['session_id', 'campaign', 'clicked_at', 'browse_seconds', 'clicked_apply_button', 'paid'],
  rules: [
    { event: 'link_open', delay_minutes: 0, message: '家长，看您进入报名通道了，支付以后麻烦您发我支付成功截图或者报名成功短信，我给您登记开课并赠送资料。' },
    { event: 'browse_30s', min_browse_seconds: 30, delay_minutes: 3, message: '家长我看到您刚刚看了报名页，是年级选择、支付还是上课时间这块不确定？我可以直接帮您看。' },
    { event: 'click_apply_button', delay_minutes: 1, message: '您已经点到报名按钮了，下一步选择孩子年级并支付9元就行，成功后截图发我登记。' },
    { event: 'no_payment_after_click', delay_minutes: 15, message: '家长，刚才报名页如果没有支付成功，可能是年级没选对或链接卡住了，您把页面截图发我，我帮您看。' },
  ],
};
const courseStopRules = {
  stop_keywords: ['不需要', '不买', '不要再发', '再发投诉', '没有孩子', '不是目标年级', '我是老师', '已经学过'],
  stop_tags: ['已报名', '已下单', '付费', '投诉', '明确拒绝', '人工接管', '无孩子', '非目标年级', '老师', '已学过'],
  message: '好的家长，收到，不再打扰您了。后面有需要可以随时联系我。',
};
const courseStopPolicy = {
  explicit_rejection_threshold: 1,
  explicit_rejection_keywords: ['不需要', '不买', '不要', '不考虑', '没兴趣'],
  immediate_stop_keywords: ['投诉', '没有孩子', '没孩子', '打错', '我是老师'],
};
const courseImageBindings = [
  {
    step_id: 'gift_poster',
    title: '完课好礼海报',
    text: '表格内置素材：用户不买、考虑、问赠品、问完课礼时发送。不要再发送SOP截图。',
    file_key: 'course-sales/phonics/gift_poster.jpeg',
    trigger_intents: ['gift', 'objection', 'course_intro'],
    enabled: true,
  },
  {
    step_id: 'gift_qr',
    title: '书课通资料二维码',
    text: '表格内置素材：用户已报名/已支付后发送，引导长按识别关注，领取2026年最新幼小资源。',
    file_key: 'course-sales/phonics/gift_qr.jpeg',
    trigger_intents: ['purchased', 'resource_help', 'screenshot_help'],
    enabled: true,
  },
];
const courseFollowupSequences = [
  {
    stage: 'purchase',
    label: '要买/怎么买',
    messages: [
      { delay_minutes: 0, message: '好的', link_id: 'phonics_radar_apply', send_link_card: true },
      { delay_minutes: 0, message: '点开上面报名链接👆🏻支付9元成功了记添加一下班主任辅导老师微信，方便给孩子辅导不懂不会的家庭作业\n\n截图发下这边登记排课，把全科学习资料发给您', link_id: 'phonics_radar_apply' },
      { delay_minutes: 5, message: '家长领取到了吗？' },
      { delay_minutes: 60, message: '孩子家长，你好，这边您给小孩领取好了吗？因为后台的话，每个年级的名额都不多了。您没领的话，抽空领一下。' },
      { delay_minutes: 0, schedule_time: '21:30', message: '晚上好家长，忙完了么？现在方便给孩子预约下吗，赠送的名额还给您保留着呢。一直等您，辛苦您看到的话回复我一下吧~' },
    ],
  },
  {
    stage: 'purchased',
    label: '买了',
    messages: [
      { delay_minutes: 0, message: '谢谢支持 报名后会跳出一个微信二维码，是指导老师的，添加一下 老师会提醒你上课的哈，没添加也没关系，开课时老师也会主动联系你，留意下老师的电话和短信' },
      { delay_minutes: 0, message: '家长这个是赠送的资料。您可以长按识别关注一下，有空都可以打开学。', image_key: 'course-sales/phonics/gift_qr.jpeg' },
      { delay_minutes: 0, message: '实物的话，完课后 直接联系 猿辅导班主任就可以，想要什么私下和老师说哈' },
    ],
  },
  {
    stage: 'radar_clicked',
    label: '点雷达',
    messages: [
      { delay_minutes: 0, message: '家长，看您进入报名通道了，支付以后麻烦您发我支付成功截图或者报名成功的短信，我给您登记开课并赠送资料' },
      { delay_minutes: 0, message: '预约通道已经发给您了👆，支付成功以后截图给我哦，给您登记发赠课~', link_id: 'phonics_radar_apply', send_link_card: true },
      { delay_minutes: 5, message: '家长领取到了吗？' },
      { delay_minutes: 60, message: '孩子家长，你好，这边您给小孩领取好了吗？因为后台的话，每个年级的名额都不多了。您没领的话，抽空领一下。' },
      { delay_minutes: 0, schedule_time: '21:30', message: '晚上好家长，忙完了么？现在方便给孩子预约下吗，赠送的名额还给您保留着呢。一直等您，辛苦您看到的话回复我一下吧~' },
    ],
  },
];
const courseLongTermBroadcasts = [
  { day: 1, title: '第一天主打介绍', time: '10:05', message: '您好家长，再次打扰您了🤝 “9元共10节名师直播课”名额不多了，预约成功找我还免费赠送资料礼包。', image_key: '' },
  { day: 2, title: '第二天再次提醒', time: '10:05', message: '对了家长，猿辅导推出五天共10节语数英名师直播课，课程有回放，随时可以学，限前39名哦。', image_key: '' },
  { day: 3, title: '第三天最后确认', time: '10:05', message: '在嘛？家长，无论孩子体验不体验，给我个答复就行，优惠马上要截止了，我这边和您确定一下这个名额。', image_key: '' },
];

export function createCourseSalesWorkflowTemplate(): PipelineWorkflow {
  const modelUuid = '';
  const nodes: PipelineWorkflowNode[] = [
    workflowNode('start', 'start', '用户进线', '用户扫码、添加微信/企微或在网页咨询课程与图书资源', { x: 80, y: 320 }, { trigger: 'message' }),
    workflowNode('opening_message', 'custom', '首次开场白与资源卡片', '用户加好友/首次进线时先发开场白，再单独发送图书配套学习资源卡片', { x: 340, y: 320 }, {
      trigger: 'first_contact',
      message: courseOpeningMessage,
      link_id: 'phonics_resource_card',
      link_url: courseResourceCardLink,
      send_link_card: true,
      radar_enabled: false,
    }),
    workflowNode('channel', 'channel', '渠道接入', '统一接收网页、微信、企微、飞书等渠道消息', { x: 600, y: 320 }, { channels: ['web', 'wechat', 'wecom', 'lark'], keep_session: true }),
    workflowNode('media_router', 'media', '消息类型判断', '区分文字、截图/图片和语音', { x: 860, y: 320 }, {
      routes: [
        { when: 'has_text', target: 'text_input' },
        { when: 'has_voice', target: 'voice_asr' },
        { when: 'has_image', target: 'screenshot_input' },
      ],
    }),
    workflowNode('text_input', 'custom', '文字问题整理', '提取家长问题、孩子年级、是否点击链接、是否已报名', { x: 1160, y: 120 }, { output_key: 'user_text', params: '{"from": "message_chain.plain_text"}' }),
    workflowNode('voice_asr', 'asr', '语音输入处理', '用户发语音时先理解课程咨询内容，语音回复开关开启时可用语音回复', { x: 1160, y: 320 }, { provider: 'volcengine', model_uuid: 'lna-doubao-bigasr-flash', fallback_text: '用户发来课程咨询语音，请用文字短句回复。' }),
    workflowNode('screenshot_input', 'vision', '截图识别', '识别支付成功页、报名页、白屏、资源页或二维码页', { x: 1160, y: 520 }, { model_uuid: modelUuid, target_steps: ['gift_poster', 'gift_qr', 'link_error'] }),
    workflowNode('intent', 'intent', '意图识别', '识别资源、课程、购买、已报名、拒绝、投诉、雷达点击等状态', { x: 1460, y: 320 }, {
      intents: ['resource_help', 'course_intro', 'course_schedule', 'course_replay', 'course_content', 'purchase', 'purchased', 'objection', 'gift', 'radar_clicked', 'handoff', 'stop', 'screenshot_help'],
      confidence_threshold: 0.55,
      image_intents: ['screenshot_help', 'purchased', 'link_error'],
    }),
    workflowNode('stop_rules', 'condition', '停发规则', '已报名、投诉、拒绝、人工接管、无孩子等状态停止群发和促单', { x: 1740, y: 320 }, { ...courseStopRules, stop_policy: courseStopPolicy }),
    workflowNode('resource_faq', 'knowledge', '图书资源FAQ', '听力、答案、验证码、暂无资源、资源不对、下载等问题', { x: 2040, y: 80 }, { resource_faqs: courseResourceFaqs, knowledge_base_uuids: [], top_k: 5 }),
    workflowNode('course_faq', 'knowledge', '课程FAQ', '自然拼读课程介绍、上课时间、回放、赠品、冲突和年级适配', { x: 2040, y: 260 }, { course_faqs: courseFaqs, knowledge_base_uuids: [], top_k: 5 }),
    workflowNode('course_product', 'product', '课程产品库', '绑定猿辅导自然拼读体验课产品，输出价格、卖点、适龄和报名方式', { x: 2040, y: 440 }, { product_uuids: ['yuanfudao-phonics-course'], course_profile: courseSalesProfile, course_profiles: courseSalesProfiles }),
    workflowNode('sales_link', 'custom', '发送报名链接', '发送指定报名链接卡片，雷达链接自动包装 tracking URL', { x: 2340, y: 440 }, { links: courseSalesLinks, link_url: courseRadarConfig.link_url }),
    workflowNode('radar', 'radar', '链接点击雷达', '通过 tracking URL 回调感知链接打开，并按规则触发跟进', { x: 2640, y: 440 }, courseRadarConfig),
    workflowNode('radar_followup', 'outreach', '主动跟进话术矩阵', '按Excel跟进表在马上、5分钟、1小时、21:30主动跟进，必要时发送Excel素材图或报名链接卡片', { x: 2940, y: 440 }, { followup_sequences: courseFollowupSequences, radar_rules: courseRadarConfig.rules }),
    workflowNode('long_term_broadcast', 'outreach', 'SOP定时群发', '按SOP图片识别出的文字在每日10:05群发；不发送SOP图片', { x: 2640, y: 700 }, { broadcasts: courseLongTermBroadcasts, stop_rules: courseStopRules }),
    workflowNode('handoff', 'handoff', '转人工', '投诉、高风险、订单纠纷或人工主动介入后停止AI和群发', { x: 2040, y: 700 }, defaultHumanHandoff),
    workflowNode('reply', 'llm', '真人客服回复', '按SOP生成短句、明确、有下一步的课程客服/销售回复', { x: 3240, y: 320 }, {
      model_uuid: modelUuid,
      tone: '真人客服、短句、先服务后转化',
      prompt: '你是真人课程客服，先处理图书资源问题，再自然承接猿辅导自然拼读体验课咨询。回复要短、具体、有下一步动作。',
    }),
    workflowNode('end', 'end', '发送给用户', '发送文字、链接卡片、Excel素材图；用户语音咨询时可按配置追加语音回复', { x: 3540, y: 420 }, {}),
  ];

  const imagePositions = [
    { x: 2040, y: 40 },
    { x: 2040, y: 180 },
    { x: 2340, y: 40 },
    { x: 2340, y: 180 },
    { x: 2640, y: 40 },
    { x: 2640, y: 180 },
  ];
  courseImageBindings.forEach((binding, index) => {
    nodes.push(
      workflowNode(`image_${binding.step_id}`, 'image', binding.title, binding.text, imagePositions[index % imagePositions.length], {
        step_id: binding.step_id,
        file_key: binding.file_key,
        image_url: '',
        caption: binding.title,
        trigger_intents: binding.trigger_intents,
        append_caption: false,
        enabled: binding.enabled,
      }),
    );
  });

  const edges: PipelineWorkflowEdge[] = [
    workflowEdge('e-start-opening', 'start', 'opening_message'),
    workflowEdge('e-opening-channel', 'opening_message', 'channel'),
    workflowEdge('e-channel-media', 'channel', 'media_router'),
    workflowEdge('e-media-text', 'media_router', 'text_input', '文字'),
    workflowEdge('e-media-voice', 'media_router', 'voice_asr', '语音'),
    workflowEdge('e-media-image', 'media_router', 'screenshot_input', '截图/图片'),
    workflowEdge('e-text-intent', 'text_input', 'intent'),
    workflowEdge('e-voice-intent', 'voice_asr', 'intent'),
    workflowEdge('e-screenshot-intent', 'screenshot_input', 'intent'),
    workflowEdge('e-intent-stop', 'intent', 'stop_rules'),
    workflowEdge('e-stop-handoff', 'stop_rules', 'handoff', '投诉/接管'),
    workflowEdge('e-stop-resource', 'stop_rules', 'resource_faq', '资源问题'),
    workflowEdge('e-stop-course', 'stop_rules', 'course_faq', '课程问题'),
    workflowEdge('e-stop-product', 'stop_rules', 'course_product', '购买/课程承接'),
    workflowEdge('e-product-link', 'course_product', 'sales_link'),
    workflowEdge('e-link-radar', 'sales_link', 'radar'),
    workflowEdge('e-radar-followup', 'radar', 'radar_followup'),
    workflowEdge('e-radar-reply', 'radar_followup', 'reply'),
    workflowEdge('e-broadcast-reply', 'long_term_broadcast', 'reply'),
    workflowEdge('e-handoff-reply', 'handoff', 'reply'),
    workflowEdge('e-resource-reply', 'resource_faq', 'reply'),
    workflowEdge('e-course-reply', 'course_faq', 'reply'),
    workflowEdge('e-link-reply', 'sales_link', 'reply'),
    workflowEdge('e-reply-end', 'reply', 'end', '文字/图片/链接'),
  ];

  courseImageBindings.forEach((binding) => {
    const source = binding.step_id === 'gift_qr' ? 'course_faq' : 'course_product';
    const imageNodeId = `image_${binding.step_id}`;
    edges.push(
      workflowEdge(`e-${source}-${imageNodeId}`, source, imageNodeId),
      workflowEdge(`e-${imageNodeId}-reply`, imageNodeId, 'reply'),
    );
  });

  const workflow: PipelineWorkflow = {
    version: 1,
    name: '课程销售模板',
    scenario: 'sales',
    metadata: {
      scenario: 'course_sales_yuanfudao_phonics',
      runtime_engine: 'langgraph',
      source_mode: 'template',
      template_name: '课程销售模板',
      source: 'SOP.doc（群发截图转文字）+ 猿辅导自然拼读常见问题(1).xlsx',
      tts_provider: 'volcengine',
      langgraph_state: {
        messages: 'list',
        intent: 'dict',
        customer_stage: 'str',
        radar_event: 'dict',
        selected_assets: 'list',
        outreach_plan: 'dict',
      },
    },
    voice: {
      model_uuid: 'lnv-doubao-seed-tts-2-0-standard',
      provider: 'volcengine',
      enabled: true,
      voice_type: 'zh_female_vv_uranus_bigtts',
      encoding: 'mp3',
    },
    nodes,
    edges,
    variables: {
      customer_stage: 'resource_service',
      intent: '',
      opening_message: courseOpeningMessage,
      radar_event: {},
      selected_product_uuid: 'yuanfudao-phonics-course',
      course_profile: courseSalesProfile,
      course_profiles: courseSalesProfiles,
      source_materials: ['SOP.doc（群发截图转文字）', '猿辅导自然拼读常见问题(1).xlsx'],
      resource_faqs: courseResourceFaqs,
      course_faqs: courseFaqs,
      sales_links: courseSalesLinks,
      radar: courseRadarConfig,
      followup_sequences: courseFollowupSequences,
      long_term_broadcasts: courseLongTermBroadcasts,
      human_handoff: defaultHumanHandoff,
      special_cases: [],
      stop_rules: courseStopRules,
      stop_policy: courseStopPolicy,
      image_text_bindings: courseImageBindings,
    },
  };

  if (workflow.nodes.length !== 21 || workflow.edges.length !== 28) {
    throw new Error('Course sales workflow template must keep 21 nodes and 28 edges.');
  }

  return workflow;
}

export function createDefaultWorkflow(): PipelineWorkflow {
  return createBlankWorkflow();
}

export function createBlankAgentTemplateConfig(): PipelineTemplateConfig {
  return {
    name: '',
    role_prompt: '',
    opening_message: '',
    recommended_questions: [],
    model_uuid: '',
    max_reasoning_steps: 0,
    reference_rounds: 0,
    response_diversity: 0.3,
    knowledge_base_uuids: [],
    product_uuids: [],
    sales_links: [],
    radar: {
      enabled: false,
      link_title: '',
      link_url: '',
      tracking_fields: [],
      rules: [],
    },
    followup_sequences: [],
    long_term_broadcasts: [],
    course_profiles: [],
    source_materials: [],
    stop_rules: {
      stop_keywords: [],
      stop_tags: [],
      message: '',
    },
    stop_policy: {
      explicit_rejection_threshold: 1,
      explicit_rejection_keywords: [],
      immediate_stop_keywords: [],
    },
    tools: {
      intent_recognition: false,
      knowledge_base: false,
      product_database: false,
      image_recognition: false,
      voice_reply: false,
    },
    reply_controls: {
      multi_reply_enabled: false,
      merge_reply_enabled: true,
      merge_delay_seconds: 10,
    },
    memory: {
      variables_enabled: false,
      table_enabled: false,
      segments_enabled: false,
    },
    voice: {
      model_uuid: '',
      provider: '',
      enabled: false,
      voice_type: '',
      encoding: '',
    },
    asr: {
      model_uuid: '',
      provider: '',
      fallback_text: '用户发来一条语音咨询，请用短句回复。',
    },
    scheduled_push: {
      enabled: false,
      mode: 'daily',
      time: '',
      single_date: '',
      message: '',
      push_message: '',
    },
    interaction_radar: {
      enabled: false,
      link_url: '',
      click_reply: '',
    },
    human_handoff: {
      ...defaultHumanHandoff,
      enabled: false,
      keywords: [],
      semantic_triggers: defaultHumanHandoff.semantic_triggers.map((trigger) => ({
        ...trigger,
        enabled: false,
      })),
      notify_message: '',
    },
    special_cases: [],
    image_text_bindings: [],
  };
}

export function createTaskAssistantTemplateConfig(): PipelineTemplateConfig {
  const bindings = [
    ['download_qr', '下载安装第一步', '先用支付宝扫码，进入蚂蚁阿福下载页，点击下载按钮。', 'task-assistant/ant-af/af_step_01.png'],
    ['app_store_download', '应用商店下载', '跳到应用商店后确认是蚂蚁阿福，点击下载并等待安装完成。', 'task-assistant/ant-af/af_step_02.png'],
    ['alipay_login', '支付宝一键登录', '打开 App 后点击支付宝一键登录。', 'task-assistant/ant-af/af_step_03.png'],
    ['alipay_login_confirm', '同意支付宝授权', '在支付宝授权页确认申请方，点击同意完成登录。', 'task-assistant/ant-af/af_step_04.png'],
    ['open_profile', '进入个人中心', '登录后点击左上角头像或菜单，进入个人中心。', 'task-assistant/ant-af/af_step_05.png'],
    ['open_settings', '进入设置', '在个人中心点击用户信息区域或设置入口，进入我的/设置页面。', 'task-assistant/ant-af/af_step_06.png'],
    ['open_real_person_verify', '点击实名认证', '在我的页面找到实名认证并进入，若显示已认证说明这步完成。', 'task-assistant/ant-af/af_step_07.png'],
    ['import_identity', '支付宝导入身份信息', '在认证页面点击支付宝一键导入，按支付宝提示完成授权。', 'task-assistant/ant-af/af_step_08.png'],
  ];

  return {
    name: '任务助手模板配置版',
    role_prompt: '你是真人客服，负责一步步引导用户完成蚂蚁阿福实名认证。回复要短、自然、像真人，不要自称 AI、机器人或任务助手。',
    opening_message: '我带你一步步完成实名认证。先用支付宝扫码下载蚂蚁阿福 App，完成后跟我说“下一步”。',
    recommended_questions: ['我应该怎么完成这个任务？', '我卡在这一步了怎么办？', '下一步怎么做？'],
    model_uuid: '',
    max_reasoning_steps: 2,
    reference_rounds: 2,
    response_diversity: 0.3,
    knowledge_base_uuids: [],
    product_uuids: [],
    sales_links: [],
    radar: {
      enabled: false,
      link_title: '',
      link_url: '',
      tracking_fields: [],
      rules: [],
    },
    followup_sequences: [],
    long_term_broadcasts: [],
    stop_rules: {
      stop_keywords: [],
      stop_tags: [],
      message: '',
    },
    tools: {
      intent_recognition: true,
      knowledge_base: true,
      product_database: true,
      image_recognition: true,
      voice_reply: true,
    },
    reply_controls: {
      multi_reply_enabled: false,
      merge_reply_enabled: true,
      merge_delay_seconds: 10,
    },
    memory: {
      variables_enabled: true,
      table_enabled: true,
      segments_enabled: false,
    },
    voice: {
      model_uuid: '',
      provider: 'volcengine',
      enabled: true,
      voice_type: 'zh_female_yuanqinvyou_moon_bigtts',
      encoding: 'ogg_opus',
    },
    asr: {
      model_uuid: 'lna-doubao-bigasr-flash',
      provider: 'volcengine',
      fallback_text: '用户发来一条语音咨询，请用短句回复。',
    },
    scheduled_push: {
      enabled: true,
      mode: 'daily',
      time: '10:00',
      single_date: '',
      message: '你好，今天继续完成蚂蚁阿福实名认证任务，有卡住的页面直接发截图给我。',
      push_message: '你好，今天继续完成蚂蚁阿福实名认证任务，有卡住的页面直接发截图给我。',
    },
    interaction_radar: {
      enabled: false,
      link_url: '',
      click_reply: '我看到您刚刚点开了链接，如果有不清楚的地方可以直接问我。',
    },
    human_handoff: {
      ...defaultHumanHandoff,
      enabled: false,
      notify_message: '我这边帮您记录好了，稍等我看下具体情况~',
    },
    special_cases: [
      {
        id: 'phonics-listening-answer-card',
        enabled: true,
        condition: '用户在问书籍二维码里的听力、答案、音频或扫码资源怎么打开、怎么听、在哪里看。',
        reply: '书籍二维码听力/答案，点击上面推送的【点击访问扫码前的资源】卡片。',
        ai_rewrite: true,
        file_key: '',
        image_url: '',
      },
    ],
    image_text_bindings: bindings.map(([step_id, title, text, file_key]) => ({
      step_id,
      title,
      text,
      file_key,
      enabled: true,
      trigger_intents: ['task_overview', 'screenshot_help'],
    })),
  };
}

export function applyTemplateConfigToWorkflow(
  templateConfig: PipelineTemplateConfig,
  workflow: PipelineWorkflow,
): PipelineWorkflow {
  const bindingByStepId = new Map(
    templateConfig.image_text_bindings.map((binding) => [binding.step_id, binding]),
  );
  return {
    ...workflow,
    name: templateConfig.name || workflow.name,
    special_cases: templateConfig.special_cases || [],
    metadata: {
      ...(workflow.metadata || {}),
      source_mode: 'template',
      template_name: templateConfig.name,
    },
    voice: {
      ...(workflow.voice || {}),
      ...templateConfig.voice,
    },
    nodes: workflow.nodes.map((node) => {
      const stepId = typeof node.config?.step_id === 'string' ? node.config.step_id : '';
      const binding = bindingByStepId.get(stepId);
      const nextNode: PipelineWorkflowNode = {
        ...node,
        config: { ...node.config },
      };
      if (node.type === 'llm' || node.type === 'vision') {
        nextNode.config.model_uuid = templateConfig.model_uuid;
      }
      if (node.type === 'voice') {
        nextNode.config = { ...nextNode.config, ...templateConfig.voice };
      }
      if (node.type === 'asr') {
        nextNode.config = {
          ...nextNode.config,
          model_uuid: templateConfig.asr?.model_uuid || '',
          provider: templateConfig.asr?.provider || nextNode.config.provider,
          fallback_text:
            templateConfig.asr?.fallback_text || nextNode.config.fallback_text,
        };
      }
      if (binding && node.type === 'task') {
        nextNode.title = binding.title;
        nextNode.description = binding.text;
        nextNode.config.instruction = binding.text;
        nextNode.config.enabled = binding.enabled !== false;
      }
      if (binding && node.type === 'image') {
        nextNode.title = binding.title;
        nextNode.description = binding.text;
        nextNode.config.file_key = binding.file_key;
        nextNode.config.image_url = binding.image_url || '';
        nextNode.config.caption = binding.title;
        nextNode.config.enabled = binding.enabled !== false;
      }
      return nextNode;
    }),
    variables: {
      ...(workflow.variables || {}),
      scheduled_push: templateConfig.scheduled_push,
      interaction_radar: templateConfig.interaction_radar,
      human_handoff: templateConfig.human_handoff,
      special_cases: templateConfig.special_cases || [],
      opening_message: templateConfig.opening_message,
      recommended_questions: templateConfig.recommended_questions,
      sales_links: templateConfig.sales_links || [],
      radar: templateConfig.radar,
      followup_sequences: templateConfig.followup_sequences || [],
      long_term_broadcasts: templateConfig.long_term_broadcasts || [],
      course_profiles: templateConfig.course_profiles || [],
      source_materials: templateConfig.source_materials || [],
      stop_rules: templateConfig.stop_rules,
      stop_policy: templateConfig.stop_policy,
    },
  };
}

export function getNodeDefaults(type: WorkflowNodeType) {
  return nodeDefaults[type];
}
