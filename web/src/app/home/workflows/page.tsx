import { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  BrainCircuit,
  CheckCircle2,
  ClipboardCheck,
  Folder,
  FolderPlus,
  GitBranch,
  Handshake,
  Loader2,
  MessageSquareText,
  PackageCheck,
  Plus,
  Route,
  Repeat2,
  Search,
  Sparkles,
  Trash2,
  UserRoundCheck,
  Workflow as WorkflowIcon,
} from 'lucide-react';

import PipelineWorkflowEditor from '@/app/home/pipelines/components/workflow-editor/PipelineWorkflowEditor';
import { createBlankWorkflow } from '@/app/home/pipelines/components/workflow-editor/workflowTemplates';
import { PipelineWorkflow } from '@/app/home/pipelines/components/workflow-editor/types';
import type { WorkflowDraft, WorkflowProject } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
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
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

type WorkflowItem = {
  id: string;
  folder: string;
  name: string;
  description: string;
  workflow: PipelineWorkflow;
  isBuiltin: boolean;
};

type SalesWorkflowTemplate = {
  title: string;
  scenario: string;
  description: string;
  checklist: string[];
  icon: typeof UserRoundCheck;
  accent: string;
};

type WorkflowPathStep = {
  title: string;
  description: string;
  node: string;
  icon: typeof MessageSquareText;
  tone: string;
};

const defaultFolder = '我的项目';

const salesPathSteps: WorkflowPathStep[] = [
  {
    title: '触发条件',
    description: '客户发消息、点击链接、进入高意向标签或销售手动标记。',
    node: '入口触发',
    icon: MessageSquareText,
    tone: 'bg-sky-50 text-sky-700 ring-sky-100',
  },
  {
    title: 'AI 识别意图',
    description: '识别询价、产品咨询、异议、转人工、复购等开放式表达。',
    node: '意图识别',
    icon: BrainCircuit,
    tone: 'bg-violet-50 text-violet-700 ring-violet-100',
  },
  {
    title: '提问补信息',
    description: '补齐年级、需求、预算、联系方式、购买时间等资格判断字段。',
    node: '线索收集',
    icon: UserRoundCheck,
    tone: 'bg-rose-50 text-rose-700 ring-rose-100',
  },
  {
    title: '条件分支',
    description: '按意向等级、缺失字段、产品匹配度决定不同推进路径。',
    node: '条件分支',
    icon: GitBranch,
    tone: 'bg-slate-100 text-slate-700 ring-slate-200',
  },
  {
    title: '执行业务动作',
    description: '推荐产品、发送素材、写入客户记忆、创建触达计划或调用 CRM。',
    node: '产品库 / 动作',
    icon: Route,
    tone: 'bg-amber-50 text-amber-800 ring-amber-100',
  },
  {
    title: '转人工/沉淀线索',
    description: '把摘要、画像、关键问答和推荐话术交给销售继续推进。',
    node: '人工介入',
    icon: Handshake,
    tone: 'bg-emerald-50 text-emerald-700 ring-emerald-100',
  },
];

const salesWorkflowTemplates: SalesWorkflowTemplate[] = [
  {
    title: '高意向转人工',
    scenario: '线索升温',
    description:
      '识别预算、时间、关键需求等信号，自动汇总上下文并提醒销售接手。',
    checklist: ['意向分规则', '转人工条件', '会话摘要字段'],
    icon: UserRoundCheck,
    accent: 'bg-emerald-50 text-emerald-700 ring-emerald-100',
  },
  {
    title: '产品内容补全',
    scenario: '知识补齐',
    description: '发现客户追问但知识库缺失的内容，沉淀为待补充素材和跟进任务。',
    checklist: ['缺口识别', '素材负责人', '补全后回访'],
    icon: PackageCheck,
    accent: 'bg-sky-50 text-sky-700 ring-sky-100',
  },
  {
    title: '持续触达培育',
    scenario: '长期跟进',
    description: '按客户阶段安排提醒、内容推送和复访节奏，避免高价值线索沉默。',
    checklist: ['客户阶段', '触达频率', '停止条件'],
    icon: Repeat2,
    accent: 'bg-amber-50 text-amber-700 ring-amber-100',
  },
];

