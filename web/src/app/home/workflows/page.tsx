import { useMemo, useState, type ElementType, type ReactNode } from 'react';
import {
  Bell,
  BookOpen,
  Bot,
  Brain,
  Cable,
  CheckCircle2,
  CircleDot,
  Clock3,
  Eye,
  GitBranch,
  Handshake,
  Image as ImageIcon,
  ListChecks,
  MessageSquare,
  MousePointerClick,
  PackageSearch,
  Play,
  Plug,
  Plus,
  Search,
  Send,
  Sparkles,
  Tags,
  UserRoundCheck,
  Volume2,
  Workflow,
  Wrench,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

type WorkflowNodeType =
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

type CanvasNode = {
  id: string;
  type: WorkflowNodeType;
  title: string;
  description: string;
  config?: Record<string, string | string[]>;
};

type WorkflowTemplate = {
  id: 'sales' | 'operations';
  icon: ReactNode;
  name: string;
  description: string;
  trigger: string;
  highlights: string[];
  nodes: CanvasNode[];
};

type WorkflowStep = 'template' | 'settings' | 'canvas';

const nodeMeta: Record<
  WorkflowNodeType,
  {
    label: string;
    group: string;
    icon: ElementType;
    accent: string;
    description: string;
  }
> = {
  start: {
    label: '入口触发',
    group: '入口',
    icon: MessageSquare,
    accent: 'border-sky-200 bg-sky-50 text-sky-700',
    description: '客户发送消息、进入阶段或定时任务触发 Workflow。',
  },
  channel: {
    label: '渠道接入',
    group: '入口',
    icon: Cable,
    accent: 'border-cyan-200 bg-cyan-50 text-cyan-700',
    description: '统一接收网页、微信、企微、飞书等渠道消息。',
  },
  media: {
    label: '消息类型判断',
    group: '入口',
    icon: GitBranch,
    accent: 'border-slate-200 bg-slate-50 text-slate-700',
    description: '区分文字、图片、语音和文件，进入不同处理链路。',
  },
  asr: {
    label: '语音输入处理',
    group: 'AI',
    icon: Volume2,
    accent: 'border-pink-200 bg-pink-50 text-pink-700',
    description: '把客户语音转成可理解的文本上下文。',
  },
  intent: {
    label: '意图识别',
    group: 'AI',
    icon: Brain,
    accent: 'border-violet-200 bg-violet-50 text-violet-700',
    description: '识别咨询、报价、售后、投诉、转人工等意图。',
  },
  router: {
    label: '意图路由',
    group: '控制',
    icon: GitBranch,
    accent: 'border-slate-200 bg-slate-50 text-slate-700',
    description: '按意图或条件把会话送到不同节点。',
  },
  knowledge: {
    label: '查询知识库',
    group: '资料',
    icon: BookOpen,
    accent: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    description: '检索知识库资料，给 AI Agent 提供回答依据。',
  },
  product: {
    label: '匹配产品',
    group: '资料',
    icon: PackageSearch,
    accent: 'border-amber-200 bg-amber-50 text-amber-800',
    description: '结合产品库、卖点和客户需求推荐合适方案。',
  },
  task: {
    label: '任务步骤',
    group: '运营',
    icon: ListChecks,
    accent: 'border-blue-200 bg-blue-50 text-blue-700',
    description: '配置任务拆解、完成条件和每一步操作说明。',
  },
  vision: {
    label: '截图识别',
    group: '运营',
    icon: Eye,
    accent: 'border-purple-200 bg-purple-50 text-purple-700',
    description: '识别客户截图所在步骤，并给出下一步引导。',
  },
  llm: {
    label: 'AI 回复',
    group: 'AI',
    icon: Bot,
    accent: 'border-indigo-200 bg-indigo-50 text-indigo-700',
    description: '调用 AI Agent 生成回复、推荐话术或线索摘要。',
  },
  condition: {
    label: '条件分流',
    group: '控制',
    icon: GitBranch,
    accent: 'border-slate-200 bg-slate-50 text-slate-700',
    description: '按意图、置信度、客户阶段或执行结果分支。',
  },
  lead: {
    label: '收集线索',
    group: '销售',
    icon: UserRoundCheck,
    accent: 'border-rose-200 bg-rose-50 text-rose-700',
    description: '记录姓名、电话、预算、需求和跟进时间。',
  },
  image: {
    label: '发送图片/素材',
    group: '素材',
    icon: ImageIcon,
    accent: 'border-cyan-200 bg-cyan-50 text-cyan-700',
    description: '按意图发送产品图、报价图、二维码、海报或步骤截图。',
  },
  memory: {
    label: '更新客户记忆',
    group: '资料',
    icon: Tags,
    accent: 'border-lime-200 bg-lime-50 text-lime-700',
    description: '沉淀客户阶段、兴趣产品、标签和对话摘要。',
  },
  outreach: {
    label: '定时跟进',
    group: '销售',
    icon: Bell,
    accent: 'border-orange-200 bg-orange-50 text-orange-700',
    description: '创建销售触达计划或运营定时提醒。',
  },
  handoff: {
    label: '人工介入',
    group: '客服',
    icon: Handshake,
    accent: 'border-red-200 bg-red-50 text-red-700',
    description: '把客户送入人工接待队列，并附带上下文摘要。',
  },
  http: {
    label: 'HTTP 请求',
    group: '工具',
    icon: Cable,
    accent: 'border-zinc-200 bg-zinc-50 text-zinc-700',
    description: '调用外部 CRM、订单、线索或内部系统接口。',
  },
  plugin: {
    label: '插件工具',
    group: '工具',
    icon: Plug,
    accent: 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700',
    description: '调用已安装插件提供的业务能力。',
  },
  mcp: {
    label: 'MCP 工具',
    group: '工具',
    icon: Wrench,
    accent: 'border-teal-200 bg-teal-50 text-teal-700',
    description: '调用已配置 MCP 服务，让 Agent 使用外部工具。',
  },
  voice: {
    label: '语音回复',
    group: '素材',
    icon: Volume2,
    accent: 'border-pink-200 bg-pink-50 text-pink-700',
    description: '把文字回复转换成语音消息。',
  },
  custom: {
    label: '自定义动作',
    group: '自定义',
    icon: Sparkles,
    accent: 'border-stone-200 bg-stone-50 text-stone-700',
    description: '无代码参数化动作，适合临时扩展。',
  },
  end: {
    label: '结束',
    group: '出口',
    icon: Send,
    accent: 'border-green-200 bg-green-50 text-green-700',
    description: '发送最终消息、记录结果并结束 Workflow。',
  },
};

const nodeOrder: WorkflowNodeType[] = [
  'start',
  'channel',
  'media',
  'asr',
  'intent',
  'router',
  'knowledge',
  'product',
  'task',
  'vision',
  'llm',
  'condition',
  'lead',
  'image',
  'memory',
  'outreach',
  'handoff',
  'http',
  'plugin',
  'mcp',
  'voice',
  'custom',
  'end',
];

function createNode(
  type: WorkflowNodeType,
  title?: string,
  description?: string,
  config?: CanvasNode['config'],
): CanvasNode {
  return {
    id: `${type}-${Math.random().toString(16).slice(2, 8)}`,
    type,
    title: title || nodeMeta[type].label,
    description: description || nodeMeta[type].description,
    config,
  };
}

function createBlankNodes(): CanvasNode[] {
  return [
    createNode('start', '开始', '流程入口'),
    createNode('end', '结束', '流程结束'),
  ];
}

const workflowTemplates: WorkflowTemplate[] = [
  {
    id: 'sales',
    icon: <UserRoundCheck className="size-5" />,
    name: '销售 Workflow',
    description:
      '承接客户咨询、识别购买意图、推荐产品、收集线索，并在高意向时转人工。',
    trigger: '客户发送消息或命中销售关键词',
    highlights: ['意图识别', '产品匹配', '线索收集', '转人工', '定时跟进'],
    nodes: [
      createNode('start', '收到客户消息', '客户进入销售咨询会话'),
      createNode('intent', '识别销售意图', '识别咨询、询价、对比、购买、转人工等信号', {
        threshold: '0.72',
        intents: ['咨询产品', '询价报价', '购买意向', '转人工'],
      }),
      createNode('product', '匹配产品', '根据客户需求匹配产品库和卖点'),
      createNode('knowledge', '查询销售知识', '检索销售话术、常见异议和活动规则'),
      createNode('llm', '调用售前 AI Agent', '生成推荐回复、报价口径和下一步动作'),
      createNode('condition', '判断是否高意向', '按预算、报价、合同、电话等信号分流'),
      createNode('image', '发送产品素材', '发送产品图、报价图、二维码或活动海报'),
      createNode('lead', '收集线索', '记录姓名、电话、预算、需求和跟进时间'),
      createNode('handoff', '人工介入', '把高意向客户交接给销售团队'),
      createNode('memory', '更新客户记忆', '沉淀客户阶段、兴趣产品和摘要'),
      createNode('outreach', '定时跟进', '生成后续触达计划'),
      createNode('end', '结束', '记录销售流程结果'),
    ],
  },
  {
    id: 'operations',
    icon: <ListChecks className="size-5" />,
    name: '运营 Workflow',
    description:
      '承接运营活动、任务助手、素材触达、截图识别、语音回复和定时推送。',
    trigger: '客户进入运营任务或触达计划',
    highlights: ['任务步骤', '截图识别', '素材发送', '语音回复', '定时推送'],
    nodes: [
      createNode('start', '进入运营任务', '客户进入活动、任务或触达计划'),
      createNode('channel', '渠道接入', '统一接收网页、微信、企微、飞书等渠道消息'),
      createNode('media', '消息类型判断', '识别文字、图片、语音和文件'),
      createNode('asr', '语音输入处理', '把语音消息转成文本上下文'),
      createNode('task', '任务步骤', '拆解运营任务，并记录每一步完成条件'),
      createNode('vision', '截图识别', '识别用户截图所在步骤，并给出下一步'),
      createNode('knowledge', '查询运营知识', '检索活动规则、任务说明和常见问题'),
      createNode('llm', '调用运营 AI Agent', '生成自然、简短、可执行的引导话术'),
      createNode('image', '发送图片/素材', '发送步骤图、二维码、海报或产品素材'),
      createNode('voice', '语音回复', '把关键引导转换成语音消息'),
      createNode('outreach', '定时推送', '按日程提醒用户继续完成任务'),
      createNode('memory', '更新客户记忆', '记录任务进度、卡点和客户偏好'),
      createNode('handoff', '人工介入', '复杂问题或投诉进入人工处理'),
      createNode('end', '结束', '记录运营任务结果'),
    ],
  },
];

const blockLibrary = nodeOrder
  .filter((type) => type !== 'start' && type !== 'end')
  .map((type) => createNode(type));

const sampleWorkflows = [
  {
    name: '销售 Workflow',
    runs: 42,
    updatedAt: '今天 15:10',
  },
  {
    name: '运营 Workflow',
    runs: 0,
    updatedAt: '昨天 17:48',
  },
];

function StepPill({
  step,
  current,
  label,
}: {
  step: WorkflowStep;
  current: WorkflowStep;
  label: string;
}) {
  const order: WorkflowStep[] = ['template', 'settings', 'canvas'];
  const currentIndex = order.indexOf(current);
  const index = order.indexOf(step);
  const done = index < currentIndex;
  const active = step === current;

  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className={cn(
          'flex size-7 items-center justify-center rounded-full border text-xs font-semibold',
          done && 'border-emerald-200 bg-emerald-50 text-emerald-700',
          active && 'border-blue-600 bg-blue-600 text-white',
          !done && !active && 'border-slate-200 bg-white text-slate-400',
        )}
      >
        {done ? <CheckCircle2 className="size-4" /> : index + 1}
      </span>
      <span
        className={cn(
          active ? 'font-semibold text-slate-950' : 'text-slate-500',
        )}
      >
        {label}
      </span>
    </div>
  );
}

