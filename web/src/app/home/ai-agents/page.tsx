import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bot,
  CheckCircle2,
  Database,
  FileUp,
  Headphones,
  MessageSquareText,
  Mic,
  Paperclip,
  Play,
  Plus,
  Search,
  Send,
  Sparkles,
  UserRoundSearch,
  WandSparkles,
  Workflow,
} from 'lucide-react';

import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { httpClient } from '@/app/infra/http/HttpClient';
import { LLMModel } from '@/app/infra/entities/api';
import { cn } from '@/lib/utils';

type AgentTemplate = {
  id: 'sales' | 'service';
  icon: ReactNode;
  name: string;
  description: string;
  defaultName: string;
  defaultDescription: string;
  rolePrompt: string;
  goals: string[];
  defaultWorkflow: string;
};

type AgentStep = 'create' | 'setup' | 'deploy';

const agentTemplates: AgentTemplate[] = [
  {
    id: 'sales',
    icon: <UserRoundSearch className="size-5" />,
    name: '销售 Agent',
    description: '接待新线索，判断客户意图，推荐产品，并推动高意向客户转人工。',
    defaultName: '售前 AI 销售员',
    defaultDescription: '负责接待新线索、判断客户意图、推荐合适产品并推动转人工。',
    rolePrompt:
      '你是公司的售前 AI 销售员。你需要先理解客户需求，再基于产品库和知识库推荐合适方案。不要编造价格、能力或承诺收益。客户出现报价单、合同、电话沟通、复杂定制、强购买意向时，要创建人工接入。',
    goals: ['识别客户意图', '推荐合适产品', '收集关键线索', '高意向客户转人工'],
    defaultWorkflow: '销售 Workflow',
  },
  {
    id: 'service',
    icon: <MessageSquareText className="size-5" />,
    name: '客服 Agent',
    description: '回答常见问题，处理基础咨询，收集问题背景，必要时转人工。',
    defaultName: '客服接待 AI',
    defaultDescription: '负责基础答疑、问题分流、资料收集和服务转人工。',
    rolePrompt:
      '你是公司的客服接待 AI。你需要用简短、清晰、耐心的方式回答客户问题。优先引用知识库和已接入资料，不确定时不要猜测。遇到投诉、复杂问题、客户明确要求人工或无法解决时，要转人工。',
    goals: ['回答常见问题', '收集问题背景', '判断是否转人工', '沉淀客户记忆'],
    defaultWorkflow: '运营 Workflow',
  },
];

const sampleAgents = [
  {
    name: '售前 AI 销售员',
    workflow: '销售 Workflow',
    channels: '企微、飞书',
    updatedAt: '今天 14:20',
  },
  {
    name: '客服接待 AI',
    workflow: '运营 Workflow',
    channels: '未部署',
    updatedAt: '昨天 18:04',
  },
];

const workflowsFromProject = ['销售 Workflow', '运营 Workflow'];
const fallbackKnowledgeBases = ['产品知识库', '销售话术库', '常见问题库'];

function StepPill({
  step,
  current,
  label,
}: {
  step: AgentStep;
  current: AgentStep;
  label: string;
}) {
  const order: AgentStep[] = ['create', 'setup', 'deploy'];
  const currentIndex = order.indexOf(current);
  const index = order.indexOf(step);
  const done = index < currentIndex;
  const active = current === step;

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

function TemplateCard({
  template,
  selected,
  onSelect,
}: {
  template: AgentTemplate;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'flex min-h-40 w-full flex-col items-start gap-3 rounded-lg border bg-white p-5 text-left transition',
        selected
          ? 'border-blue-500 shadow-sm ring-2 ring-blue-100'
          : 'border-slate-200 hover:border-slate-300 hover:shadow-sm',
      )}
    >
      <span className="rounded-md bg-blue-50 p-2 text-blue-600">
        {template.icon}
      </span>
      <div>
        <div className="text-base font-semibold text-slate-950">
          {template.name}
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          {template.description}
        </p>
      </div>
    </button>
  );
}

function SettingSection({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="border-b border-slate-200 px-5 py-4 last:border-b-0">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-blue-600">{icon}</span>
        <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
      </div>
      {children}
    </section>
  );
}

