import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type ElementType,
  type PointerEvent as ReactPointerEvent,
} from 'react';
import { createPortal } from 'react-dom';
import {
  Bell,
  BookOpen,
  Bot,
  Brain,
  Cable,
  GitBranch,
  Handshake,
  Eye,
  Image as ImageIcon,
  Link2,
  ListChecks,
  Maximize2,
  MessageSquare,
  Minimize2,
  MousePointer2,
  PackageSearch,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Plug,
  Plus,
  Save,
  Send,
  Sparkles,
  Tags,
  Trash2,
  Upload,
  UserRoundCheck,
  Volume2,
  Wrench,
} from 'lucide-react';
import { toast } from 'sonner';

import { httpClient } from '@/app/infra/http/HttpClient';
import { KnowledgeBase, LLMModel, SalesProduct } from '@/app/infra/entities/api';
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

import {
  createDefaultWorkflow,
  createSalesWorkflowTemplate,
  createSupportWorkflowTemplate,
  createWorkflowNode,
  getNodeDefaults,
} from './workflowTemplates';
import {
  PipelineWorkflow,
  PipelineWorkflowEdge,
  PipelineWorkflowNode,
  WorkflowNodeType,
} from './types';

const NODE_WIDTH = 220;
const NODE_HEIGHT = 76;

interface CanvasPoint {
  x: number;
  y: number;
}

interface DraftConnection {
  sourceId: string;
  pointer: CanvasPoint;
}

const nodeMeta: Record<
  WorkflowNodeType,
  {
    label: string;
    group: string;
    icon: ElementType;
    accent: string;
  }
> = {
  start: {
    label: '入口触发',
    group: '入口',
    icon: MessageSquare,
    accent: 'border-sky-200 bg-sky-50 text-sky-700',
  },
  channel: {
    label: '渠道接入',
    group: '入口',
    icon: Cable,
    accent: 'border-cyan-200 bg-cyan-50 text-cyan-700',
  },
  media: {
    label: '消息类型',
    group: '入口',
    icon: GitBranch,
    accent: 'border-slate-200 bg-slate-50 text-slate-700',
  },
  asr: {
    label: '语音转写',
    group: 'AI',
    icon: Volume2,
    accent: 'border-pink-200 bg-pink-50 text-pink-700',
  },
  intent: {
    label: '意图识别',
    group: 'AI',
    icon: Brain,
    accent: 'border-violet-200 bg-violet-50 text-violet-700',
  },
  router: {
    label: '意图路由',
    group: '控制',
    icon: GitBranch,
    accent: 'border-slate-200 bg-slate-50 text-slate-700',
  },
  knowledge: {
    label: '知识库',
    group: '资料',
    icon: BookOpen,
    accent: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  },
  product: {
    label: '产品库',
    group: '资料',
    icon: PackageSearch,
    accent: 'border-amber-200 bg-amber-50 text-amber-800',
  },
  task: {
    label: '任务步骤',
    group: '任务助手',
    icon: ListChecks,
    accent: 'border-blue-200 bg-blue-50 text-blue-700',
  },
  vision: {
    label: '截图识别',
    group: '任务助手',
    icon: Eye,
    accent: 'border-purple-200 bg-purple-50 text-purple-700',
  },
  llm: {
    label: 'AI 回复',
    group: 'AI',
    icon: Bot,
    accent: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  },
  condition: {
    label: '条件分支',
    group: '控制',
    icon: GitBranch,
    accent: 'border-slate-200 bg-slate-50 text-slate-700',
  },
  lead: {
    label: '线索收集',
    group: '销售',
    icon: UserRoundCheck,
    accent: 'border-rose-200 bg-rose-50 text-rose-700',
  },
  image: {
    label: '发送图片',
    group: '素材',
    icon: ImageIcon,
    accent: 'border-cyan-200 bg-cyan-50 text-cyan-700',
  },
  memory: {
    label: '客户记忆',
    group: '资料',
    icon: Tags,
    accent: 'border-lime-200 bg-lime-50 text-lime-700',
  },
  outreach: {
    label: '定时推送',
    group: '销售',
    icon: Bell,
    accent: 'border-orange-200 bg-orange-50 text-orange-700',
  },
  handoff: {
    label: '人工介入',
    group: '客服',
    icon: Handshake,
    accent: 'border-red-200 bg-red-50 text-red-700',
  },
  http: {
    label: 'HTTP',
    group: '工具',
    icon: Cable,
    accent: 'border-zinc-200 bg-zinc-50 text-zinc-700',
  },
  plugin: {
    label: '插件工具',
    group: '工具',
    icon: Plug,
    accent: 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700',
  },
  mcp: {
    label: 'MCP 工具',
    group: '工具',
    icon: Wrench,
    accent: 'border-teal-200 bg-teal-50 text-teal-700',
  },
  voice: {
    label: '语音回复',
    group: '任务助手',
    icon: Volume2,
    accent: 'border-pink-200 bg-pink-50 text-pink-700',
  },
  custom: {
    label: '自定义动作',
    group: '自定义',
    icon: Sparkles,
    accent: 'border-stone-200 bg-stone-50 text-stone-700',
  },
  end: {
    label: '最终回复',
    group: '出口',
    icon: Send,
    accent: 'border-green-200 bg-green-50 text-green-700',
  },
};