function NodeIcon({ type }: { type: WorkflowNodeType }) {
  const Icon = nodeMeta[type].icon;
  return <Icon className="size-4" />;
}

function TemplateCard({
  template,
  selected,
  onSelect,
}: {
  template: WorkflowTemplate;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'flex min-h-44 w-full flex-col items-start gap-3 rounded-lg border bg-white p-5 text-left transition',
        selected
          ? 'border-blue-500 shadow-sm ring-2 ring-blue-100'
          : 'border-slate-200 hover:border-slate-300 hover:shadow-sm',
      )}
    >
      <span className="rounded-md bg-blue-50 p-2 text-blue-600">
        {template.icon}
      </span>
      <div>
        <div className="text-lg font-semibold text-slate-950">
          {template.name}
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          {template.description}
        </p>
      </div>
      <div className="mt-auto flex flex-wrap gap-2">
        {template.highlights.map((item) => (
          <Badge
            key={item}
            variant="outline"
            className="border-blue-100 bg-blue-50 text-blue-700"
          >
            {item}
          </Badge>
        ))}
      </div>
    </button>
  );
}

function CanvasNodeCard({
  node,
  selected,
  onSelect,
}: {
  node: CanvasNode;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'w-72 rounded-lg border bg-white text-left shadow-sm transition',
        selected && 'ring-2 ring-blue-200',
      )}
    >
      <div
        className={cn(
          'flex items-center gap-2 rounded-t-lg border-b px-4 py-3 text-sm font-semibold',
          nodeMeta[node.type].accent,
        )}
      >
        <NodeIcon type={node.type} />
        {node.title}
      </div>
      <div className="p-4">
        <p className="text-sm leading-6 text-slate-600">{node.description}</p>
        <Badge variant="outline" className="mt-3 text-xs">
          {nodeMeta[node.type].group}
        </Badge>
      </div>
    </button>
  );
}