export default function AiAgentsPage() {
  const { t } = useTranslation();
  const { knowledgeBases } = useSidebarData();
  const [mode, setMode] = useState<'list' | 'create'>('list');
  const [step, setStep] = useState<AgentStep>('create');
  const [selectedTemplateId, setSelectedTemplateId] =
    useState<AgentTemplate['id']>('sales');
  const selectedTemplate = useMemo(
    () =>
      agentTemplates.find((template) => template.id === selectedTemplateId) ||
      agentTemplates[0],
    [selectedTemplateId],
  );
  const [agentName, setAgentName] = useState(selectedTemplate.defaultName);
  const [agentDescription, setAgentDescription] = useState(
    selectedTemplate.defaultDescription,
  );
  const [rolePrompt, setRolePrompt] = useState(selectedTemplate.rolePrompt);
  const [selectedWorkflow, setSelectedWorkflow] = useState(
    selectedTemplate.defaultWorkflow,
  );
  const [selectedKnowledge, setSelectedKnowledge] = useState(
    fallbackKnowledgeBases[0],
  );
  const [llmModels, setLlmModels] = useState<LLMModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [model, setModel] = useState('');
  const [thinkingSteps, setThinkingSteps] = useState(2);
  const [referenceRounds, setReferenceRounds] = useState(4);
  const [openingMessage, setOpeningMessage] = useState(
    '您好，我是 AI 助手。请简单说一下您的需求，我来帮您匹配合适方案。',
  );
  const [testMessage, setTestMessage] = useState(
    '客户问：你们这个 AI 销售系统能不能接入企微？大概怎么收费？',
  );
  const [testResult, setTestResult] = useState('');

  const configuredLlmModels = useMemo(
    () =>
      llmModels.filter(
        (item) => item.provider?.requester !== 'space-chat-completions',
      ),
    [llmModels],
  );

  const selectedModel = useMemo(
    () => configuredLlmModels.find((item) => item.uuid === model),
    [configuredLlmModels, model],
  );

  const knowledgeOptions =
    knowledgeBases.length > 0
      ? knowledgeBases.map((base) => base.name)
      : fallbackKnowledgeBases;

  useEffect(() => {
    setModelsLoading(true);
    httpClient
      .getProviderLLMModels(undefined, {
        include_space_models: false,
        include_system_models: false,
        only_configured_providers: true,
        model_category: 'text',
      })
      .then((resp) => {
        setLlmModels(resp.models || []);
      })
      .catch((error) => {
        console.warn('Failed to load LLM models', error);
        setLlmModels([]);
      })
      .finally(() => {
        setModelsLoading(false);
      });
  }, []);

  useEffect(() => {
    if (configuredLlmModels.length === 0) {
      setModel('');
      return;
    }
    if (!configuredLlmModels.some((item) => item.uuid === model)) {
      setModel(configuredLlmModels[0].uuid);
    }
  }, [configuredLlmModels, model]);

  function selectTemplate(template: AgentTemplate) {
    setSelectedTemplateId(template.id);
    setAgentName(template.defaultName);
    setAgentDescription(template.defaultDescription);
    setRolePrompt(template.rolePrompt);
    setSelectedWorkflow(template.defaultWorkflow);
  }

  function startCustomAgent() {
    setAgentName('自定义 AI Agent');
    setAgentDescription('根据你的业务场景自定义角色、知识、Workflow 和回复方式。');
    setRolePrompt('请在这里定义 Agent 的角色、目标、边界和执行规则。');
    setSelectedWorkflow(workflowsFromProject[0]);
  }

  function runPreview() {
    const modelLabel = selectedModel?.name || t('aiAgents.noModelSelected');
    setTestResult(
      `已使用 ${modelLabel} 模型，并接入「${selectedWorkflow}」与「${selectedKnowledge}」。${agentName} 会先识别客户意图，再根据角色指令生成回复；如果命中高意向或复杂问题，会交给 Workflow 继续处理。`,
    );
  }

  function nextStep() {
    if (step === 'create') {
      setStep('setup');
      return;
    }
    if (step === 'setup') {
      setStep('deploy');
    }
  }

  if (mode === 'list') {
    return (
      <div className="h-full overflow-y-auto bg-slate-50 p-4 text-slate-900">
        <div className="mx-auto flex max-w-[1500px] flex-col gap-4">
          <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-slate-950">
                AI Agent
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                创建和管理可执行销售任务的 AI 员工。Agent 负责怎么说、知道什么、能读取哪些客户资料，以及可以触发哪些 Workflow。
              </p>
            </div>
            <Button onClick={() => setMode('create')}>
              <Plus className="size-4" />
              创建 AI Agent
            </Button>
          </div>

          <section className="rounded-lg border border-slate-200 bg-white">
            <div className="border-b border-slate-200 p-4">
              <div className="relative max-w-md flex-1">
                <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                <Input className="pl-9" placeholder="搜索 Agent 名称或场景" />
              </div>
            </div>
            <div className="divide-y divide-slate-100">
              {sampleAgents.map((agent) => (
                <div
                  key={agent.name}
                  className="grid gap-3 p-4 md:grid-cols-[1.3fr_1fr_1fr_0.7fr]"
                >
                  <div>
                    <div className="font-semibold text-slate-950">
                      {agent.name}
                    </div>
                    <p className="mt-1 text-sm text-slate-500">
                      接入 Workflow：{agent.workflow}
                    </p>
                  </div>
                  <div className="text-sm text-slate-600">{agent.channels}</div>
                  <div className="text-sm text-slate-600">
                    {agent.updatedAt}
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
            <p className="text-sm font-medium text-slate-500">AI Agent 设置</p>
            <h1 className="text-2xl font-semibold text-slate-950">
              创建 Agent
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-5">
            <StepPill step="create" current={step} label="创建" />
            <StepPill step="setup" current={step} label="设置" />
            <StepPill step="deploy" current={step} label="部署" />
            <Button variant="outline" onClick={() => setMode('list')}>
              返回列表
            </Button>
            <Button onClick={step === 'deploy' ? undefined : nextStep}>
              {step === 'deploy' ? '发布 Agent' : '下一步'}
            </Button>
          </div>
        </header>

        {step === 'create' && (
          <main className="min-h-0 flex-1 overflow-y-auto p-5">
            <div className="mx-auto grid max-w-[1500px] gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
              <section>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <h2 className="text-xl font-semibold text-slate-950">
                      AI Agent 模板
                    </h2>
                    <p className="mt-1 text-sm text-slate-500">
                      先选择销售或客服模板；也可以从自定义 Agent 开始。
                    </p>
                  </div>
                  <Button variant="outline" onClick={startCustomAgent}>
                    <WandSparkles className="size-4" />
                    自定义 Agent
                  </Button>
                </div>

                <div className="mt-6 grid gap-4 md:grid-cols-2">
                  {agentTemplates.map((template) => (
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
                      {selectedTemplate.defaultWorkflow}
                    </p>
                  </div>
                </div>
                <label className="text-sm font-medium text-slate-700">
                  Agent 名称（仅供内部使用）
                </label>
                <Input
                  className="mt-2"
                  value={agentName}
                  onChange={(event) => setAgentName(event.target.value)}
                />
                <label className="mt-4 block text-sm font-medium text-slate-700">
                  描述（选填）
                </label>
                <Textarea
                  className="mt-2 min-h-28"
                  value={agentDescription}
                  onChange={(event) => setAgentDescription(event.target.value)}
                />
                <div className="mt-5 rounded-lg border border-slate-200 p-4">
                  <h4 className="font-semibold text-slate-950">目标总览</h4>
                  <div className="mt-3 space-y-3">
                    {selectedTemplate.goals.map((goal, index) => (
                      <div
                        key={goal}
                        className="flex items-center gap-3 text-sm text-slate-600"
                      >
                        <span className="flex size-6 items-center justify-center rounded-full bg-blue-50 text-xs font-semibold text-blue-600">
                          {index + 1}
                        </span>
                        {goal}
                      </div>
                    ))}
                  </div>
                </div>
              </aside>
            </div>
          </main>
        )}

        {step === 'setup' && (
          <main className="grid min-h-0 flex-1 lg:grid-cols-[minmax(360px,0.95fr)_minmax(360px,0.95fr)_420px]">
            <section className="min-h-0 border-r border-slate-200 bg-white">
              <div className="border-b border-slate-200 px-5 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-slate-950">
                      角色指令
                    </h2>
                    <p className="mt-1 text-xs text-slate-500">
                      定义 Agent 的身份、目标、边界和回复规则。
                    </p>
                  </div>
                  <Button size="sm" variant="outline">
                    <Sparkles className="size-4" />
                    生成
                  </Button>
                </div>
              </div>
              <div className="flex h-[calc(100%-73px)] min-h-0 flex-col p-5">
                <Textarea
                  className="min-h-0 flex-1 resize-none text-sm leading-6"
                  value={rolePrompt}
                  onChange={(event) => setRolePrompt(event.target.value)}
                />
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span>可引用：</span>
                  <Badge variant="outline">@ 工具</Badge>
                  <Badge variant="outline">{'{变量值}'}</Badge>
                  <Badge variant="outline">知识库</Badge>
                </div>
              </div>
            </section>

            <section className="min-h-0 overflow-y-auto bg-white">
              <div className="border-b border-slate-200 px-5 py-4">
                <h2 className="text-base font-semibold text-slate-950">
                  能力配置
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  接入模型、Workflow、知识、声音和开场白。
                </p>
              </div>

              <SettingSection
                icon={<Bot className="size-4" />}
                title="模型与思考"
              >
                <div className="grid gap-3">
                  <label className="space-y-1">
                    <span className="text-xs font-medium text-slate-500">
                      选择模型
                    </span>
                    <Select
                      value={model || undefined}
                      onValueChange={setModel}
                      disabled={modelsLoading || configuredLlmModels.length === 0}
                    >
                      <SelectTrigger>
                        <SelectValue
                          placeholder={
                            modelsLoading
                              ? t('common.loading')
                              : t('models.selectModel')
                          }
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {configuredLlmModels.map((item) => (
                          <SelectItem key={item.uuid} value={item.uuid}>
                            {item.name}
                            {item.provider?.name ? ` · ${item.provider.name}` : ''}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {!modelsLoading && configuredLlmModels.length === 0 && (
                      <p className="text-xs leading-5 text-amber-600">
                        {t('aiAgents.configureModelsHint')}
                      </p>
                    )}
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="space-y-1">
                      <span className="text-xs font-medium text-slate-500">
                        思考次数
                      </span>
                      <Input
                        type="number"
                        min={1}
                        max={8}
                        value={thinkingSteps}
                        onChange={(event) =>
                          setThinkingSteps(Number(event.target.value || 1))
                        }
                      />
                    </label>
                    <label className="space-y-1">
                      <span className="text-xs font-medium text-slate-500">
                        对话轮数
                      </span>
                      <Input
                        type="number"
                        min={1}
                        max={20}
                        value={referenceRounds}
                        onChange={(event) =>
                          setReferenceRounds(Number(event.target.value || 1))
                        }
                      />
                    </label>
                  </div>
                </div>
              </SettingSection>

              <SettingSection
                icon={<Workflow className="size-4" />}
                title="接入 Workflow"
              >
                <Select
                  value={selectedWorkflow}
                  onValueChange={setSelectedWorkflow}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {workflowsFromProject.map((workflow) => (
                      <SelectItem key={workflow} value={workflow}>
                        {workflow}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  Workflow 决定什么时候调用 Agent，以及调用后继续执行哪些节点。
                </p>
              </SettingSection>

              <SettingSection
                icon={<Database className="size-4" />}
                title="接入知识库"
              >
                <Select
                  value={selectedKnowledge}
                  onValueChange={setSelectedKnowledge}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {knowledgeOptions.map((base) => (
                      <SelectItem key={base} value={base}>
                        {base}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="mt-3 flex flex-wrap gap-2">
                  {knowledgeOptions.slice(0, 3).map((base) => (
                    <Badge
                      key={base}
                      variant="outline"
                      className="border-blue-100 bg-blue-50 text-blue-700"
                    >
                      {base}
                    </Badge>
                  ))}
                </div>
              </SettingSection>

              <SettingSection
                icon={<Headphones className="size-4" />}
                title="接入声音"
              >
                <div className="space-y-3">
                  {[
                    ['语音输入', '允许运营测试时用语音提问。'],
                    ['语音回复', 'Agent 可把关键回复转换为语音。'],
                  ].map(([label, desc]) => (
                    <div
                      key={label}
                      className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3"
                    >
                      <div>
                        <p className="text-sm font-medium text-slate-900">
                          {label}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">{desc}</p>
                      </div>
                      <Switch defaultChecked />
                    </div>
                  ))}
                </div>
              </SettingSection>

              <SettingSection
                icon={<MessageSquareText className="size-4" />}
                title="开场白"
              >
                <Textarea
                  className="min-h-24"
                  value={openingMessage}
                  onChange={(event) => setOpeningMessage(event.target.value)}
                />
              </SettingSection>
            </section>

            <aside className="min-h-0 border-l border-slate-200 bg-slate-50">
              <div className="border-b border-slate-200 bg-white px-5 py-4">
                <h2 className="text-base font-semibold text-slate-950">
                  预览与调试
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  测试问题、文件上传和语音输入。
                </p>
              </div>
              <div className="flex h-[calc(100%-73px)] min-h-0 flex-col p-5">
                <div className="flex flex-1 flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white p-6 text-center">
                  <span className="rounded-2xl bg-gradient-to-br from-sky-400 via-blue-500 to-emerald-300 p-5 text-white">
                    <Bot className="size-8" />
                  </span>
                  <h3 className="mt-4 text-lg font-semibold text-slate-950">
                    {agentName || 'AI Agent'}
                  </h3>
                  <p className="mt-2 max-w-xs text-sm leading-6 text-slate-500">
                    当前接入 {selectedWorkflow}、{selectedKnowledge}，可在下方输入客户问题进行测试。
                  </p>
                  {testResult && (
                    <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4 text-left text-sm leading-6 text-slate-600">
                      {testResult}
                    </div>
                  )}
                </div>

                <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
                  <Textarea
                    className="min-h-24 border-0 p-0 shadow-none focus-visible:ring-0"
                    value={testMessage}
                    onChange={(event) => setTestMessage(event.target.value)}
                    placeholder="请输入你的问题，支持对上传文件内容进行提问"
                  />
                  <div className="mt-3 flex items-center justify-between">
                    <div className="flex items-center gap-1">
                      <Button size="icon" variant="ghost" title="上传文件">
                        <Paperclip className="size-4" />
                      </Button>
                      <Button size="icon" variant="ghost" title="上传素材">
                        <FileUp className="size-4" />
                      </Button>
                      <Button size="icon" variant="ghost" title="语音输入">
                        <Mic className="size-4" />
                      </Button>
                    </div>
                    <Button size="icon" onClick={runPreview} title="发送测试">
                      <Send className="size-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </aside>
          </main>
        )}

        {step === 'deploy' && (
          <main className="min-h-0 flex-1 overflow-y-auto p-5">
            <div className="mx-auto max-w-4xl space-y-5">
              <div>
                <h2 className="text-xl font-semibold text-slate-950">
                  部署 Agent
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  选择 Agent 将在哪些渠道和 Workflow 中生效。
                </p>
              </div>

              <section className="rounded-lg border border-slate-200 bg-white p-5">
                <h3 className="font-semibold text-slate-950">绑定渠道</h3>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {['企微', '飞书', '微信客服', '网站客服'].map((channel) => (
                    <div
                      key={channel}
                      className="flex items-center justify-between rounded-lg border border-slate-200 p-4"
                    >
                      <span className="font-medium text-slate-800">
                        {channel}
                      </span>
                      <Switch defaultChecked={channel !== '网站客服'} />
                    </div>
                  ))}
                </div>
              </section>

              <section className="rounded-lg border border-slate-200 bg-white p-5">
                <h3 className="font-semibold text-slate-950">发布确认</h3>
                <div className="mt-4 space-y-3 text-sm text-slate-600">
                  <div>Agent：{agentName}</div>
                  <div>
                    模型：
                    {selectedModel?.name || t('aiAgents.noModelSelected')}
                  </div>
                  <div>Workflow：{selectedWorkflow}</div>
                  <div>知识库：{selectedKnowledge}</div>
                </div>
              </section>
            </div>
          </main>
        )}
      </div>
    </div>
  );
}