const launchChecklist = [
  '明确触发入口：客户问题、意向分、标签变化或人工标记。',
  '准备销售上下文：产品卖点、报价口径、常见异议和客户画像。',
  '设置交接标准：何时自动回复、何时提醒人工、交接给谁。',
  '上线前小流量验证：先用真实销售对话回放检查节点结果。',
];

const defaultDraftInstruction =
  '当家长咨询图书资源、答案或音频时，先帮他打开资源卡片；确认资源能打开后，再根据孩子年级和需求推荐猿辅导自然拼读或阅读思维体验课。客户问价格、怎么报名、已点击链接或近期想买时，发送报名链接并创建雷达跟进；客户已支付、支付异常、投诉、要求人工或AI无法判断截图时，停止AI促单并把摘要、画像、关键问答和推荐话术交给人工销售。未成交24小时后继续触达。';

type WorkflowDraftScenario = 'yuanfudao_sales' | 'sales';

function fromWorkflowProject(project: WorkflowProject): WorkflowItem {
  return {
    id: project.uuid,
    folder: project.folder || defaultFolder,
    name: project.name,
    description: project.description || '',
    workflow: project.workflow as PipelineWorkflow,
    isBuiltin: project.is_builtin || false,
  };
}

export default function WorkflowsPage() {
  const [folders, setFolders] = useState(() => [defaultFolder]);
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [activeFolder, setActiveFolder] = useState(defaultFolder);
  const [keyword, setKeyword] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [workflowPendingDeleteId, setWorkflowPendingDeleteId] = useState<
    string | null
  >(null);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [draftInstruction, setDraftInstruction] = useState(
    defaultDraftInstruction,
  );
  const [draftScenario, setDraftScenario] =
    useState<WorkflowDraftScenario>('yuanfudao_sales');
  const [draftGenerating, setDraftGenerating] = useState(false);
  const [generatedDraft, setGeneratedDraft] = useState<{
    draft: WorkflowDraft;
    used_llm: boolean;
    model_name?: string;
    fallback_reason?: string;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    httpClient
      .getWorkflows()
      .then((data) => {
        if (cancelled) return;
        const nextFolders = data.folders.length
          ? data.folders
          : [defaultFolder];
        setFolders(nextFolders);
        setWorkflows((data.workflows || []).map(fromWorkflowProject));
        setActiveFolder((current) =>
          nextFolders.includes(current) ? current : nextFolders[0],
        );
      })
      .catch((error) => {
        toast.error(`工作流加载失败${error?.msg ? `：${error.msg}` : ''}`);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const editingWorkflow = workflows.find((item) => item.id === editingId);
  const workflowPendingDelete = workflows.find(
    (item) => item.id === workflowPendingDeleteId,
  );
  const visibleWorkflows = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    return workflows.filter((item) => {
      const inFolder = item.folder === activeFolder;
      const matchesKeyword =
        !normalizedKeyword ||
        `${item.name} ${item.description} ${item.folder}`
          .toLowerCase()
          .includes(normalizedKeyword);
      return inFolder && matchesKeyword;
    });
  }, [activeFolder, keyword, workflows]);

  function updateWorkflow(nextWorkflow: PipelineWorkflow) {
    if (!editingId) return;
    setWorkflows((current) =>
      current.map((item) =>
        item.id === editingId
          ? {
              ...item,
              name: nextWorkflow.name || item.name,
              workflow: nextWorkflow,
            }
          : item,
      ),
    );
  }

  async function createNewWorkflow(template?: SalesWorkflowTemplate) {
    const workflow = createBlankWorkflow();
    const workflowName = template?.title || '新建工作流';
    const workflowDescription =
      template?.description || '从空白画布开始搭建新的自动化流程。';
    const payload = {
      folder: activeFolder,
      name: workflowName,
      description: workflowDescription,
      workflow: {
        ...workflow,
        name: workflowName,
      },
    };
    let resp: { uuid: string };
    try {
      resp = await httpClient.createWorkflow(payload);
    } catch (error: any) {
      toast.error(`工作流创建失败${error?.msg ? `：${error.msg}` : ''}`);
      return;
    }
    setWorkflows((current) => [
      {
        id: resp.uuid,
        ...payload,
        isBuiltin: false,
      },
      ...current,
    ]);
    setEditingId(resp.uuid);
  }

  async function generateDraftWorkflow() {
    const instruction = draftInstruction.trim();
    if (!instruction) {
      toast.error('请先输入销售规则');
      return;
    }
    setDraftGenerating(true);
    try {
      const resp = await httpClient.generateWorkflowDraft({
        instruction,
        scenario: draftScenario,
      });
      setGeneratedDraft(resp);
      toast.success(
        resp.used_llm ? 'AI 已生成流程草稿' : '已使用规则兜底生成草稿',
      );
    } catch (error: any) {
      toast.error(`流程草稿生成失败${error?.msg ? `：${error.msg}` : ''}`);
    } finally {
      setDraftGenerating(false);
    }
  }

  async function createGeneratedWorkflow() {
    if (!generatedDraft) return;
    const payload = {
      folder: activeFolder,
      name: generatedDraft.draft.title || 'AI销售流程',
      description: generatedDraft.draft.summary,
      workflow: generatedDraft.draft.workflow,
    };
    let resp: { uuid: string };
    try {
      resp = await httpClient.createWorkflow(payload);
    } catch (error: any) {
      toast.error(`工作流创建失败${error?.msg ? `：${error.msg}` : ''}`);
      return;
    }
    setWorkflows((current) => [
      {
        id: resp.uuid,
        ...payload,
        workflow: payload.workflow as PipelineWorkflow,
        isBuiltin: false,
      },
      ...current,
    ]);
    setEditingId(resp.uuid);
  }

  async function createFolder() {
    const folderName = newFolderName.trim();
    if (!folderName || folders.includes(folderName)) {
      setCreatingFolder(false);
      setNewFolderName('');
      return;
    }

    try {
      await httpClient.createWorkflowFolder(folderName);
    } catch (error: any) {
      toast.error(`目录创建失败${error?.msg ? `：${error.msg}` : ''}`);
      return;
    }
    setFolders((current) => [...current, folderName]);
    setActiveFolder(folderName);
    setCreatingFolder(false);
    setNewFolderName('');
  }

  async function deleteWorkflow() {
    if (!workflowPendingDeleteId) return;
    try {
      await httpClient.deleteWorkflow(workflowPendingDeleteId);
    } catch (error: any) {
      toast.error(`工作流删除失败${error?.msg ? `：${error.msg}` : ''}`);
      return;
    }
    setWorkflows((current) =>
      current.filter((item) => item.id !== workflowPendingDeleteId),
    );
    if (editingId === workflowPendingDeleteId) {
      setEditingId(null);
    }
    setWorkflowPendingDeleteId(null);
  }

  async function saveEditingWorkflow() {
    if (!editingWorkflow) return;
    setSaving(true);
    try {
      await httpClient.updateWorkflow(editingWorkflow.id, {
        folder: editingWorkflow.folder,
        name: editingWorkflow.name,
        description: editingWorkflow.description,
        workflow: editingWorkflow.workflow,
      });
      setEditingId(null);
      toast.success('工作流已保存');
    } catch (error: any) {
      toast.error(`工作流保存失败${error?.msg ? `：${error.msg}` : ''}`);
    } finally {
      setSaving(false);
    }
  }

  if (editingWorkflow) {
    return (
      <div className="flex h-full min-h-0 flex-col bg-slate-50 text-slate-900">
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-9"
              onClick={() => setEditingId(null)}
            >
              <ArrowLeft className="size-4" />
            </Button>
            <div className="min-w-0">
              <h1 className="truncate text-xl font-semibold text-slate-950">
                {editingWorkflow.name}
              </h1>
              <p className="mt-1 text-sm text-slate-500">
                {editingWorkflow.workflow.nodes.length} 个节点，
                {editingWorkflow.workflow.edges.length} 条连线
              </p>
            </div>
          </div>
          <Button type="button" onClick={saveEditingWorkflow} disabled={saving}>
            {saving ? '保存中' : '保存并返回'}
          </Button>
        </header>
        <div className="min-h-0 flex-1">
          <PipelineWorkflowEditor
            value={editingWorkflow.workflow}
            onChange={updateWorkflow}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-[#f5f7fb] text-slate-950">
      <header className="shrink-0 px-5 pb-5 pt-6 lg:px-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-normal">工作流</h1>
            <p className="mt-2 max-w-3xl text-base leading-7 text-slate-500">
              将销售智能体的判断、交接和触达动作编排成可复用流程，让线索从咨询、培育到转人工都有清晰路径。
            </p>
          </div>
          <Button
            type="button"
            className="mt-1 h-11 rounded-md bg-indigo-600 px-5 text-white hover:bg-indigo-700"
            onClick={() => createNewWorkflow()}
            disabled={loading}
          >
            <Plus className="size-4" />
            新建工作流
          </Button>
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="min-h-0 max-h-64 border-b border-slate-200/80 px-5 pb-4 lg:max-h-none lg:border-b-0 lg:border-r lg:px-7 lg:pb-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold">目录</h2>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="size-10 rounded-lg border-slate-200 bg-white"
                title="创建新目录"
                onClick={() => setCreatingFolder(true)}
              >
                <FolderPlus className="size-5" />
              </Button>
            </div>
          </div>
          <div className="h-[calc(100%-56px)] overflow-y-auto pr-2">
            {creatingFolder && (
              <div className="mb-3 rounded-lg border border-slate-200 bg-white p-3">
                <Input
                  value={newFolderName}
                  onChange={(event) => setNewFolderName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      createFolder();
                    }
                    if (event.key === 'Escape') {
                      setCreatingFolder(false);
                      setNewFolderName('');
                    }
                  }}
                  placeholder="新目录名称"
                  className="h-9"
                  autoFocus
                />
                <div className="mt-2 flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setCreatingFolder(false);
                      setNewFolderName('');
                    }}
                  >
                    取消
                  </Button>
                  <Button type="button" size="sm" onClick={createFolder}>
                    创建
                  </Button>
                </div>
              </div>
            )}
            <div className="space-y-2">
              {folders.map((folder) => (
                <button
                  key={folder}
                  type="button"
                  className={cn(
                    'flex h-11 w-full items-center gap-3 rounded-md px-3 text-left text-base font-medium text-slate-500 transition',
                    activeFolder === folder
                      ? 'bg-indigo-50 text-indigo-600'
                      : 'hover:bg-white hover:text-slate-900',
                  )}
                  onClick={() => setActiveFolder(folder)}
                >
                  <Folder className="size-5 shrink-0" />
                  <span className="truncate">{folder}</span>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <section className="min-h-0 overflow-y-auto px-5 pb-8 lg:px-9">
          <div className="mb-6 rounded-xl border border-slate-200 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="max-w-3xl">
                <div className="flex items-center gap-2 text-sm font-medium text-indigo-600">
                  <Sparkles className="size-4" />
                  业务路径 + AI 节点
                </div>
                <h2 className="mt-2 text-xl font-semibold text-slate-950">
                  工作流不是一个大 Prompt，而是一条可检查的销售推进路径
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  先确定客户从哪里进入、AI
                  负责识别和追问什么、哪些条件触发业务动作，再决定何时转人工或沉淀线索。
                </p>
              </div>
              <Button
                type="button"
                className="h-10 bg-indigo-600 text-white hover:bg-indigo-700"
                onClick={() => {
                  const template = salesWorkflowTemplates[0];
                  void createNewWorkflow(template);
                }}
                disabled={loading}
              >
                <Sparkles className="size-4" />
                生成销售流程初稿
              </Button>
            </div>

            <div className="mt-5 grid gap-3 lg:grid-cols-6">
              {salesPathSteps.map((step, index) => {
                const Icon = step.icon;
                return (
                  <div
                    key={step.title}
                    className="relative rounded-lg border border-slate-200 bg-slate-50 p-3"
                  >
                    <div className="flex items-start gap-2">
                      <span
                        className={cn(
                          'flex size-8 shrink-0 items-center justify-center rounded-lg ring-1',
                          step.tone,
                        )}
                      >
                        <Icon className="size-4" />
                      </span>
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-slate-950">
                          {step.title}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          {step.node}
                        </div>
                      </div>
                    </div>
                    <p className="mt-3 text-xs leading-5 text-slate-600">
                      {step.description}
                    </p>
                    {index < salesPathSteps.length - 1 && (
                      <div className="absolute -right-2 top-1/2 hidden size-4 -translate-y-1/2 rounded-full border border-slate-200 bg-white text-center text-[10px] leading-3 text-slate-400 lg:block">
                        →
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
              <div className="rounded-lg border border-indigo-100 bg-indigo-50/50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-indigo-700">
                      AI-first Workflow 生成器
                    </div>
                    <p className="mt-1 text-sm leading-6 text-indigo-700/80">
                      用自然语言描述路由、追问、转人工和跟进规则，系统会生成可检查的业务节点链路。
                    </p>
                  </div>
                  <Select
                    value={draftScenario}
                    onValueChange={(value) =>
                      setDraftScenario(value as WorkflowDraftScenario)
                    }
                  >
                    <SelectTrigger className="h-10 w-[190px] bg-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="yuanfudao_sales">
                        猿辅导销售加强版
                      </SelectItem>
                      <SelectItem value="sales">通用销售流程</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Textarea
                  value={draftInstruction}
                  onChange={(event) => setDraftInstruction(event.target.value)}
                  className="mt-4 min-h-[154px] resize-none border-indigo-100 bg-white text-sm leading-6"
                  placeholder="例如：客户问价格时先追问年级和预算，高意向转销售，未成交24小时后触达。"
                />
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                  <div className="text-xs leading-5 text-indigo-700/75">
                    后端会优先调用已配置的真实
                    LLM；没有可用模型时才使用规则兜底。
                  </div>
                  <Button
                    type="button"
                    className="h-10 bg-indigo-600 text-white hover:bg-indigo-700"
                    onClick={generateDraftWorkflow}
                    disabled={draftGenerating}
                  >
                    {draftGenerating ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Sparkles className="size-4" />
                    )}
                    {draftGenerating ? '生成中' : '生成流程草稿'}
                  </Button>
                </div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-slate-950">
                      草稿审查
                    </div>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      先确认路径，再创建到画布继续细化节点。
                    </p>
                  </div>
                  {generatedDraft && (
                    <Badge
                      variant="outline"
                      className={cn(
                        'shrink-0',
                        generatedDraft.used_llm
                          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                          : 'border-amber-200 bg-amber-50 text-amber-700',
                      )}
                    >
                      {generatedDraft.used_llm ? '真实模型生成' : '规则兜底'}
                    </Badge>
                  )}
                </div>

                {generatedDraft ? (
                  <div className="mt-4 space-y-4">
                    <div>
                      <h3 className="text-base font-semibold text-slate-950">
                        {generatedDraft.draft.title}
                      </h3>
                      <p className="mt-1 text-sm leading-6 text-slate-500">
                        {generatedDraft.draft.summary}
                      </p>
                      {generatedDraft.fallback_reason && (
                        <p className="mt-2 text-xs leading-5 text-amber-700">
                          {generatedDraft.fallback_reason}
                        </p>
                      )}
                    </div>

                    <div className="max-h-[178px] space-y-2 overflow-y-auto pr-1">
                      {generatedDraft.draft.rules.map((rule, index) => (
                        <div
                          key={`${rule.intent}-${index}`}
                          className="rounded-md border border-slate-100 bg-slate-50 p-3"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold text-slate-500">
                              {rule.intent}
                            </span>
                            {rule.handoff && (
                              <Badge
                                variant="outline"
                                className="border-orange-200 bg-orange-50 text-orange-700"
                              >
                                转人工
                              </Badge>
                            )}
                          </div>
                          <p className="mt-2 text-xs leading-5 text-slate-600">
                            当 {rule.when}，执行 {rule.action}
                          </p>
                        </div>
                      ))}
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <div className="text-xs font-medium text-slate-500">
                          资格判断字段
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {generatedDraft.draft.qualification_fields.map(
                            (field) => (
                              <span
                                key={field}
                                className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600"
                              >
                                {field}
                              </span>
                            ),
                          )}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs font-medium text-slate-500">
                          人工接管条件
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {generatedDraft.draft.handoff_rules.map((rule) => (
                            <span
                              key={rule}
                              className="rounded-md bg-orange-50 px-2 py-1 text-xs text-orange-700"
                            >
                              {rule}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>

                    <Button
                      type="button"
                      className="w-full bg-slate-950 text-white hover:bg-slate-800"
                      onClick={createGeneratedWorkflow}
                    >
                      创建到画布
                    </Button>
                  </div>
                ) : (
                  <div className="mt-5 space-y-3 text-sm text-slate-600">
                    {[
                      '触发入口是否真实存在',
                      'AI 追问字段是否足够',
                      '转人工规则是否清晰',
                    ].map((item) => (
                      <div key={item} className="flex items-center gap-2">
                        <CheckCircle2 className="size-4 text-emerald-500" />
                        {item}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="mb-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-indigo-600">
                    <MessageSquareText className="size-4" />
                    销售智能体推荐入口
                  </div>
                  <h2 className="mt-2 text-xl font-semibold text-slate-950">
                    从常见销售场景开始搭建
                  </h2>
                </div>
                <span className="rounded-md bg-slate-100 px-3 py-1 text-sm text-slate-500">
                  创建后进入画布细化节点
                </span>
              </div>
              <div className="grid gap-3 lg:grid-cols-3">
                {salesWorkflowTemplates.map((template) => {
                  const Icon = template.icon;
                  return (
                    <article
                      key={template.title}
                      className="flex min-h-[220px] flex-col rounded-lg border border-slate-200 p-4 transition hover:border-indigo-200 hover:shadow-sm"
                    >
                      <div className="mb-4 flex items-start justify-between gap-3">
                        <span
                          className={cn(
                            'flex size-10 shrink-0 items-center justify-center rounded-lg ring-1',
                            template.accent,
                          )}
                        >
                          <Icon className="size-5" />
                        </span>
                        <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-500">
                          {template.scenario}
                        </span>
                      </div>
                      <h3 className="text-lg font-semibold text-slate-950">
                        {template.title}
                      </h3>
                      <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-500">
                        {template.description}
                      </p>
                      <div className="mt-4 space-y-2">
                        {template.checklist.map((item) => (
                          <div
                            key={item}
                            className="flex items-center gap-2 text-sm text-slate-600"
                          >
                            <CheckCircle2 className="size-4 shrink-0 text-emerald-500" />
                            <span className="truncate">{item}</span>
                          </div>
                        ))}
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        className="mt-auto h-9 justify-center border-slate-200"
                        onClick={() => createNewWorkflow(template)}
                        disabled={loading}
                      >
                        用此场景创建
                      </Button>
                    </article>
                  );
                })}
              </div>
            </div>

            <aside className="rounded-xl border border-slate-200 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
              <div className="flex items-center gap-2 text-sm font-medium text-indigo-600">
                <ClipboardCheck className="size-4" />
                上线前检查
              </div>
              <h2 className="mt-2 text-xl font-semibold text-slate-950">
                让流程先能被销售团队接住
              </h2>
              <div className="mt-4 space-y-3">
                {launchChecklist.map((item, index) => (
                  <div key={item} className="flex gap-3 text-sm text-slate-600">
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs font-semibold text-slate-500">
                      {index + 1}
                    </span>
                    <span className="leading-6">{item}</span>
                  </div>
                ))}
              </div>
              <div className="mt-5 rounded-lg bg-indigo-50 p-4 text-sm leading-6 text-indigo-700">
                建议先选择一个高频场景创建工作流，再在画布中补充判断节点、通知对象和异常兜底。
              </div>
            </aside>
          </div>

          <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
            <div className="relative w-full max-w-[360px]">
              <Search className="absolute right-4 top-1/2 size-5 -translate-y-1/2 text-slate-500" />
              <Input
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                className="h-14 rounded-lg border-slate-200 bg-white px-7 pr-12 text-base shadow-none"
                placeholder="搜索销售流程、场景或目录"
              />
            </div>
            <div className="text-sm text-slate-500">
              当前目录：{activeFolder}，共 {visibleWorkflows.length} 个工作流
            </div>
          </div>

          {loading ? (
            <div className="mt-12 rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
              正在加载工作流...
            </div>
          ) : (
            <div className="grid gap-5 xl:grid-cols-2 2xl:grid-cols-3">
              {visibleWorkflows.map((item) => {
                return (
                  <article
                    key={item.id}
                    role="button"
                    tabIndex={0}
                    className="group/card relative min-h-[168px] cursor-pointer rounded-2xl bg-white p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                    onClick={() => setEditingId(item.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        setEditingId(item.id);
                      }
                    }}
                  >
                    {!item.isBuiltin && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="absolute right-4 top-4 size-9 text-slate-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover/card:opacity-100"
                        title="删除工作流"
                        onClick={(event) => {
                          event.stopPropagation();
                          setWorkflowPendingDeleteId(item.id);
                        }}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    )}

                    <div className="mb-5 flex items-start gap-4 pr-10">
                      <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500 text-white shadow-sm">
                        <WorkflowIcon className="size-5" />
                      </span>
                      <div className="min-w-0">
                        <h2 className="truncate text-xl font-semibold text-slate-950">
                          {item.name}
                        </h2>
                      </div>
                    </div>

                    <p className="line-clamp-2 min-h-[52px] text-base leading-7 text-slate-500">
                      {item.description}
                    </p>
                  </article>
                );
              })}
            </div>
          )}

          <AlertDialog
            open={!!workflowPendingDelete}
            onOpenChange={(open) => {
              if (!open) {
                setWorkflowPendingDeleteId(null);
              }
            }}
          >
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>确认删除工作流</AlertDialogTitle>
                <AlertDialogDescription>
                  删除后无法恢复，确定要删除
                  {workflowPendingDelete
                    ? `「${workflowPendingDelete.name}」`
                    : ''}
                  吗？
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>取消</AlertDialogCancel>
                <AlertDialogAction
                  className="bg-red-600 text-white hover:bg-red-700"
                  onClick={deleteWorkflow}
                >
                  删除
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          {!loading && visibleWorkflows.length === 0 && (
            <div className="mt-12 flex min-h-[280px] items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white">
              <div className="text-center">
                <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                  <WorkflowIcon className="size-6" />
                </div>
                <h2 className="mt-4 text-lg font-semibold">暂无工作流</h2>
                <p className="mt-2 text-sm text-slate-500">
                  换一个目录，或新建一个工作流。
                </p>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