export default function WorkflowsPage() {
  const [mode, setMode] = useState<'list' | 'create'>('list');
  const [step, setStep] = useState<WorkflowStep>('template');
  const [selectedTemplateId, setSelectedTemplateId] =
    useState<WorkflowTemplate['id']>('sales');
  const selectedTemplate = useMemo(
    () =>
      workflowTemplates.find(
        (template) => template.id === selectedTemplateId,
      ) || workflowTemplates[0],
    [selectedTemplateId],
  );
  const [workflowName, setWorkflowName] = useState(selectedTemplate.name);
  const [workflowDescription, setWorkflowDescription] = useState(
    selectedTemplate.description,
  );
  const [nodes, setNodes] = useState<CanvasNode[]>(selectedTemplate.nodes);
  const [selectedNodeId, setSelectedNodeId] = useState(nodes[0]?.id || '');
  const [nodeQuery, setNodeQuery] = useState('');
  const selectedNode =
    nodes.find((node) => node.id === selectedNodeId) || nodes[0];

  const visibleBlocks = blockLibrary.filter((block) => {
    const keyword = nodeQuery.trim().toLowerCase();
    if (!keyword) return true;
    return `${block.title} ${block.description} ${nodeMeta[block.type].group}`
      .toLowerCase()
      .includes(keyword);
  });
  const blockGroups = Array.from(
    new Set(visibleBlocks.map((block) => nodeMeta[block.type].group)),
  );

  function selectTemplate(template: WorkflowTemplate) {
    setSelectedTemplateId(template.id);
    setWorkflowName(template.name);
    setWorkflowDescription(template.description);
    setNodes(template.nodes);
    setSelectedNodeId(template.nodes[0]?.id || '');
  }

  function startBlankWorkflow() {
    const blankNodes = createBlankNodes();
    setWorkflowName('自定义 Workflow');
    setWorkflowDescription('默认只有开始和结束节点，由运营自行添加步骤。');
    setNodes(blankNodes);
    setSelectedNodeId(blankNodes[0].id);
    setStep('canvas');
  }

  function addNode(block: CanvasNode) {
    const endNode = nodes[nodes.length - 1];
    const beforeEnd = nodes.slice(0, -1);
    const newNode = {
      ...block,
      id: `${block.type}-${Date.now()}`,
    };
    setNodes([...beforeEnd, newNode, endNode]);
    setSelectedNodeId(newNode.id);
  }

  function nextStep() {
    if (step === 'template') {
      setStep('settings');
      return;
    }
    if (step === 'settings') {
      setStep('canvas');
    }
  }

  if (mode === 'list') {
    return (
      <div className="h-full overflow-y-auto bg-slate-50 p-4 text-slate-900">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-4">
          <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-slate-950">
                Workflow
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                设计客户消息进入系统后的自动化流程。Workflow 决定什么时候触发、按什么步骤执行、在哪一步调用 AI Agent，并承接原流水线的节点能力。
              </p>
            </div>
            <Button onClick={() => setMode('create')}>
              <Plus className="size-4" />
              创建 Workflow
            </Button>
          </div>

          <section className="rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-200 p-4">
              <div className="relative max-w-md flex-1">
                <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                <Input className="pl-9" placeholder="搜索流程名称或场景" />
              </div>
            </div>
            <div className="divide-y divide-slate-100">
              {sampleWorkflows.map((workflow) => (
                <div
                  key={workflow.name}
                  className="grid gap-3 p-4 md:grid-cols-[1.2fr_1fr_0.6fr_0.6fr]"
                >
                  <div>
                    <div className="font-semibold text-slate-950">
                      {workflow.name}
                    </div>
                  </div>
                  <div className="text-sm text-slate-600">
                    今日执行 {workflow.runs} 次
                  </div>
                  <div className="text-sm text-slate-600">
                    {workflow.updatedAt}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setMode('create')}
                  >
                    编辑
                  </Button>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden bg-slate-50 text-slate-900">
      <div className="flex h-full min-h-0 flex-col">
        <header className="flex shrink-0 flex-col gap-4 border-b border-slate-200 bg-white px-5 py-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">
              自动化流程
            </p>
            <h1 className="text-2xl font-semibold text-slate-950">
              创建 Workflow
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-5">
            <StepPill step="template" current={step} label="选择模板" />
            <StepPill step="settings" current={step} label="流程设置" />
            <StepPill step="canvas" current={step} label="画布编辑" />
            <Button variant="outline" onClick={() => setMode('list')}>
              返回列表
            </Button>
            <Button onClick={step === 'canvas' ? undefined : nextStep}>
              {step === 'canvas' ? '发布 Workflow' : '下一步'}
            </Button>
          </div>
        </header>

        {step === 'template' && (
          <main className="min-h-0 flex-1 overflow-y-auto p-5">
            <div className="mx-auto grid max-w-[1500px] gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
              <section>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <h2 className="text-xl font-semibold text-slate-950">
                      Workflow 模板
                    </h2>
                    <p className="mt-1 text-sm text-slate-500">
                      模板只保留销售和运营两类；需要完全自定义时，可直接从空白画布开始。
                    </p>
                  </div>
                  <Button variant="outline" onClick={startBlankWorkflow}>
                    <Workflow className="size-4" />
                    从空白画布开始
                  </Button>
                </div>
                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  {workflowTemplates.map((template) => (
                    <TemplateCard
                      key={template.id}
                      template={template}
                      selected={selectedTemplateId === template.id}
                      onSelect={() => selectTemplate(template)}
                    />
                  ))}
                </div>
              </section>
              <aside className="rounded-lg border border-slate-200 bg-white p-5">
                <div className="mb-5 flex items-center gap-3">
                  <span className="rounded-lg bg-blue-50 p-3 text-blue-600">
                    {selectedTemplate.icon}
                  </span>
                  <div>
                    <h3 className="font-semibold text-slate-950">
                      {selectedTemplate.name}
                    </h3>
                    <p className="text-sm text-slate-500">
                      {selectedTemplate.trigger}
                    </p>
                  </div>
                </div>
                <label className="text-sm font-medium text-slate-700">
                  流程名称
                </label>
                <Input
                  className="mt-2"
                  value={workflowName}
                  onChange={(event) => setWorkflowName(event.target.value)}
                />
                <label className="mt-4 block text-sm font-medium text-slate-700">
                  流程描述
                </label>
                <Textarea
                  className="mt-2 min-h-28"
                  value={workflowDescription}
                  onChange={(event) =>
                    setWorkflowDescription(event.target.value)
                  }
                />
                <div className="mt-5 rounded-lg border border-slate-200 p-4">
                  <h4 className="font-semibold text-slate-950">
                    生成的流程节点
                  </h4>
                  <div className="mt-3 space-y-2">
                    {selectedTemplate.nodes.map((node, index) => (
                      <div
                        key={node.id}
                        className="flex items-center gap-3 text-sm text-slate-600"
                      >
                        <span className="flex size-6 items-center justify-center rounded-full bg-blue-50 text-xs font-semibold text-blue-600">
                          {index + 1}
                        </span>
                        {node.title}
                      </div>
                    ))}
                  </div>
                </div>
              </aside>
            </div>
          </main>
        )}

        {step === 'settings' && (
          <main className="min-h-0 flex-1 overflow-y-auto p-5">
            <div className="mx-auto max-w-4xl space-y-5">
              <div>
                <h2 className="text-xl font-semibold text-slate-950">
                  流程设置
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  设置 Workflow 的基础信息、触发方式、生效范围和旧流水线迁移过来的高级能力。
                </p>
              </div>
              <section className="rounded-lg border border-slate-200 bg-white p-5">
                <h3 className="font-semibold text-slate-950">基础信息</h3>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <div className="md:col-span-2">
                    <label className="text-sm font-medium text-slate-700">
                      流程名称
                    </label>
                    <Input
                      className="mt-2"
                      value={workflowName}
                      onChange={(event) => setWorkflowName(event.target.value)}
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="text-sm font-medium text-slate-700">
                      流程描述
                    </label>
                    <Textarea
                      className="mt-2 min-h-24"
                      value={workflowDescription}
                      onChange={(event) =>
                        setWorkflowDescription(event.target.value)
                      }
                    />
                  </div>
                </div>
              </section>

              <section className="rounded-lg border border-slate-200 bg-white p-5">
                <h3 className="font-semibold text-slate-950">触发方式</h3>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {[
                    ['客户发送消息时', '客户进入会话后自动检查流程条件。'],
                    ['命中特定关键词时', '例如价格、报价、试用、转人工。'],
                    ['客户进入某个阶段时', '例如新线索、高意向、待跟进。'],
                    ['定时触发', '适合沉默客户跟进和运营触达。'],
                  ].map(([title, desc], index) => (
                    <div
                      key={title}
                      className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 p-4"
                    >
                      <div>
                        <p className="font-medium text-slate-950">{title}</p>
                        <p className="mt-1 text-sm text-slate-500">{desc}</p>
                      </div>
                      <Switch defaultChecked={index < 2} />
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-lg border border-slate-200 bg-white p-5">
                <h3 className="font-semibold text-slate-950">高级能力</h3>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {[
                    ['客户记忆', '把客户阶段、兴趣产品和任务进度沉淀为变量。'],
                    ['外部工具', '通过 HTTP、插件、MCP 调用 CRM、订单和内部系统。'],
                    ['素材触达', '发送图片、步骤截图、语音和定时提醒。'],
                  ].map(([title, desc]) => (
                    <div
                      key={title}
                      className="rounded-lg border border-slate-200 p-4"
                    >
                      <p className="font-medium text-slate-950">{title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-500">
                        {desc}
                      </p>
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-lg border border-slate-200 bg-white p-5">
                <h3 className="font-semibold text-slate-950">生效范围</h3>
                <div className="mt-4 flex flex-wrap gap-2">
                  {['企微', '飞书', '微信客服', '网站客服'].map((channel) => (
                    <Badge
                      key={channel}
                      variant="outline"
                      className="border-blue-100 bg-blue-50 px-3 py-1.5 text-blue-700"
                    >
                      {channel}
                    </Badge>
                  ))}
                </div>
              </section>
            </div>
          </main>
        )}

        {step === 'canvas' && (
          <main className="grid min-h-0 flex-1 lg:grid-cols-[280px_minmax(0,1fr)_360px]">
            <aside className="hidden min-h-0 overflow-y-auto border-r border-slate-200 bg-white p-4 lg:block">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                <Input
                  className="pl-9"
                  placeholder="搜索节点"
                  value={nodeQuery}
                  onChange={(event) => setNodeQuery(event.target.value)}
                />
              </div>
              <div className="mt-4 space-y-5">
                {blockGroups.map((group) => (
                  <section key={group}>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                      {group}
                    </h3>
                    <div className="space-y-2">
                      {visibleBlocks
                        .filter((block) => nodeMeta[block.type].group === group)
                        .map((block) => (
                          <button
                            key={block.id}
                            type="button"
                            onClick={() => addNode(block)}
                            className="w-full rounded-lg border border-slate-200 bg-white p-3 text-left hover:border-blue-200 hover:bg-blue-50"
                          >
                            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                              <span
                                className={cn(
                                  'rounded-md border p-1',
                                  nodeMeta[block.type].accent,
                                )}
                              >
                                <NodeIcon type={block.type} />
                              </span>
                              {block.title}
                            </div>
                            <p className="mt-2 text-xs leading-5 text-slate-500">
                              {block.description}
                            </p>
                          </button>
                        ))}
                    </div>
                  </section>
                ))}
              </div>
            </aside>

            <section className="min-h-0 overflow-auto bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] [background-size:20px_20px] p-8">
              <div className="mx-auto flex min-h-full w-fit flex-col items-center justify-center py-8">
                {nodes.map((node, index) => (
                  <div key={node.id} className="flex flex-col items-center">
                    <CanvasNodeCard
                      node={node}
                      selected={selectedNode?.id === node.id}
                      onSelect={() => setSelectedNodeId(node.id)}
                    />
                    {index < nodes.length - 1 && (
                      <>
                        <div className="h-10 w-px bg-slate-300" />
                        <button
                          type="button"
                          className="flex size-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 shadow-sm hover:border-blue-300 hover:text-blue-600"
                          onClick={() => addNode(createNode('llm'))}
                        >
                          <Plus className="size-5" />
                        </button>
                        <div className="h-10 w-px bg-slate-300" />
                      </>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <aside className="hidden min-h-0 border-l border-slate-200 bg-white lg:flex lg:flex-col">
              <div className="border-b border-slate-200 p-5">
                <p className="text-sm text-slate-500">节点设置</p>
                <h2 className="mt-1 text-lg font-semibold text-slate-950">
                  {selectedNode?.title}
                </h2>
              </div>
              <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-5">
                <div>
                  <label className="text-sm font-medium text-slate-700">
                    节点名称
                  </label>
                  <Input
                    className="mt-2"
                    value={selectedNode?.title || ''}
                    readOnly
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">
                    节点说明
                  </label>
                  <Textarea
                    className="mt-2 min-h-24"
                    value={selectedNode?.description || ''}
                    readOnly
                  />
                </div>
                <div className="rounded-lg border border-slate-200 p-4">
                  <p className="text-sm font-semibold text-slate-950">
                    节点类型
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <span
                      className={cn(
                        'rounded-md border p-1',
                        selectedNode && nodeMeta[selectedNode.type].accent,
                      )}
                    >
                      {selectedNode && <NodeIcon type={selectedNode.type} />}
                    </span>
                    <span className="text-sm text-slate-600">
                      {selectedNode && nodeMeta[selectedNode.type].label}
                    </span>
                  </div>
                </div>
                {selectedNode?.type === 'llm' && (
                  <div className="rounded-lg border border-violet-200 bg-violet-50 p-4">
                    <div className="flex items-center gap-2 font-semibold text-violet-800">
                      <Bot className="size-4" />
                      调用 AI Agent
                    </div>
                    <p className="mt-2 text-sm leading-6 text-violet-700">
                      当前节点会调用绑定的 AI Agent，生成回复、推荐产品、总结线索，并返回是否转人工的判断结果。
                    </p>
                  </div>
                )}
                {selectedNode?.config && (
                  <div className="rounded-lg border border-slate-200 p-4">
                    <p className="text-sm font-semibold text-slate-950">
                      默认配置
                    </p>
                    <div className="mt-3 space-y-2 text-sm text-slate-600">
                      {Object.entries(selectedNode.config).map(([key, value]) => (
                        <div key={key} className="rounded-md bg-slate-50 p-2">
                          <span className="font-medium text-slate-700">
                            {key}：
                          </span>
                          {Array.isArray(value) ? value.join('、') : value}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div className="rounded-lg border border-slate-200 p-4">
                  <p className="text-sm font-semibold text-slate-950">
                    执行结果
                  </p>
                  <div className="mt-3 space-y-2 text-sm text-slate-600">
                    <div className="flex items-center gap-2">
                      <CircleDot className="size-4 text-emerald-600" />
                      可进入下一节点
                    </div>
                    <div className="flex items-center gap-2">
                      <MousePointerClick className="size-4 text-blue-600" />
                      可查看节点详情
                    </div>
                    <div className="flex items-center gap-2">
                      <Clock3 className="size-4 text-orange-600" />
                      支持后续接入真实 LangGraph 执行状态
                    </div>
                  </div>
                </div>
              </div>
            </aside>
          </main>
        )}
      </div>
    </div>
  );
}