const paletteOrder: WorkflowNodeType[] = [
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

interface PipelineWorkflowEditorProps {
  value?: PipelineWorkflow;
  onChange: (workflow: PipelineWorkflow) => void;
}

function normalizeWorkflow(workflow?: PipelineWorkflow): PipelineWorkflow {
  if (!workflow || !Array.isArray(workflow.nodes) || !Array.isArray(workflow.edges)) {
    return createDefaultWorkflow();
  }
  return workflow;
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function asNumber(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    return value
      .split(/[\n,，]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function listToText(value: unknown): string {
  return asStringList(value).join('\n');
}

function makeEdge(source: string, target: string): PipelineWorkflowEdge {
  const id =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? `edge-${crypto.randomUUID().slice(0, 8)}`
      : `edge-${Math.random().toString(16).slice(2, 10)}`;
  return { id, source, target };
}

export default function PipelineWorkflowEditor({
  value,
  onChange,
}: PipelineWorkflowEditorProps) {
  const workflow = useMemo(() => normalizeWorkflow(value), [value]);
  const [selectedNodeId, setSelectedNodeId] = useState<string>(
    workflow.nodes[0]?.id ?? '',
  );
  const [draftConnection, setDraftConnection] = useState<DraftConnection | null>(null);
  const [connectionTargetId, setConnectionTargetId] = useState<string>('');
  const [uploadingNodeId, setUploadingNodeId] = useState<string>('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [llmModels, setLlmModels] = useState<LLMModel[]>([]);
  const [salesProducts, setSalesProducts] = useState<SalesProduct[]>([]);
  const dragRef = useRef<{
    id: string;
    offsetX: number;
    offsetY: number;
  } | null>(null);
  const canvasScrollRef = useRef<HTMLDivElement>(null);

  const selectedNode = workflow.nodes.find((node) => node.id === selectedNodeId);
  const imageNodes = workflow.nodes.filter((node) => node.type === 'image');

  useEffect(() => {
    if (!selectedNodeId && workflow.nodes[0]) {
      setSelectedNodeId(workflow.nodes[0].id);
    }
    if (selectedNodeId && !workflow.nodes.some((node) => node.id === selectedNodeId)) {
      setSelectedNodeId(workflow.nodes[0]?.id ?? '');
    }
  }, [selectedNodeId, workflow.nodes]);

  useEffect(() => {
    httpClient
      .getKnowledgeBases()
      .then((resp) => setKnowledgeBases(resp.bases || []))
      .catch((error) => console.warn('Failed to load knowledge bases', error));
    httpClient
      .getSalesProducts()
      .then((resp) => setSalesProducts(resp.products || []))
      .catch((error) => console.warn('Failed to load sales products', error));
    httpClient
      .getProviderLLMModels()
      .then((resp) => setLlmModels(resp.models || []))
      .catch((error) => console.warn('Failed to load LLM models', error));
  }, []);

  useEffect(() => {
    if (!draftConnection) return;

    function handleWindowPointerMove(event: PointerEvent) {
      setDraftConnection((current) =>
        current
          ? {
              ...current,
              pointer: clientPointToCanvasPoint(event.clientX, event.clientY),
            }
          : current,
      );
    }

    function handleWindowPointerUp() {
      setDraftConnection(null);
      setConnectionTargetId('');
    }

    window.addEventListener('pointermove', handleWindowPointerMove);
    window.addEventListener('pointerup', handleWindowPointerUp);
    return () => {
      window.removeEventListener('pointermove', handleWindowPointerMove);
      window.removeEventListener('pointerup', handleWindowPointerUp);
    };
  }, [draftConnection?.sourceId]);

  useEffect(() => {
    if (!isFullscreen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [isFullscreen]);

  function commit(next: PipelineWorkflow) {
    onChange(next);
  }

  function updateWorkflow(patch: Partial<PipelineWorkflow>) {
    commit({ ...workflow, ...patch });
  }

  function updateNode(
    nodeId: string,
    patch: Partial<PipelineWorkflowNode>,
  ) {
    commit({
      ...workflow,
      nodes: workflow.nodes.map((node) =>
        node.id === nodeId ? { ...node, ...patch } : node,
      ),
    });
  }

  function updateNodeConfig(nodeId: string, patch: Record<string, unknown>) {
    commit({
      ...workflow,
      nodes: workflow.nodes.map((node) =>
        node.id === nodeId
          ? { ...node, config: { ...node.config, ...patch } }
          : node,
      ),
    });
  }

  function addNode(type: WorkflowNodeType) {
    const canvas = canvasScrollRef.current;
    const visibleX = canvas ? canvas.scrollLeft + 96 : 120;
    const visibleY = canvas ? canvas.scrollTop + 96 : 120;
    const nextNode = createWorkflowNode(type, {
      x: Math.max(24, visibleX),
      y: Math.max(24, visibleY),
    });
    commit({ ...workflow, nodes: [...workflow.nodes, nextNode] });
    setSelectedNodeId(nextNode.id);
    window.requestAnimationFrame(() => {
      document
        .querySelector(`[data-workflow-node-id="${nextNode.id}"]`)
        ?.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' });
    });
  }

  function deleteNode(nodeId: string) {
    commit({
      ...workflow,
      nodes: workflow.nodes.filter((node) => node.id !== nodeId),
      edges: workflow.edges.filter(
        (edge) => edge.source !== nodeId && edge.target !== nodeId,
      ),
    });
    setSelectedNodeId(workflow.nodes.find((node) => node.id !== nodeId)?.id ?? '');
  }

  function connectNodes(sourceId: string, targetId: string) {
    if (sourceId === targetId) return;
    const exists = workflow.edges.some(
      (edge) => edge.source === sourceId && edge.target === targetId,
    );
    if (!exists) {
      commit({
        ...workflow,
        edges: [...workflow.edges, makeEdge(sourceId, targetId)],
      });
    }
  }

  function deleteEdge(edgeId: string) {
    commit({
      ...workflow,
      edges: workflow.edges.filter((edge) => edge.id !== edgeId),
    });
  }

  function handleNodePointerDown(
    event: ReactPointerEvent<HTMLDivElement>,
    node: PipelineWorkflowNode,
  ) {
    if ((event.target as HTMLElement).closest('[data-node-action]')) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      id: node.id,
      offsetX: event.clientX - node.position.x,
      offsetY: event.clientY - node.position.y,
    };
    setSelectedNodeId(node.id);
  }

  function handleNodePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    updateNode(drag.id, {
      position: {
        x: Math.max(24, event.clientX - drag.offsetX),
        y: Math.max(24, event.clientY - drag.offsetY),
      },
    });
  }

  function handleNodePointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    if (dragRef.current) {
      event.currentTarget.releasePointerCapture(event.pointerId);
      dragRef.current = null;
    }
  }

  function clientPointToCanvasPoint(clientX: number, clientY: number): CanvasPoint {
    const canvas = canvasScrollRef.current;
    if (!canvas) return { x: clientX, y: clientY };
    const rect = canvas.getBoundingClientRect();
    return {
      x: clientX - rect.left + canvas.scrollLeft,
      y: clientY - rect.top + canvas.scrollTop,
    };
  }

  function handleConnectionStart(
    event: ReactPointerEvent<HTMLButtonElement>,
    node: PipelineWorkflowNode,
  ) {
    event.preventDefault();
    event.stopPropagation();
    setSelectedNodeId(node.id);
    setDraftConnection({
      sourceId: node.id,
      pointer: clientPointToCanvasPoint(event.clientX, event.clientY),
    });
  }

  function handleConnectionEnd(
    event: ReactPointerEvent<HTMLButtonElement>,
    targetId: string,
  ) {
    event.preventDefault();
    event.stopPropagation();
    if (draftConnection) {
      connectNodes(draftConnection.sourceId, targetId);
    }
    setDraftConnection(null);
    setConnectionTargetId('');
  }

  async function uploadImageForNode(
    node: PipelineWorkflowNode,
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      setUploadingNodeId(node.id);
      const result = await httpClient.uploadImage(file);
      updateNodeConfig(node.id, { file_key: result.file_key, image_url: '' });
      toast.success('图片已绑定到节点');
    } catch (error) {
      console.error('Workflow image upload failed:', error);
      toast.error('图片上传失败');
    } finally {
      setUploadingNodeId('');
      event.target.value = '';
    }
  }

  function imageAssetUrl(fileKey: string) {
    const baseUrl = httpClient.getBaseUrl();
    const prefix = baseUrl === '/' ? '' : baseUrl.replace(/\/$/, '');
    return `${prefix}/api/v1/files/image/${encodeURIComponent(fileKey)}`;
  }

  function nodeOutputPoint(nodeId: string) {
    const node = workflow.nodes.find((item) => item.id === nodeId);
    if (!node) return { x: 0, y: 0 };
    return {
      x: node.position.x + NODE_WIDTH,
      y: node.position.y + NODE_HEIGHT / 2,
    };
  }

  function nodeInputPoint(nodeId: string) {
    const node = workflow.nodes.find((item) => item.id === nodeId);
    if (!node) return { x: 0, y: 0 };
    return {
      x: node.position.x,
      y: node.position.y + NODE_HEIGHT / 2,
    };
  }

  function edgePath(source: CanvasPoint, target: CanvasPoint) {
    const bend = Math.max(80, Math.abs(target.x - source.x) / 2);
    return `M ${source.x} ${source.y} C ${source.x + bend} ${source.y}, ${target.x - bend} ${target.y}, ${target.x} ${target.y}`;
  }

  const groupedPalette = paletteOrder.reduce<Record<string, WorkflowNodeType[]>>(
    (groups, type) => {
      const group = nodeMeta[type].group;
      groups[group] = groups[group] || [];
      groups[group].push(type);
      return groups;
    },
    {},
  );

  const editor = (
    <div
      className={cn(
        'flex overflow-hidden bg-background',
        isFullscreen
          ? 'h-full w-full'
          : 'h-[calc(100vh-240px)] min-h-[640px] rounded-lg border',
      )}
    >
      {!leftPanelCollapsed ? (
      <aside className="flex w-64 shrink-0 flex-col border-r bg-muted/20">
        <div className="border-b p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-semibold">工作流模板</div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7 shrink-0"
              title="收起节点库"
              onClick={() => setLeftPanelCollapsed(true)}
            >
              <PanelLeftClose className="size-4" />
            </Button>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button
              type="button"
              size="sm"
              variant={workflow.scenario === 'sales' ? 'default' : 'outline'}
              onClick={() => {
                const next = createSalesWorkflowTemplate();
                commit(next);
                setSelectedNodeId(next.nodes[0]?.id ?? '');
              }}
            >
              销售
            </Button>
            <Button
              type="button"
              size="sm"
              variant={workflow.scenario === 'support' ? 'default' : 'outline'}
              onClick={() => {
                const next = createSupportWorkflowTemplate();
                commit(next);
                setSelectedNodeId(next.nodes[0]?.id ?? '');
              }}
            >
              客服
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          <div className="mb-2 text-sm font-semibold">节点库</div>
          <div className="space-y-4">
            {Object.entries(groupedPalette).map(([group, types]) => (
              <div key={group}>
                <div className="mb-1.5 text-xs font-medium text-muted-foreground">
                  {group}
                </div>
                <div className="grid gap-1.5">
                  {types.map((type) => {
                    const meta = nodeMeta[type];
                    const Icon = meta.icon;
                    return (
                      <button
                        key={type}
                        type="button"
                        onClick={() => addNode(type)}
                        className="flex items-center justify-between rounded-md border bg-background px-2.5 py-2 text-left text-sm transition-colors hover:bg-accent"
                      >
                        <span className="flex min-w-0 items-center gap-2">
                          <Icon className="size-4 shrink-0 text-muted-foreground" />
                          <span className="truncate">{meta.label}</span>
                        </span>
                        <Plus className="size-3.5 shrink-0 text-muted-foreground" />
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      </aside>
      ) : (
        <div className="flex w-10 shrink-0 flex-col items-center border-r bg-muted/20 py-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8"
            title="展开节点库"
            onClick={() => setLeftPanelCollapsed(false)}
          >
            <PanelLeftOpen className="size-4" />
          </Button>
        </div>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b px-3 py-2">
          {leftPanelCollapsed && (
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="size-8 shrink-0"
              title="展开节点库"
              onClick={() => setLeftPanelCollapsed(false)}
            >
              <PanelLeftOpen className="size-4" />
            </Button>
          )}
          <Input
            value={workflow.name}
            onChange={(event) => updateWorkflow({ name: event.target.value })}
            className="h-8 max-w-xs"
          />
          <Badge variant="secondary">{workflow.nodes.length} 个节点</Badge>
          <Badge variant="secondary">{workflow.edges.length} 条连线</Badge>
          {draftConnection && (
            <Badge className="gap-1 bg-amber-100 text-amber-800 hover:bg-amber-100">
              <Link2 className="size-3" />
              拖到目标输入点
            </Badge>
          )}
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-xs text-muted-foreground xl:inline-flex xl:items-center xl:gap-1.5">
              <MousePointer2 className="size-3.5" />
              拖动节点调整流程，从右侧圆点拉线
            </span>
            {rightPanelCollapsed && (
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="size-8"
                title="展开节点配置"
                onClick={() => setRightPanelCollapsed(false)}
              >
                <PanelRightOpen className="size-4" />
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="size-8"
              title={isFullscreen ? '退出全屏' : '全屏编辑'}
              onClick={() => setIsFullscreen((current) => !current)}
            >
              {isFullscreen ? (
                <Minimize2 className="size-4" />
              ) : (
                <Maximize2 className="size-4" />
              )}
            </Button>
          </div>
        </div>

        <div ref={canvasScrollRef} className="relative min-h-0 flex-1 overflow-auto bg-[#f7f7f2]">
          <div
            className="relative min-h-[760px] min-w-[2360px]"
            style={{
              backgroundImage:
                'linear-gradient(rgba(15,23,42,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(15,23,42,0.06) 1px, transparent 1px)',
              backgroundSize: '24px 24px',
            }}
          >
            <svg className="absolute inset-0 h-full w-full overflow-visible">
              <defs>
                <marker
                  id="workflow-arrow"
                  markerHeight="8"
                  markerWidth="8"
                  orient="auto"
                  refX="7"
                  refY="4"
                >
                  <path d="M0,0 L8,4 L0,8 Z" fill="#64748b" />
                </marker>
              </defs>
              {workflow.edges.map((edge) => {
                const source = nodeOutputPoint(edge.source);
                const target = nodeInputPoint(edge.target);
                if (!source.x && !target.x) return null;
                const path = edgePath(source, target);
                return (
                  <g key={edge.id}>
                    <path
                      d={path}
                      fill="none"
                      markerEnd="url(#workflow-arrow)"
                      stroke="#64748b"
                      strokeWidth="2"
                      pointerEvents="none"
                    />
                    <path
                      d={path}
                      fill="none"
                      stroke="transparent"
                      strokeWidth="14"
                      pointerEvents="stroke"
                      onClick={() => deleteEdge(edge.id)}
                      className="cursor-pointer"
                    />
                    {edge.label && (
                      <text
                        x={(source.x + target.x) / 2}
                        y={(source.y + target.y) / 2 - 8}
                        className="fill-slate-500 text-[11px]"
                        textAnchor="middle"
                      >
                        {edge.label}
                      </text>
                    )}
                  </g>
                );
              })}
              {draftConnection && (
                <path
                  data-workflow-draft-edge
                  d={edgePath(nodeOutputPoint(draftConnection.sourceId), draftConnection.pointer)}
                  fill="none"
                  stroke="#2563eb"
                  strokeDasharray="7 5"
                  strokeLinecap="round"
                  strokeWidth="2.5"
                  pointerEvents="none"
                />
              )}
            </svg>

            {workflow.nodes.map((node) => {
              const meta = nodeMeta[node.type];
              const Icon = meta.icon;
              const selected = selectedNodeId === node.id;
              const connecting = draftConnection?.sourceId === node.id;
              const receiving = connectionTargetId === node.id;
              const canReceive = node.type !== 'start';
              const canSend = node.type !== 'end';
              return (
                <div
                  key={node.id}
                  data-workflow-node-id={node.id}
                  onPointerDown={(event) => handleNodePointerDown(event, node)}
                  onPointerMove={handleNodePointerMove}
                  onPointerUp={handleNodePointerUp}
                  className={cn(
                    'absolute cursor-grab select-none rounded-lg border bg-white p-3 shadow-sm transition-shadow active:cursor-grabbing',
                    selected && 'ring-2 ring-slate-900',
                    connecting && 'ring-2 ring-amber-500',
                    receiving && 'ring-2 ring-blue-500',
                  )}
                  style={{
                    left: node.position.x,
                    top: node.position.y,
                    width: NODE_WIDTH,
                    minHeight: NODE_HEIGHT,
                  }}
                >
                  {canReceive && (
                    <button
                      type="button"
                      aria-label={`连接到 ${node.title}`}
                      data-node-action
                      data-workflow-port="input"
                      onPointerEnter={() => {
                        if (draftConnection && draftConnection.sourceId !== node.id) {
                          setConnectionTargetId(node.id);
                        }
                      }}
                      onPointerLeave={() => {
                        if (connectionTargetId === node.id) {
                          setConnectionTargetId('');
                        }
                      }}
                      onPointerUp={(event) => handleConnectionEnd(event, node.id)}
                      className={cn(
                        'absolute -left-2 top-1/2 z-10 size-4 -translate-y-1/2 rounded-full border-2 border-white bg-slate-300 shadow-sm transition-colors',
                        draftConnection &&
                          draftConnection.sourceId !== node.id &&
                          'bg-blue-500 ring-4 ring-blue-100',
                      )}
                    />
                  )}
                  {canSend && (
                    <button
                      type="button"
                      aria-label={`从 ${node.title} 连线`}
                      data-node-action
                      data-workflow-port="output"
                      onPointerDown={(event) => handleConnectionStart(event, node)}
                      className={cn(
                        'absolute -right-2 top-1/2 z-10 size-4 -translate-y-1/2 cursor-crosshair rounded-full border-2 border-white bg-slate-800 shadow-sm transition-colors hover:bg-blue-600',
                        connecting && 'bg-blue-600 ring-4 ring-blue-100',
                      )}
                    />
                  )}
                  <div className="flex items-start gap-2">
                    <div className={cn('rounded-md border p-1.5', meta.accent)}>
                      <Icon className="size-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold">
                        {node.title}
                      </div>
                      <div className="truncate text-xs text-muted-foreground">
                        {node.description || meta.label}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        data-node-action
                        title="删除节点"
                        onClick={() => deleteNode(node.id)}
                        className="rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>

      {!rightPanelCollapsed ? (
      <aside className="flex w-80 shrink-0 flex-col border-l bg-background">
        <div className="border-b p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-semibold">节点配置</div>
            <div className="flex items-center gap-1">
              <Save className="size-4 text-muted-foreground" />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-7"
                title="收起节点配置"
                onClick={() => setRightPanelCollapsed(true)}
              >
                <PanelRightClose className="size-4" />
              </Button>
            </div>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {selectedNode ? (
            <NodeConfigPanel
              imageNodes={imageNodes}
              knowledgeBases={knowledgeBases}
              llmModels={llmModels}
              node={selectedNode}
              products={salesProducts}
              uploading={uploadingNodeId === selectedNode.id}
              imageAssetUrl={imageAssetUrl}
              onNodeChange={(patch) => updateNode(selectedNode.id, patch)}
              onConfigChange={(patch) => updateNodeConfig(selectedNode.id, patch)}
              onUploadImage={(event) => uploadImageForNode(selectedNode, event)}
            />
          ) : (
            <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
              请选择一个节点
            </div>
          )}

          <div className="mt-4">
            <div className="mb-2 text-xs font-medium text-muted-foreground">
              连线
            </div>
            <div className="space-y-1.5">
              {workflow.edges.map((edge) => {
                const source = workflow.nodes.find((node) => node.id === edge.source);
                const target = workflow.nodes.find((node) => node.id === edge.target);
                return (
                  <div
                    key={edge.id}
                    className="flex items-center gap-2 rounded-md border px-2 py-1.5 text-xs"
                  >
                    <span className="min-w-0 flex-1 truncate">
                      {`${source?.title ?? edge.source} -> ${target?.title ?? edge.target}`}
                    </span>
                    <button
                      type="button"
                      onClick={() => deleteEdge(edge.id)}
                      className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                    >
                      <Trash2 className="size-3" />
                    </button>
                  </div>
                );
              })}
              {!workflow.edges.length && (
                <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
                  暂无连线
                </div>
              )}
            </div>
          </div>
        </div>
      </aside>
      ) : null}
    </div>
  );

  if (isFullscreen && typeof document !== 'undefined') {
    return createPortal(
      <div className="fixed inset-0 z-50 flex flex-col bg-background">
        <div className="flex items-center justify-between border-b px-4 py-2">
          <div className="min-w-0">
            <div className="text-sm font-semibold">工作流全屏编辑</div>
            <div className="truncate text-xs text-muted-foreground">
              {workflow.name || '未命名工作流'}
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-1.5"
            onClick={() => setIsFullscreen(false)}
          >
            <Minimize2 className="size-4" />
            退出全屏
          </Button>
        </div>
        <div className="min-h-0 flex-1">{editor}</div>
      </div>,
      document.body,
    );
  }

  return editor;
}

function NodeConfigPanel({
  imageNodes,
  imageAssetUrl,
  knowledgeBases,
  llmModels,
  node,
  products,
  uploading,
  onConfigChange,
  onNodeChange,
  onUploadImage,
}: {
  imageNodes: PipelineWorkflowNode[];
  imageAssetUrl: (fileKey: string) => string;
  knowledgeBases: KnowledgeBase[];
  llmModels: LLMModel[];
  node: PipelineWorkflowNode;
  products: SalesProduct[];
  uploading: boolean;
  onNodeChange: (patch: Partial<PipelineWorkflowNode>) => void;
  onConfigChange: (patch: Record<string, unknown>) => void;
  onUploadImage: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  const defaults = getNodeDefaults(node.type);
  const fileKey = asString(node.config.file_key);
  const imageUrl = asString(node.config.image_url);
  const previewUrl = fileKey ? imageAssetUrl(fileKey) : imageUrl;
  const selectedKbIds = asStringList(node.config.knowledge_base_uuids);
  const selectedProductIds = asStringList(node.config.product_uuids);

  function toggleListValue(field: string, value: string) {
    const current = asStringList(node.config[field]);
    const next = current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value];
    onConfigChange({ [field]: next });
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground">名称</label>
        <Input
          value={node.title}
          onChange={(event) => onNodeChange({ title: event.target.value })}
        />
      </div>
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground">说明</label>
        <Input
          value={node.description ?? ''}
          placeholder={defaults.description}
          onChange={(event) => onNodeChange({ description: event.target.value })}
        />
      </div>

      {node.type === 'llm' && (
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">
            回复模型
          </label>
          <Select
            value={asString(node.config.model_uuid) || '__none__'}
            onValueChange={(value) =>
              onConfigChange({ model_uuid: value === '__none__' ? '' : value })
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="选择 AI 回复模型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">跟随流水线默认模型</SelectItem>
              {llmModels.map((model) => (
                <SelectItem key={model.uuid} value={model.uuid}>
                  {model.name}
                  {model.provider?.name ? ` · ${model.provider.name}` : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            保存后会同步为这条流水线实际调用的主模型。
          </p>
        </div>
      )}

      {node.type === 'intent' && (
        <>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              意图标签
            </label>
            <Textarea
              value={listToText(node.config.intents)}
              onChange={(event) =>
                onConfigChange({ intents: asStringList(event.target.value) })
              }
              className="min-h-28"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              触发图片回复的意图
            </label>
            <Textarea
              value={listToText(node.config.image_intents)}
              onChange={(event) =>
                onConfigChange({ image_intents: asStringList(event.target.value) })
              }
              className="min-h-20"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              置信度阈值
            </label>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={asNumber(node.config.confidence_threshold, 0.72)}
              onChange={(event) =>
                onConfigChange({ confidence_threshold: Number(event.target.value) })
              }
            />
          </div>
          <div className="rounded-md border bg-muted/30 p-3">
            <div className="mb-2 text-xs font-medium text-muted-foreground">
              可用图片节点
            </div>
            <div className="space-y-1 text-xs">
              {imageNodes.map((imageNode) => (
                <div key={imageNode.id} className="rounded bg-background px-2 py-1">
                  {imageNode.title}：{listToText(imageNode.config.trigger_intents) || '未绑定意图'}
                </div>
              ))}
              {!imageNodes.length && <div className="text-muted-foreground">暂无图片节点</div>}
            </div>
          </div>
        </>
      )}

      {node.type === 'knowledge' && (
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">
            关联知识库
          </label>
          <div className="space-y-1.5">
            {knowledgeBases.map((kb) => (
              <button
                key={kb.uuid}
                type="button"
                onClick={() => toggleListValue('knowledge_base_uuids', kb.uuid || '')}
                className={cn(
                  'flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm',
                  selectedKbIds.includes(kb.uuid || '')
                    ? 'border-slate-900 bg-slate-50'
                    : 'bg-background hover:bg-accent',
                )}
              >
                <span className="truncate">{kb.name}</span>
                {selectedKbIds.includes(kb.uuid || '') && <Badge>已选</Badge>}
              </button>
            ))}
            {!knowledgeBases.length && (
              <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                暂无知识库
              </div>
            )}
          </div>
          <Input
            type="number"
            min={1}
            value={asNumber(node.config.top_k, 5)}
            onChange={(event) => onConfigChange({ top_k: Number(event.target.value) })}
          />
        </div>
      )}

      {node.type === 'product' && (
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">
            关联产品
          </label>
          <div className="space-y-1.5">
            {products.map((product) => (
              <button
                key={product.uuid}
                type="button"
                onClick={() => toggleListValue('product_uuids', product.uuid || '')}
                className={cn(
                  'flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm',
                  selectedProductIds.includes(product.uuid || '')
                    ? 'border-slate-900 bg-slate-50'
                    : 'bg-background hover:bg-accent',
                )}
              >
                <span className="min-w-0">
                  <span className="block truncate">{product.name}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {product.price || product.category}
                  </span>
                </span>
                {selectedProductIds.includes(product.uuid || '') && <Badge>已选</Badge>}
              </button>
            ))}
            {!products.length && (
              <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                暂无产品
              </div>
            )}
          </div>
        </div>
      )}

      {node.type === 'llm' && (
        <>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">语气</label>
            <Select
              value={asString(node.config.tone, 'professional')}
              onValueChange={(value) => onConfigChange({ tone: value })}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="professional">专业克制</SelectItem>
                <SelectItem value="consultative">顾问式销售</SelectItem>
                <SelectItem value="friendly">亲和客服</SelectItem>
                <SelectItem value="concise">简洁直接</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              提示词
            </label>
            <Textarea
              value={asString(node.config.prompt)}
              onChange={(event) => onConfigChange({ prompt: event.target.value })}
              className="min-h-36"
            />
          </div>
        </>
      )}

      {node.type === 'image' && (
        <>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              触发意图
            </label>
            <Textarea
              value={listToText(node.config.trigger_intents)}
              onChange={(event) =>
                onConfigChange({ trigger_intents: asStringList(event.target.value) })
              }
              className="min-h-20"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              图片
            </label>
            <input
              id={`workflow-image-${node.id}`}
              className="hidden"
              type="file"
              accept="image/*"
              onChange={onUploadImage}
            />
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={uploading}
                onClick={() =>
                  document.getElementById(`workflow-image-${node.id}`)?.click()
                }
              >
                <Upload className="mr-1.5 size-4" />
                {uploading ? '上传中' : '上传'}
              </Button>
              <Input
                value={imageUrl}
                placeholder="https://..."
                onChange={(event) =>
                  onConfigChange({ image_url: event.target.value, file_key: '' })
                }
              />
            </div>
            {previewUrl && (
              <div className="overflow-hidden rounded-md border bg-muted">
                <img
                  src={previewUrl}
                  alt={node.title}
                  className="max-h-44 w-full object-contain"
                />
              </div>
            )}
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              图片配文
            </label>
            <Textarea
              value={asString(node.config.caption)}
              onChange={(event) => onConfigChange({ caption: event.target.value })}
              className="min-h-20"
            />
          </div>
        </>
      )}

      {node.type === 'condition' && (
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">
            分支规则
          </label>
          <Textarea
            value={listToText(node.config.rules)}
            onChange={(event) => onConfigChange({ rules: asStringList(event.target.value) })}
            className="min-h-28 font-mono text-xs"
          />
        </div>
      )}

      {node.type === 'lead' && (
        <>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              收集字段
            </label>
            <Textarea
              value={listToText(node.config.fields)}
              onChange={(event) => onConfigChange({ fields: asStringList(event.target.value) })}
              className="min-h-24"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              必填字段
            </label>
            <Input
              value={asStringList(node.config.required_fields).join('，')}
              onChange={(event) =>
                onConfigChange({ required_fields: asStringList(event.target.value) })
              }
            />
          </div>
        </>
      )}

      {node.type === 'handoff' && (
        <>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              介入原因
            </label>
            <Input
              value={asString(node.config.reason)}
              onChange={(event) => onConfigChange({ reason: event.target.value })}
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              指派给
            </label>
            <Input
              value={asString(node.config.assigned_to)}
              onChange={(event) => onConfigChange({ assigned_to: event.target.value })}
            />
          </div>
        </>
      )}

      {node.type === 'outreach' && (
        <>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              延迟分钟
            </label>
            <Input
              type="number"
              min={0}
              value={asNumber(node.config.delay_minutes, 1440)}
              onChange={(event) =>
                onConfigChange({ delay_minutes: Number(event.target.value) })
              }
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              推送内容
            </label>
            <Textarea
              value={asString(node.config.message_template)}
              onChange={(event) =>
                onConfigChange({ message_template: event.target.value })
              }
              className="min-h-24"
            />
          </div>
        </>
      )}

      {[
        'http',
        'plugin',
        'mcp',
        'custom',
        'memory',
        'start',
        'channel',
        'media',
        'asr',
        'router',
        'task',
        'vision',
        'voice',
        'end',
      ].includes(
        node.type,
      ) && <GenericConfig node={node} onConfigChange={onConfigChange} />}
    </div>
  );
}

function GenericConfig({
  node,
  onConfigChange,
}: {
  node: PipelineWorkflowNode;
  onConfigChange: (patch: Record<string, unknown>) => void;
}) {
  if (node.type === 'http') {
    return (
      <>
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">方法</label>
          <Select
            value={asString(node.config.method, 'POST')}
            onValueChange={(value) => onConfigChange({ method: value })}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="GET">GET</SelectItem>
              <SelectItem value="POST">POST</SelectItem>
              <SelectItem value="PUT">PUT</SelectItem>
              <SelectItem value="DELETE">DELETE</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">URL</label>
          <Input
            value={asString(node.config.url)}
            onChange={(event) => onConfigChange({ url: event.target.value })}
          />
        </div>
        <JsonLikeTextarea
          label="请求模板"
          value={asString(node.config.body_template, '{}')}
          onChange={(value) => onConfigChange({ body_template: value })}
        />
      </>
    );
  }

  if (node.type === 'plugin' || node.type === 'mcp' || node.type === 'custom') {
    return (
      <>
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">
            {node.type === 'custom' ? '输出字段' : '工具名称'}
          </label>
          <Input
            value={asString(node.config.tool || node.config.output_key)}
            onChange={(event) =>
              onConfigChange(
                node.type === 'custom'
                  ? { output_key: event.target.value }
                  : { tool: event.target.value },
              )
            }
          />
        </div>
        <JsonLikeTextarea
          label="参数"
          value={asString(node.config.params, '{}')}
          onChange={(value) => onConfigChange({ params: value })}
        />
      </>
    );
  }

  if (node.type === 'memory') {
    return (
      <>
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">
            客户阶段
          </label>
          <Input
            value={asString(node.config.stage, 'new')}
            onChange={(event) => onConfigChange({ stage: event.target.value })}
          />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">
            标签
          </label>
          <Input
            value={asStringList(node.config.tags).join('，')}
            onChange={(event) => onConfigChange({ tags: asStringList(event.target.value) })}
          />
        </div>
      </>
    );
  }

  if (node.type === 'end') {
    return (
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground">
          结束动作
        </label>
        <Select
          value={node.config.close_conversation ? 'close' : 'keep'}
          onValueChange={(value) =>
            onConfigChange({ close_conversation: value === 'close' })
          }
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="keep">保持会话</SelectItem>
            <SelectItem value="close">关闭会话</SelectItem>
          </SelectContent>
        </Select>
      </div>
    );
  }

  return (
    <JsonLikeTextarea
      label="配置"
      value={JSON.stringify(node.config, null, 2)}
      onChange={(value) => {
        try {
          onConfigChange(JSON.parse(value) as Record<string, unknown>);
        } catch {
          onConfigChange({ raw_config: value });
        }
      }}
    />
  );
}

function JsonLikeTextarea({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <Textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-28 font-mono text-xs"
      />
    </div>
  );
}
