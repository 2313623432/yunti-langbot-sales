import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent as ReactDragEvent,
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
  Code2,
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
  PanelRightClose,
  PanelRightOpen,
  PlayCircle,
  Plug,
  Plus,
  RadioTower,
  Save,
  Search,
  Send,
  Settings2,
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
import {
  KnowledgeBase,
  LLMModel,
  SalesProduct,
  WorkflowComponentFamily,
  WorkflowComponentField,
  WorkflowComponentSchema,
} from '@/app/infra/entities/api';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
  radar: {
    label: '雷达监测',
    group: '销售',
    icon: RadioTower,
    accent: 'border-sky-200 bg-sky-50 text-sky-700',
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
  'radar',
  'outreach',
  'handoff',
  'http',
  'plugin',
  'mcp',
  'voice',
  'custom',
  'end',
];

const iconByName: Record<string, ElementType> = {
  Bell,
  BookOpen,
  Bot,
  Brain,
  Cable,
  Code2,
  Eye,
  GitBranch,
  Handshake,
  Image: ImageIcon,
  ImageIcon,
  ListChecks,
  MessageSquare,
  PackageSearch,
  Plug,
  RadioTower,
  Send,
  Sparkles,
  Tags,
  UserRoundCheck,
  Volume2,
  Wrench,
};

interface PipelineWorkflowEditorProps {
  value?: PipelineWorkflow;
  onChange: (workflow: PipelineWorkflow) => void;
}

function normalizeWorkflow(workflow?: PipelineWorkflow): PipelineWorkflow {
  if (
    !workflow ||
    !Array.isArray(workflow.nodes) ||
    !Array.isArray(workflow.edges)
  ) {
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

function groupPaletteTypes(types: WorkflowNodeType[]) {
  return types.reduce<Record<string, WorkflowNodeType[]>>((groups, type) => {
    const group = nodeMeta[type].group;
    groups[group] = groups[group] || [];
    groups[group].push(type);
    return groups;
  }, {});
}

function filterPaletteTypes(query: string, includeStart = false) {
  const normalizedQuery = query.trim().toLowerCase();
  const availableTypes = paletteOrder.filter(
    (type) => includeStart || type !== 'start',
  );
  if (!normalizedQuery) return availableTypes;
  return availableTypes.filter((type) => {
    const meta = nodeMeta[type];
    return (
      meta.label.toLowerCase().includes(normalizedQuery) ||
      meta.group.toLowerCase().includes(normalizedQuery) ||
      type.toLowerCase().includes(normalizedQuery)
    );
  });
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
  const [draftConnection, setDraftConnection] =
    useState<DraftConnection | null>(null);
  const [connectionTargetId, setConnectionTargetId] = useState<string>('');
  const [uploadingNodeId, setUploadingNodeId] = useState<string>('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [hoveredOutputNodeId, setHoveredOutputNodeId] = useState<string>('');
  const [addNodeMenuSourceId, setAddNodeMenuSourceId] = useState<string>('');
  const [nodePaletteOpen, setNodePaletteOpen] = useState(false);
  const [nodePaletteSearch, setNodePaletteSearch] = useState('');
  const [librarySearch, setLibrarySearch] = useState('');
  const [componentFamilies, setComponentFamilies] = useState<
    WorkflowComponentFamily[]
  >([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [llmModels, setLlmModels] = useState<LLMModel[]>([]);
  const [salesProducts, setSalesProducts] = useState<SalesProduct[]>([]);
  const dragRef = useRef<{
    id: string;
    offsetX: number;
    offsetY: number;
  } | null>(null);
  const canvasPanRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    scrollLeft: number;
    scrollTop: number;
  } | null>(null);
  const canvasScrollRef = useRef<HTMLDivElement>(null);
  const addNodeMenuRef = useRef<HTMLDivElement>(null);

  const selectedNode = workflow.nodes.find(
    (node) => node.id === selectedNodeId,
  );
  const imageNodes = workflow.nodes.filter((node) => node.type === 'image');
  const draftConnectionSourceId = draftConnection?.sourceId;
  const componentSchemaByType = useMemo(() => {
    const schemas: Record<string, WorkflowComponentSchema> = {};
    componentFamilies.forEach((family) => {
      family.components.forEach((component) => {
        schemas[component.type] = component;
      });
    });
    return schemas;
  }, [componentFamilies]);

  useEffect(() => {
    if (!selectedNodeId && workflow.nodes[0]) {
      setSelectedNodeId(workflow.nodes[0].id);
    }
    if (
      selectedNodeId &&
      !workflow.nodes.some((node) => node.id === selectedNodeId)
    ) {
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
      .getProviderLLMModels(undefined, {
        include_space_models: false,
        include_system_models: false,
        only_configured_providers: true,
        model_category: 'text',
      })
      .then((resp) => setLlmModels(resp.models || []))
      .catch((error) => console.warn('Failed to load LLM models', error));
    httpClient
      .getWorkflowComponents()
      .then((resp) => setComponentFamilies(resp.families || []))
      .catch((error) =>
        console.warn('Failed to load workflow components', error),
      );
  }, []);

  useEffect(() => {
    if (!draftConnectionSourceId) return;

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
  }, [draftConnectionSourceId]);

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

  useEffect(() => {
    if (!addNodeMenuSourceId && !nodePaletteOpen) return;

    function handlePointerDown(event: PointerEvent) {
      const target = event.target as HTMLElement;
      if (
        target.closest('[data-node-add-trigger]') ||
        target.closest('[data-node-palette-trigger]') ||
        target.closest('[data-node-add-menu]')
      ) {
        return;
      }
      setAddNodeMenuSourceId('');
      setNodePaletteOpen(false);
      setNodePaletteSearch('');
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setAddNodeMenuSourceId('');
        setNodePaletteOpen(false);
        setNodePaletteSearch('');
      }
    }

    window.addEventListener('pointerdown', handlePointerDown);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('pointerdown', handlePointerDown);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [addNodeMenuSourceId, nodePaletteOpen]);

  function commit(next: PipelineWorkflow) {
    onChange(next);
  }

  function updateWorkflow(patch: Partial<PipelineWorkflow>) {
    commit({ ...workflow, ...patch });
  }

  function updateNode(nodeId: string, patch: Partial<PipelineWorkflowNode>) {
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

  function addNodeAt(
    type: WorkflowNodeType,
    position: CanvasPoint,
    sourceId?: string,
  ) {
    const source = sourceId
      ? workflow.nodes.find((node) => node.id === sourceId)
      : undefined;
    const nextNode = createWorkflowNode(type, {
      x: Math.max(
        24,
        source ? source.position.x + NODE_WIDTH + 100 : position.x,
      ),
      y: Math.max(24, source ? source.position.y : position.y),
    });
    const edges = [...workflow.edges];
    if (source && type !== 'start') {
      const exists = edges.some(
        (edge) => edge.source === source.id && edge.target === nextNode.id,
      );
      if (!exists) {
        edges.push(makeEdge(source.id, nextNode.id));
      }
    }
    commit({ ...workflow, nodes: [...workflow.nodes, nextNode], edges });
    setSelectedNodeId(nextNode.id);
    setAddNodeMenuSourceId('');
    setHoveredOutputNodeId('');
    setNodePaletteOpen(false);
    setNodePaletteSearch('');
    window.requestAnimationFrame(() => {
      document
        .querySelector(`[data-workflow-node-id="${nextNode.id}"]`)
        ?.scrollIntoView({
          block: 'center',
          inline: 'center',
          behavior: 'smooth',
        });
    });
  }

  function addNode(type: WorkflowNodeType, sourceId?: string) {
    const canvas = canvasScrollRef.current;
    const visibleX = canvas ? canvas.scrollLeft + 96 : 120;
    const visibleY = canvas ? canvas.scrollTop + 96 : 120;
    addNodeAt(type, { x: visibleX, y: visibleY }, sourceId);
  }

  function openAddNodeMenu(sourceId: string) {
    setSelectedNodeId(sourceId);
    setAddNodeMenuSourceId(sourceId);
    setNodePaletteOpen(false);
    setNodePaletteSearch('');
    setHoveredOutputNodeId(sourceId);
  }

  function openNodePalette() {
    setAddNodeMenuSourceId('');
    setNodePaletteOpen(true);
    setNodePaletteSearch('');
  }

  function deleteNode(nodeId: string) {
    commit({
      ...workflow,
      nodes: workflow.nodes.filter((node) => node.id !== nodeId),
      edges: workflow.edges.filter(
        (edge) => edge.source !== nodeId && edge.target !== nodeId,
      ),
    });
    setSelectedNodeId(
      workflow.nodes.find((node) => node.id !== nodeId)?.id ?? '',
    );
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

  function updateEdge(edgeId: string, patch: Partial<PipelineWorkflowEdge>) {
    commit({
      ...workflow,
      edges: workflow.edges.map((edge) =>
        edge.id === edgeId ? { ...edge, ...patch } : edge,
      ),
    });
  }

  function handleNodePointerDown(
    event: ReactPointerEvent<HTMLDivElement>,
    node: PipelineWorkflowNode,
  ) {
    if ((event.target as HTMLElement).closest('[data-node-action]')) return;
    event.stopPropagation();
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

  function handleCanvasPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (
      target.closest('[data-workflow-node-id]') ||
      target.closest('[data-node-action]') ||
      target.closest('[data-node-add-menu]')
    ) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    canvasPanRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      scrollLeft: event.currentTarget.scrollLeft,
      scrollTop: event.currentTarget.scrollTop,
    };
  }

  function handleCanvasPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const pan = canvasPanRef.current;
    if (!pan || pan.pointerId !== event.pointerId) return;
    event.currentTarget.scrollLeft =
      pan.scrollLeft - (event.clientX - pan.startX);
    event.currentTarget.scrollTop =
      pan.scrollTop - (event.clientY - pan.startY);
  }

  function handleCanvasPointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    const pan = canvasPanRef.current;
    if (!pan || pan.pointerId !== event.pointerId) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    canvasPanRef.current = null;
  }

  function handleCanvasDrop(event: ReactDragEvent<HTMLDivElement>) {
    const type = event.dataTransfer.getData(
      'application/x-yunti-workflow-node',
    ) as WorkflowNodeType;
    if (!type || !paletteOrder.includes(type)) return;
    event.preventDefault();
    addNodeAt(type, clientPointToCanvasPoint(event.clientX, event.clientY));
  }

  function clientPointToCanvasPoint(
    clientX: number,
    clientY: number,
  ): CanvasPoint {
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
    const encodedKey = fileKey.split('/').map(encodeURIComponent).join('/');
    return `${prefix}/api/v1/files/image/${encodedKey}`;
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

  const addMenuSourceNode = workflow.nodes.find(
    (node) => node.id === addNodeMenuSourceId,
  );

  const filteredAddMenuPalette = useMemo(() => {
    return groupPaletteTypes(filterPaletteTypes(nodePaletteSearch));
  }, [nodePaletteSearch]);

  const libraryFamilies = useMemo(() => {
    const query = librarySearch.trim().toLowerCase();
    if (!componentFamilies.length) {
      return Object.entries(
        groupPaletteTypes(filterPaletteTypes(librarySearch)),
      ).map(([label, types]) => ({
        id: label,
        label,
        components: types.map((type) => ({
          type,
          display_name: nodeMeta[type].label,
          description: nodeMeta[type].group,
          icon: '',
          inputs: [],
          outputs: [],
          fields: [],
        })),
      })) as WorkflowComponentFamily[];
    }
    if (!query) return componentFamilies;
    return componentFamilies
      .map((family) => ({
        ...family,
        components: family.components.filter((component) => {
          return (
            family.label.toLowerCase().includes(query) ||
            component.type.toLowerCase().includes(query) ||
            component.display_name.toLowerCase().includes(query) ||
            component.description.toLowerCase().includes(query)
          );
        }),
      }))
      .filter((family) => family.components.length > 0);
  }, [componentFamilies, librarySearch]);

  const editor = (
    <div
      className={cn(
        'relative flex overflow-hidden border-slate-200 bg-[#f6f7fb] text-slate-950 shadow-sm',
        isFullscreen
          ? 'h-full w-full'
          : 'h-[calc(100vh-218px)] min-h-[620px] rounded-xl border',
      )}
      data-langflow-editor
    >
      <WorkflowLibraryPanel
        families={libraryFamilies}
        search={librarySearch}
        nodesCount={workflow.nodes.length}
        edgesCount={workflow.edges.length}
        onSearchChange={setLibrarySearch}
        onAddNode={(type) => addNode(type)}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-slate-200 bg-white/95 px-3 py-2.5">
          <Input
            value={workflow.name}
            onChange={(event) => updateWorkflow({ name: event.target.value })}
            className="h-9 max-w-[280px] rounded-md border-slate-200 bg-slate-50/70 font-medium shadow-none focus-visible:bg-white"
          />
          <Button
            type="button"
            size="sm"
            data-node-palette-trigger
            className="h-9 gap-1.5 rounded-md bg-slate-950 px-3 text-white hover:bg-slate-800"
            onClick={openNodePalette}
          >
            <Plus className="size-4" />
            Component
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="hidden h-9 rounded-md border-slate-200 bg-white px-3 lg:inline-flex"
            title="导入销售模板，会替换当前画布"
            onClick={() => {
              const next = createSalesWorkflowTemplate();
              commit(next);
              setSelectedNodeId(next.nodes[0]?.id ?? '');
            }}
          >
            销售模板
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="hidden h-9 rounded-md border-slate-200 bg-white px-3 lg:inline-flex"
            title="导入客服模板，会替换当前画布"
            onClick={() => {
              const next = createSupportWorkflowTemplate();
              commit(next);
              setSelectedNodeId(next.nodes[0]?.id ?? '');
            }}
          >
            客服模板
          </Button>
          <Badge
            variant="secondary"
            className="rounded-md bg-slate-100 px-2.5 py-1 text-slate-700"
          >
            {workflow.nodes.length} 个节点
          </Badge>
          <Badge
            variant="secondary"
            className="rounded-md bg-teal-50 px-2.5 py-1 text-teal-700"
          >
            {workflow.edges.length} 条连线
          </Badge>
          {draftConnection && (
            <Badge className="gap-1 bg-amber-100 text-amber-800 hover:bg-amber-100">
              <Link2 className="size-3" />
              拖到目标输入点
            </Badge>
          )}
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden max-w-[210px] text-xs leading-tight text-muted-foreground 2xl:inline-flex 2xl:items-center 2xl:gap-1.5">
              <MousePointer2 className="size-3.5" />
              从左侧拖入组件，或拖拽端口连接 Flow
            </span>
            {rightPanelCollapsed && (
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="size-8 rounded-lg border-slate-200 bg-white"
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
              className="size-8 rounded-lg border-slate-200 bg-white"
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

        <div
          ref={canvasScrollRef}
          data-workflow-canvas
          onPointerDown={handleCanvasPointerDown}
          onPointerMove={handleCanvasPointerMove}
          onPointerUp={handleCanvasPointerUp}
          onPointerCancel={handleCanvasPointerUp}
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleCanvasDrop}
          className="relative min-h-0 flex-1 cursor-grab overflow-auto bg-[#f8fafc] active:cursor-grabbing"
        >
          <div
            className="relative min-h-[760px] min-w-[2360px]"
            style={{
              backgroundImage:
                'radial-gradient(circle at 1px 1px, rgba(15,23,42,0.13) 1px, transparent 0)',
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
                  <path d="M0,0 L8,4 L0,8 Z" fill="#52627a" />
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
                      stroke="#52627a"
                      strokeLinecap="round"
                      strokeWidth="2.25"
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
                  d={edgePath(
                    nodeOutputPoint(draftConnection.sourceId),
                    draftConnection.pointer,
                  )}
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
              const schema = componentSchemaByType[node.type];
              const Icon = schema?.icon
                ? iconByName[schema.icon] || meta.icon
                : meta.icon;
              const selected = selectedNodeId === node.id;
              const connecting = draftConnection?.sourceId === node.id;
              const receiving = connectionTargetId === node.id;
              const canReceive = node.type !== 'start';
              const canSend = node.type !== 'end';
              const configCount = Object.keys(node.config || {}).length;
              const showOutputActions =
                canSend &&
                (hoveredOutputNodeId === node.id ||
                  addNodeMenuSourceId === node.id);
              return (
                <div
                  key={node.id}
                  data-workflow-node-id={node.id}
                  onPointerDown={(event) => handleNodePointerDown(event, node)}
                  onPointerMove={handleNodePointerMove}
                  onPointerUp={handleNodePointerUp}
                  className={cn(
                    'absolute cursor-grab select-none rounded-lg border border-slate-200 bg-white shadow-[0_8px_22px_rgba(15,23,42,0.08)] transition-[box-shadow,border-color,transform] active:cursor-grabbing',
                    'hover:border-slate-300 hover:shadow-[0_14px_30px_rgba(15,23,42,0.12)]',
                    selected && 'border-slate-950 ring-4 ring-slate-200/80',
                    connecting && 'ring-2 ring-amber-500',
                    receiving && 'ring-2 ring-teal-500',
                  )}
                  style={{
                    left: node.position.x,
                    top: node.position.y,
                    width: NODE_WIDTH,
                    minHeight: NODE_HEIGHT,
                  }}
                >
                  {canSend && (
                    <div
                      className="absolute -right-14 top-0 z-20 flex h-full w-14 items-center justify-center"
                      onMouseEnter={() => setHoveredOutputNodeId(node.id)}
                      onMouseLeave={() => {
                        if (addNodeMenuSourceId !== node.id) {
                          setHoveredOutputNodeId('');
                        }
                      }}
                    >
                      <div
                        className={cn(
                          'flex flex-col items-center gap-1 transition-all duration-150',
                          showOutputActions
                            ? 'translate-x-0 opacity-100'
                            : 'pointer-events-none translate-x-1 opacity-0',
                        )}
                      >
                        <button
                          type="button"
                          data-node-action
                          data-node-add-trigger
                          aria-label={`从 ${node.title} 添加节点`}
                          title="添加节点"
                          onPointerDown={(event) => event.stopPropagation()}
                          onClick={(event) => {
                            event.stopPropagation();
                            openAddNodeMenu(node.id);
                          }}
                          className={cn(
                            'flex size-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-700 shadow-lg shadow-slate-950/10 transition-colors hover:border-slate-400 hover:bg-slate-50',
                            addNodeMenuSourceId === node.id &&
                              'border-slate-400 bg-slate-50 text-slate-950 ring-2 ring-slate-200',
                          )}
                        >
                          <Plus className="size-4" />
                        </button>
                        <span className="pointer-events-none w-[88px] text-center text-[10px] leading-tight text-slate-500">
                          点击添加节点，或拖拽圆点连线
                        </span>
                      </div>
                    </div>
                  )}
                  {canReceive && (
                    <button
                      type="button"
                      aria-label={`连接到 ${node.title}`}
                      data-node-action
                      data-workflow-port="input"
                      onPointerEnter={() => {
                        if (
                          draftConnection &&
                          draftConnection.sourceId !== node.id
                        ) {
                          setConnectionTargetId(node.id);
                        }
                      }}
                      onPointerLeave={() => {
                        if (connectionTargetId === node.id) {
                          setConnectionTargetId('');
                        }
                      }}
                      onPointerUp={(event) =>
                        handleConnectionEnd(event, node.id)
                      }
                      className={cn(
                        'absolute -left-2 top-1/2 z-10 size-4 -translate-y-1/2 rounded-full border-2 border-white bg-slate-300 shadow-sm transition-colors',
                        draftConnection &&
                          draftConnection.sourceId !== node.id &&
                          'bg-teal-500 ring-4 ring-teal-100',
                      )}
                    />
                  )}
                  {canSend && (
                    <button
                      type="button"
                      aria-label={`从 ${node.title} 连线`}
                      data-node-action
                      data-workflow-port="output"
                      onPointerDown={(event) =>
                        handleConnectionStart(event, node)
                      }
                      className={cn(
                        'absolute -right-2 top-1/2 z-10 size-4 -translate-y-1/2 cursor-crosshair rounded-full border-2 border-white bg-slate-800 shadow-sm transition-colors hover:bg-teal-600',
                        connecting && 'bg-teal-600 ring-4 ring-teal-100',
                      )}
                    />
                  )}
                  <div className="rounded-t-lg border-b border-slate-100 px-3 py-2">
                    <div className="flex items-start gap-2.5">
                      <div
                        className={cn(
                          'mt-0.5 rounded-md border p-1.5',
                          meta.accent,
                        )}
                      >
                        <Icon className="size-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold">
                          {node.title}
                        </div>
                        <div className="truncate text-[11px] text-muted-foreground">
                          {node.description ||
                            schema?.description ||
                            meta.label}
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
                  <div className="flex items-center justify-between gap-2 px-3 py-2 text-[11px] text-slate-500">
                    <div className="flex min-w-0 items-center gap-1.5">
                      {canReceive && (
                        <span className="rounded bg-slate-100 px-1.5 py-0.5">
                          Input
                        </span>
                      )}
                      {canSend && (
                        <span className="rounded bg-slate-100 px-1.5 py-0.5">
                          Output
                        </span>
                      )}
                    </div>
                    <div className="truncate">
                      {configCount ? `${configCount} 参数` : 'No params'}
                    </div>
                  </div>
                </div>
              );
            })}

            {addMenuSourceNode && (
              <div
                ref={addNodeMenuRef}
                data-node-add-menu
                className="absolute z-30 w-[min(400px,calc(100%-48px))] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl shadow-slate-950/10"
                style={{
                  left: addMenuSourceNode.position.x + NODE_WIDTH + 56,
                  top: Math.max(24, addMenuSourceNode.position.y - 12),
                }}
              >
                <div className="border-b border-slate-200 bg-slate-50/80 p-3">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      value={nodePaletteSearch}
                      onChange={(event) =>
                        setNodePaletteSearch(event.target.value)
                      }
                      placeholder="搜索节点或工具"
                      className="h-9 rounded-lg border-slate-200 bg-white pl-8 shadow-none"
                      autoFocus
                    />
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    从「{addMenuSourceNode.title}」后添加节点，将自动连线
                  </p>
                </div>
                <div className="max-h-[min(420px,50vh)] overflow-y-auto p-3">
                  {Object.keys(filteredAddMenuPalette).length ? (
                    <div className="space-y-4">
                      {Object.entries(filteredAddMenuPalette).map(
                        ([group, types]) => (
                          <div key={group}>
                            <div className="mb-2 text-xs font-semibold text-muted-foreground">
                              {group}
                            </div>
                            <div className="grid gap-1">
                              {types.map((type) => {
                                const meta = nodeMeta[type];
                                const Icon = meta.icon;
                                return (
                                  <button
                                    key={type}
                                    type="button"
                                    data-node-action
                                    onClick={() =>
                                      addNode(type, addMenuSourceNode.id)
                                    }
                                    className="flex items-center gap-2.5 rounded-lg border border-transparent px-2.5 py-2 text-left text-sm transition-colors hover:border-slate-200 hover:bg-slate-50"
                                  >
                                    <span
                                      className={cn(
                                        'flex size-8 shrink-0 items-center justify-center rounded-lg border',
                                        meta.accent,
                                      )}
                                    >
                                      <Icon className="size-4" />
                                    </span>
                                    <span className="min-w-0 flex-1 truncate font-medium">
                                      {meta.label}
                                    </span>
                                    <Plus className="size-3.5 shrink-0 text-muted-foreground" />
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        ),
                      )}
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed px-3 py-8 text-center text-sm text-muted-foreground">
                      未找到匹配的节点
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {nodePaletteOpen && (
        <div
          data-node-add-menu
          className="absolute left-3 top-14 z-40 w-[min(420px,calc(100%-32px))] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl shadow-slate-950/10"
        >
          <div className="border-b border-slate-200 bg-slate-50/80 p-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={nodePaletteSearch}
                onChange={(event) => setNodePaletteSearch(event.target.value)}
                placeholder="搜索节点或工具"
                className="h-9 rounded-lg border-slate-200 bg-white pl-8 shadow-none"
                autoFocus
              />
            </div>
            <div className="mt-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
              <span>添加到当前画布视野内，不自动连线</span>
              <span>{paletteOrder.length - 1} 个节点</span>
            </div>
          </div>
          <div className="max-h-[min(520px,65vh)] overflow-y-auto p-3">
            {Object.keys(filteredAddMenuPalette).length ? (
              <div className="space-y-4">
                {Object.entries(filteredAddMenuPalette).map(
                  ([group, types]) => (
                    <div key={group}>
                      <div className="mb-2 text-xs font-semibold text-muted-foreground">
                        {group}
                      </div>
                      <div className="grid gap-1">
                        {types.map((type) => {
                          const meta = nodeMeta[type];
                          const Icon = meta.icon;
                          return (
                            <button
                              key={type}
                              type="button"
                              data-node-action
                              onClick={() => addNode(type)}
                              className="flex items-center gap-2.5 rounded-lg border border-transparent px-2.5 py-2 text-left text-sm transition-colors hover:border-slate-200 hover:bg-slate-50"
                            >
                              <span
                                className={cn(
                                  'flex size-8 shrink-0 items-center justify-center rounded-lg border',
                                  meta.accent,
                                )}
                              >
                                <Icon className="size-4" />
                              </span>
                              <span className="min-w-0 flex-1 truncate font-medium">
                                {meta.label}
                              </span>
                              <Plus className="size-3.5 shrink-0 text-muted-foreground" />
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ),
                )}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed px-3 py-8 text-center text-sm text-muted-foreground">
                未找到匹配的节点
              </div>
            )}
          </div>
        </div>
      )}

      {!rightPanelCollapsed ? (
        <aside className="flex w-[360px] shrink-0 flex-col border-l border-slate-200 bg-white">
          <div className="border-b border-slate-200 p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="text-xs font-semibold text-slate-500">
                  Inspector
                </div>
                <div className="mt-0.5 truncate text-sm font-semibold">
                  {selectedNode?.title ?? '未选择节点'}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Save className="size-4 text-muted-foreground" />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-8 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                  title="收起节点配置"
                  onClick={() => setRightPanelCollapsed(true)}
                >
                  <PanelRightClose className="size-4" />
                </Button>
              </div>
            </div>
          </div>
          <Tabs defaultValue="params" className="min-h-0 flex-1 gap-0">
            <div className="border-b border-slate-200 px-3 py-2">
              <TabsList className="grid h-9 w-full grid-cols-3 rounded-md bg-slate-100 p-1">
                <TabsTrigger value="params" className="gap-1 text-xs">
                  <Settings2 className="size-3.5" />
                  配置
                </TabsTrigger>
                <TabsTrigger value="io" className="gap-1 text-xs">
                  <Code2 className="size-3.5" />
                  流数据
                </TabsTrigger>
                <TabsTrigger value="run" className="gap-1 text-xs">
                  <PlayCircle className="size-3.5" />
                  Playground
                </TabsTrigger>
              </TabsList>
            </div>
            <TabsContent value="params" className="min-h-0 overflow-y-auto p-3">
              {selectedNode ? (
                <NodeConfigPanel
                  imageNodes={imageNodes}
                  knowledgeBases={knowledgeBases}
                  llmModels={llmModels}
                  node={selectedNode}
                  componentSchema={componentSchemaByType[selectedNode.type]}
                  products={salesProducts}
                  uploading={uploadingNodeId === selectedNode.id}
                  imageAssetUrl={imageAssetUrl}
                  onNodeChange={(patch) => updateNode(selectedNode.id, patch)}
                  onConfigChange={(patch) =>
                    updateNodeConfig(selectedNode.id, patch)
                  }
                  onUploadImage={(event) =>
                    uploadImageForNode(selectedNode, event)
                  }
                />
              ) : (
                <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                  请选择一个节点
                </div>
              )}
            </TabsContent>
            <TabsContent value="io" className="min-h-0 overflow-y-auto p-3">
              <WorkflowIoPanel
                workflow={workflow}
                selectedNode={selectedNode}
                componentSchema={
                  selectedNode
                    ? componentSchemaByType[selectedNode.type]
                    : undefined
                }
                onDeleteEdge={deleteEdge}
                onEdgeChange={updateEdge}
                onSelectNode={setSelectedNodeId}
              />
            </TabsContent>
            <TabsContent value="run" className="min-h-0 overflow-y-auto p-3">
              <WorkflowExecutionPanel
                workflow={workflow}
                onWorkflowChange={updateWorkflow}
                onLoadSalesTemplate={() => {
                  const next = createSalesWorkflowTemplate();
                  commit(next);
                  setSelectedNodeId(next.nodes[0]?.id ?? '');
                }}
                onLoadSupportTemplate={() => {
                  const next = createSupportWorkflowTemplate();
                  commit(next);
                  setSelectedNodeId(next.nodes[0]?.id ?? '');
                }}
              />
            </TabsContent>
          </Tabs>
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

function WorkflowLibraryPanel({
  edgesCount,
  families,
  nodesCount,
  search,
  onAddNode,
  onSearchChange,
}: {
  edgesCount: number;
  families: WorkflowComponentFamily[];
  nodesCount: number;
  search: string;
  onAddNode: (type: WorkflowNodeType) => void;
  onSearchChange: (value: string) => void;
}) {
  return (
    <aside className="hidden w-[286px] shrink-0 flex-col border-r border-slate-200 bg-white xl:flex">
      <div className="border-b border-slate-200 p-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-sm font-semibold text-slate-950">
              Components
            </div>
            <div className="mt-0.5 text-xs text-slate-500">
              拖到画布，或点击快速添加
            </div>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-500">
            {nodesCount}/{edgesCount}
          </div>
        </div>
        <div className="relative mt-3">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search components"
            className="h-9 rounded-md border-slate-200 bg-slate-50/80 pl-8 shadow-none focus-visible:bg-white"
          />
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {families.length ? (
          <div className="space-y-4">
            {families.map((family) => (
              <div key={family.id}>
                <div className="mb-2 flex items-center justify-between text-xs font-semibold text-slate-500">
                  <span>{family.label}</span>
                  <span>{family.components.length}</span>
                </div>
                <div className="grid gap-1.5">
                  {family.components.map((component) => {
                    const type = component.type as WorkflowNodeType;
                    const meta = nodeMeta[type] || nodeMeta.custom;
                    const Icon = component.icon
                      ? iconByName[component.icon] || meta.icon
                      : meta.icon;
                    return (
                      <button
                        key={`${family.id}-${component.type}`}
                        type="button"
                        draggable
                        onDragStart={(event) => {
                          event.dataTransfer.setData(
                            'application/x-yunti-workflow-node',
                            component.type,
                          );
                          event.dataTransfer.effectAllowed = 'copy';
                        }}
                        onClick={() => {
                          if (paletteOrder.includes(type)) onAddNode(type);
                        }}
                        className="group flex min-h-12 items-center gap-2.5 rounded-md border border-slate-200 bg-white px-2.5 py-2 text-left transition-colors hover:border-slate-300 hover:bg-slate-50"
                      >
                        <span
                          className={cn(
                            'flex size-8 shrink-0 items-center justify-center rounded-md border',
                            meta.accent,
                          )}
                        >
                          <Icon className="size-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-slate-900">
                            {component.display_name || meta.label}
                          </span>
                          <span className="block truncate text-[11px] text-slate-500">
                            {component.description || component.type}
                          </span>
                        </span>
                        <Plus className="size-3.5 text-slate-400 group-hover:text-slate-900" />
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-slate-200 p-6 text-center text-sm text-muted-foreground">
            没有匹配的节点
          </div>
        )}
      </div>
    </aside>
  );
}

function WorkflowIoPanel({
  workflow,
  selectedNode,
  componentSchema,
  onDeleteEdge,
  onEdgeChange,
  onSelectNode,
}: {
  workflow: PipelineWorkflow;
  selectedNode?: PipelineWorkflowNode;
  componentSchema?: WorkflowComponentSchema;
  onDeleteEdge: (edgeId: string) => void;
  onEdgeChange: (edgeId: string, patch: Partial<PipelineWorkflowEdge>) => void;
  onSelectNode: (nodeId: string) => void;
}) {
  if (!selectedNode) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        请选择一个节点查看输入输出
      </div>
    );
  }

  const incoming = workflow.edges.filter(
    (edge) => edge.target === selectedNode.id,
  );
  const outgoing = workflow.edges.filter(
    (edge) => edge.source === selectedNode.id,
  );

  function nodeTitle(nodeId: string) {
    return workflow.nodes.find((node) => node.id === nodeId)?.title ?? nodeId;
  }

  return (
    <div className="space-y-4">
      {componentSchema && (
        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="mb-2 text-xs font-semibold text-slate-500">
            Component ports
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <PortList title="Inputs" ports={componentSchema.inputs} />
            <PortList title="Outputs" ports={componentSchema.outputs} />
          </div>
        </div>
      )}
      <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
        <div className="mb-2 text-xs font-semibold text-slate-500">Inputs</div>
        <EdgeList
          edges={incoming}
          emptyText="暂无上游输入"
          labelFor={(edge) => nodeTitle(edge.source)}
          onDeleteEdge={onDeleteEdge}
          onEdgeChange={onEdgeChange}
          onSelect={(edge) => onSelectNode(edge.source)}
        />
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
        <div className="mb-2 text-xs font-semibold text-slate-500">Outputs</div>
        <EdgeList
          edges={outgoing}
          emptyText="暂无下游输出"
          labelFor={(edge) => nodeTitle(edge.target)}
          onDeleteEdge={onDeleteEdge}
          onEdgeChange={onEdgeChange}
          onSelect={(edge) => onSelectNode(edge.target)}
        />
      </div>
      <JsonLikeTextarea
        label="Component data"
        value={JSON.stringify(selectedNode.config, null, 2)}
        onChange={() => {}}
        readOnly
      />
    </div>
  );
}

function PortList({
  ports,
  title,
}: {
  ports: WorkflowComponentSchema['inputs'];
  title: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
      <div className="mb-1 font-semibold text-slate-600">{title}</div>
      <div className="space-y-1">
        {ports.map((port) => (
          <div
            key={`${title}-${port.name}`}
            className="rounded border border-slate-200 bg-white px-2 py-1"
          >
            <span className="font-medium">{port.name}</span>
            <span className="ml-1 text-slate-400">
              {port.types?.join(' | ')}
            </span>
          </div>
        ))}
        {!ports.length && <div className="text-slate-400">None</div>}
      </div>
    </div>
  );
}

function EdgeList({
  edges,
  emptyText,
  labelFor,
  onDeleteEdge,
  onEdgeChange,
  onSelect,
}: {
  edges: PipelineWorkflowEdge[];
  emptyText: string;
  labelFor: (edge: PipelineWorkflowEdge) => string;
  onDeleteEdge: (edgeId: string) => void;
  onEdgeChange: (edgeId: string, patch: Partial<PipelineWorkflowEdge>) => void;
  onSelect: (edge: PipelineWorkflowEdge) => void;
}) {
  if (!edges.length) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-white p-3 text-xs text-muted-foreground">
        {emptyText}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {edges.map((edge) => (
        <div
          key={edge.id}
          className="rounded-lg border border-slate-200 bg-white p-2"
        >
          <div className="mb-2 flex items-center gap-2">
            <button
              type="button"
              onClick={() => onSelect(edge)}
              className="min-w-0 flex-1 truncate text-left text-xs font-medium text-slate-700 hover:text-blue-700"
            >
              {labelFor(edge)}
            </button>
            <button
              type="button"
              onClick={() => onDeleteEdge(edge.id)}
              className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              title="删除连线"
            >
              <Trash2 className="size-3" />
            </button>
          </div>
          <Input
            value={edge.label ?? ''}
            placeholder="连线标签，例如：已报名 / 未报名"
            onChange={(event) =>
              onEdgeChange(edge.id, { label: event.target.value })
            }
            className="h-8 rounded-md border-slate-200 bg-slate-50 text-xs shadow-none"
          />
        </div>
      ))}
    </div>
  );
}

function WorkflowExecutionPanel({
  workflow,
  onLoadSalesTemplate,
  onLoadSupportTemplate,
  onWorkflowChange,
}: {
  workflow: PipelineWorkflow;
  onLoadSalesTemplate: () => void;
  onLoadSupportTemplate: () => void;
  onWorkflowChange: (patch: Partial<PipelineWorkflow>) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
        <div className="mb-3 text-xs font-semibold text-slate-500">
          Flow settings
        </div>
        <div className="space-y-3">
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              场景
            </label>
            <Select
              value={workflow.scenario}
              onValueChange={(value) =>
                onWorkflowChange({
                  scenario: value as PipelineWorkflow['scenario'],
                })
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sales">销售</SelectItem>
                <SelectItem value="support">客服</SelectItem>
                <SelectItem value="task">任务助手</SelectItem>
                <SelectItem value="custom">自定义</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <JsonLikeTextarea
            label="Flow variables"
            value={JSON.stringify(workflow.variables || {}, null, 2)}
            onChange={(value) => {
              try {
                onWorkflowChange({ variables: JSON.parse(value) });
              } catch {
                onWorkflowChange({
                  variables: { raw_variables: value },
                });
              }
            }}
          />
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="mb-3 text-xs font-semibold text-slate-500">
          Starter flows
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button
            type="button"
            variant="outline"
            className="rounded-lg border-slate-200"
            onClick={onLoadSalesTemplate}
          >
            销售模板
          </Button>
          <Button
            type="button"
            variant="outline"
            className="rounded-lg border-slate-200"
            onClick={onLoadSupportTemplate}
          >
            客服模板
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-xl border border-blue-100 bg-blue-50 p-3">
          <div className="text-2xl font-semibold text-blue-700">
            {workflow.nodes.length}
          </div>
          <div className="mt-1 text-xs text-blue-700/80">节点</div>
        </div>
        <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-3">
          <div className="text-2xl font-semibold text-emerald-700">
            {workflow.edges.length}
          </div>
          <div className="mt-1 text-xs text-emerald-700/80">连线</div>
        </div>
      </div>
    </div>
  );
}

function NodeConfigPanel({
  componentSchema,
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
  componentSchema?: WorkflowComponentSchema;
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
    <div className="space-y-5 [&_input]:h-10 [&_input]:rounded-lg [&_input]:border-slate-200 [&_input]:bg-slate-50/70 [&_input]:shadow-none [&_input]:focus-visible:bg-white [&_label]:text-[11px] [&_label]:font-semibold [&_label]:text-slate-500 [&_textarea]:rounded-lg [&_textarea]:border-slate-200 [&_textarea]:bg-slate-50/70 [&_textarea]:shadow-none [&_textarea]:focus-visible:bg-white">
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground">
          名称
        </label>
        <Input
          value={node.title}
          onChange={(event) => onNodeChange({ title: event.target.value })}
        />
      </div>
      <div className="space-y-2">
        <label className="text-xs font-medium text-muted-foreground">
          说明
        </label>
        <Input
          value={node.description ?? ''}
          placeholder={defaults.description}
          onChange={(event) =>
            onNodeChange({ description: event.target.value })
          }
        />
      </div>

      {componentSchema && (
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs font-semibold text-slate-500">
                Langflow component
              </div>
              <div className="mt-0.5 text-sm font-semibold text-slate-900">
                {componentSchema.display_name}
              </div>
              <div className="mt-1 text-xs leading-relaxed text-slate-500">
                {componentSchema.description}
              </div>
            </div>
            <Badge variant="secondary" className="rounded-md">
              {node.type}
            </Badge>
          </div>
          <div className="space-y-3">
            {componentSchema.fields.map((field) => (
              <WorkflowFieldEditor
                key={field.name}
                field={field}
                value={
                  node.config[field.name] === undefined
                    ? field.default
                    : node.config[field.name]
                }
                onChange={(value) => onConfigChange({ [field.name]: value })}
              />
            ))}
            {!componentSchema.fields.length && (
              <div className="rounded-lg border border-dashed border-slate-200 p-3 text-xs text-slate-500">
                这个组件没有可配置字段
              </div>
            )}
          </div>
        </div>
      )}

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
              <SelectItem value="__none__">跟随数字员工默认模型</SelectItem>
              {llmModels
                .filter(
                  (model) =>
                    model.provider?.requester !== 'space-chat-completions',
                )
                .map((model) => (
                  <SelectItem key={model.uuid} value={model.uuid}>
                    {model.name}
                    {model.provider?.name ? ` · ${model.provider.name}` : ''}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            保存后会同步为这个数字员工实际调用的主模型。
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
                onConfigChange({
                  image_intents: asStringList(event.target.value),
                })
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
                onConfigChange({
                  confidence_threshold: Number(event.target.value),
                })
              }
            />
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
            <div className="mb-2 text-xs font-semibold text-slate-500">
              可用图片节点
            </div>
            <div className="space-y-1 text-xs">
              {imageNodes.map((imageNode) => (
                <div
                  key={imageNode.id}
                  className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5"
                >
                  {imageNode.title}：
                  {listToText(imageNode.config.trigger_intents) || '未绑定意图'}
                </div>
              ))}
              {!imageNodes.length && (
                <div className="text-muted-foreground">暂无图片节点</div>
              )}
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
                onClick={() =>
                  toggleListValue('knowledge_base_uuids', kb.uuid || '')
                }
                className={cn(
                  'flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm',
                  selectedKbIds.includes(kb.uuid || '')
                    ? 'border-blue-300 bg-blue-50 text-blue-950'
                    : 'border-slate-200 bg-white hover:bg-slate-50',
                )}
              >
                <span className="truncate">{kb.name}</span>
                {selectedKbIds.includes(kb.uuid || '') && <Badge>已选</Badge>}
              </button>
            ))}
            {!knowledgeBases.length && (
              <div className="rounded-lg border border-dashed border-slate-200 p-3 text-sm text-muted-foreground">
                暂无知识库
              </div>
            )}
          </div>
          <Input
            type="number"
            min={1}
            value={asNumber(node.config.top_k, 5)}
            onChange={(event) =>
              onConfigChange({ top_k: Number(event.target.value) })
            }
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
                onClick={() =>
                  toggleListValue('product_uuids', product.uuid || '')
                }
                className={cn(
                  'flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm',
                  selectedProductIds.includes(product.uuid || '')
                    ? 'border-blue-300 bg-blue-50 text-blue-950'
                    : 'border-slate-200 bg-white hover:bg-slate-50',
                )}
              >
                <span className="min-w-0">
                  <span className="block truncate">{product.name}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {product.price || product.category}
                  </span>
                </span>
                {selectedProductIds.includes(product.uuid || '') && (
                  <Badge>已选</Badge>
                )}
              </button>
            ))}
            {!products.length && (
              <div className="rounded-lg border border-dashed border-slate-200 p-3 text-sm text-muted-foreground">
                暂无产品
              </div>
            )}
          </div>
        </div>
      )}

      {node.type === 'llm' && (
        <>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              语气
            </label>
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
              onChange={(event) =>
                onConfigChange({ prompt: event.target.value })
              }
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
                onConfigChange({
                  trigger_intents: asStringList(event.target.value),
                })
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
                  onConfigChange({
                    image_url: event.target.value,
                    file_key: '',
                  })
                }
              />
            </div>
            {previewUrl && (
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
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
              onChange={(event) =>
                onConfigChange({ caption: event.target.value })
              }
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
            onChange={(event) =>
              onConfigChange({ rules: asStringList(event.target.value) })
            }
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
              onChange={(event) =>
                onConfigChange({ fields: asStringList(event.target.value) })
              }
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
                onConfigChange({
                  required_fields: asStringList(event.target.value),
                })
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
              onChange={(event) =>
                onConfigChange({ reason: event.target.value })
              }
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              指派给
            </label>
            <Input
              value={asString(node.config.assigned_to)}
              onChange={(event) =>
                onConfigChange({ assigned_to: event.target.value })
              }
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

      {node.type === 'radar' && (
        <>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              雷达链接
            </label>
            <Input
              value={asString(node.config.link_url)}
              onChange={(event) =>
                onConfigChange({ link_url: event.target.value })
              }
              placeholder="https://m.yuanfudao.com/primary/templates/package"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">
              链接标题
            </label>
            <Input
              value={asString(node.config.link_title)}
              onChange={(event) =>
                onConfigChange({ link_title: event.target.value })
              }
            />
          </div>
          <JsonLikeTextarea
            label="雷达规则 JSON"
            value={JSON.stringify(node.config.rules || [], null, 2)}
            onChange={(value) => {
              try {
                onConfigChange({ rules: JSON.parse(value) });
              } catch {
                onConfigChange({ rules_text: value });
              }
            }}
          />
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
      ].includes(node.type) && (
        <GenericConfig node={node} onConfigChange={onConfigChange} />
      )}
    </div>
  );
}

function WorkflowFieldEditor({
  field,
  value,
  onChange,
}: {
  field: WorkflowComponentField;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const label = (
    <label className="text-xs font-medium text-muted-foreground">
      {field.label}
    </label>
  );

  if (field.type === 'boolean') {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2">
        {label}
        <button
          type="button"
          onClick={() => onChange(!(value === true))}
          className={cn(
            'relative h-6 w-11 rounded-full transition-colors',
            value === true ? 'bg-slate-950' : 'bg-slate-300',
          )}
        >
          <span
            className={cn(
              'absolute top-1 size-4 rounded-full bg-white transition-transform',
              value === true ? 'translate-x-5' : 'translate-x-1',
            )}
          />
        </button>
      </div>
    );
  }

  if (field.type === 'select') {
    return (
      <div className="space-y-2">
        {label}
        <Select
          value={String(value ?? field.default ?? '')}
          onValueChange={(next) => onChange(next)}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(field.options || []).map((option) => (
              <SelectItem key={String(option)} value={String(option)}>
                {String(option)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    );
  }

  if (field.type === 'number') {
    return (
      <div className="space-y-2">
        {label}
        <Input
          type="number"
          value={asNumber(value, asNumber(field.default, 0))}
          onChange={(event) => onChange(Number(event.target.value))}
        />
      </div>
    );
  }

  if (field.type === 'tags') {
    return (
      <div className="space-y-2">
        {label}
        <Textarea
          value={listToText(value)}
          onChange={(event) => onChange(asStringList(event.target.value))}
          className="min-h-20"
          placeholder="每行一个，或用逗号分隔"
        />
      </div>
    );
  }

  if (field.type === 'json') {
    return (
      <JsonLikeTextarea
        label={field.label}
        value={JSON.stringify(value ?? field.default ?? {}, null, 2)}
        onChange={(next) => {
          try {
            onChange(JSON.parse(next));
          } catch {
            onChange(next);
          }
        }}
      />
    );
  }

  if (field.type === 'textarea') {
    return (
      <div className="space-y-2">
        {label}
        <Textarea
          value={asString(value, asString(field.default))}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-24"
        />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {label}
      <Input
        value={asString(value, asString(field.default))}
        onChange={(event) => onChange(event.target.value)}
      />
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
          <label className="text-xs font-medium text-muted-foreground">
            方法
          </label>
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
          <label className="text-xs font-medium text-muted-foreground">
            URL
          </label>
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
            onChange={(event) =>
              onConfigChange({ tags: asStringList(event.target.value) })
            }
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
  readOnly = false,
  value,
  onChange,
}: {
  label: string;
  readOnly?: boolean;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <label className="text-xs font-medium text-muted-foreground">
        {label}
      </label>
      <Textarea
        value={value}
        readOnly={readOnly}
        onChange={(event) => {
          if (!readOnly) onChange(event.target.value);
        }}
        className={cn(
          'min-h-28 font-mono text-xs',
          readOnly && 'cursor-default bg-slate-50 text-slate-500',
        )}
      />
    </div>
  );
}
