import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  BadgeDollarSign,
  BarChart3,
  Bot,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  CircleAlert,
  Database,
  FileText,
  Handshake,
  MessageSquareText,
  RefreshCw,
  Rocket,
  Route,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
  WandSparkles,
  Workflow,
} from 'lucide-react';
import { toast } from 'sonner';

import { SalesOverview, SalesProduct } from '@/app/infra/entities/api';
import { httpClient, initializeUserInfo } from '@/app/infra/http';
import { hasCustomSalesProduct } from '@/app/home/products/utils/productUtils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const errorMessage = (error: unknown): string => {
  if (error && typeof error === 'object' && 'msg' in error) {
    return String((error as { msg?: string }).msg);
  }
  if (error instanceof Error) return error.message;
  return '请求失败';
};

const openWeComWizard = () => {
  window.location.href = '/wizard';
};

type AgentMetric = {
  icon: ReactNode;
  label: string;
  value: number;
  description: string;
  tone: string;
  onClick?: () => void;
};

type SetupStep = {
  id: string;
  title: string;
  description: string;
  detail: string;
  done: boolean;
  actionLabel: string;
  icon: ReactNode;
  onAction: () => void;
};

type JourneyStage = {
  title: string;
  label: string;
  description: string;
  icon: ReactNode;
};

type WorkflowTemplate = {
  title: string;
  description: string;
  actionLabel: string;
  icon: ReactNode;
  onAction: () => void;
};

type PlaybookSignal = {
  title: string;
  value: string;
  description: string;
};

type LaunchCheck = {
  title: string;
  description: string;
  done: boolean;
  actionLabel: string;
  onAction: () => void;
};

function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
        {description && (
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}

function MetricCard({ metric }: { metric: AgentMetric }) {
  const clickable = Boolean(metric.onClick);
  return (
    <button
      type="button"
      onClick={metric.onClick}
      disabled={!clickable}
      className={cn(
        'rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm transition',
        clickable
          ? 'cursor-pointer hover:border-indigo-200 hover:shadow-md'
          : 'cursor-default',
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-slate-500">
          {metric.label}
        </span>
        <span className={cn('rounded-md p-2', metric.tone)}>{metric.icon}</span>
      </div>
      <div className="mt-4 text-3xl font-semibold text-slate-950">
        {metric.value}
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-500">
        {metric.description}
        {clickable && <ArrowRight className="ml-1 inline size-3" />}
      </p>
    </button>
  );
}

function ReadinessBar({
  completed,
  total,
}: {
  completed: number;
  total: number;
}) {
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700">上线准备度</span>
        <span className="text-slate-500">{percentage}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-indigo-600 transition-all"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

function SetupStepCard({ step }: { step: SetupStep }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span
          className={cn(
            'flex size-10 shrink-0 items-center justify-center rounded-lg',
            step.done
              ? 'bg-emerald-50 text-emerald-700'
              : 'bg-indigo-50 text-indigo-700',
          )}
        >
          {step.icon}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-slate-950">{step.title}</h3>
            {step.done && (
              <Badge className="bg-emerald-50 text-emerald-700 hover:bg-emerald-50">
                已就绪
              </Badge>
            )}
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {step.description}
          </p>
          <p className="mt-2 text-xs leading-5 text-slate-500">{step.detail}</p>
          <Button
            variant={step.done ? 'outline' : 'default'}
            size="sm"
            className="mt-3"
            onClick={step.onAction}
          >
            {step.actionLabel}
            <ArrowRight className="size-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function JourneyCard({ stage }: { stage: JourneyStage }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-500">
          {stage.label}
        </span>
        <span className="text-indigo-600">{stage.icon}</span>
      </div>
      <h3 className="mt-4 text-base font-semibold text-slate-950">
        {stage.title}
      </h3>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        {stage.description}
      </p>
    </div>
  );
}

function WorkflowTemplateCard({ template }: { template: WorkflowTemplate }) {
  return (
    <button
      type="button"
      onClick={template.onAction}
      className="rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-indigo-200 hover:shadow-md"
    >
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
          {template.icon}
        </span>
        <div className="min-w-0">
          <h3 className="font-semibold text-slate-950">{template.title}</h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {template.description}
          </p>
          <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-indigo-700">
            {template.actionLabel}
            <ArrowRight className="size-3.5" />
          </span>
        </div>
      </div>
    </button>
  );
}

function ProductReadiness({ products }: { products: SalesProduct[] }) {
  const shownProducts = products.slice(0, 4);
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <SectionHeader
        title="内容与产品准备"
        description="销售智能体需要可引用的产品资料、价格信息、卖点和异议处理内容。"
      />
      <div className="mt-4 divide-y divide-slate-100">
        {shownProducts.map((product) => (
          <div
            key={product.uuid || product.name}
            className="grid gap-3 py-3 md:grid-cols-[minmax(0,1fr)_120px_120px]"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate font-medium text-slate-950">
                  {product.name}
                </p>
                <Badge variant="outline">{product.category || '未分类'}</Badge>
              </div>
              <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-600">
                {product.description || '暂无产品说明'}
              </p>
            </div>
            <div className="text-sm">
              <p className="text-slate-500">卖点</p>
              <p className="mt-1 font-medium text-slate-950">
                {product.selling_points?.length || 0} 条
              </p>
            </div>
            <div className="text-sm">
              <p className="text-slate-500">状态</p>
              <p
                className={cn(
                  'mt-1 font-medium',
                  product.enabled ? 'text-emerald-700' : 'text-slate-500',
                )}
              >
                {product.enabled ? '可用' : '停用'}
              </p>
            </div>
          </div>
        ))}
        {!shownProducts.length && (
          <div className="py-8 text-center text-sm text-slate-500">
            暂无产品资料，先录入真实在售产品后再测试销售智能体。
          </div>
        )}
      </div>
    </section>
  );
}

function PreviewPanel({ onOpenChat }: { onOpenChat: () => void }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <SectionHeader
        title="上线前预览"
        description="把测试问题、命中内容和销售动作放在同一处。"
        action={
          <Button variant="outline" size="sm" onClick={onOpenChat}>
            打开真实会话
          </Button>
        }
      />
      <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
        <div className="space-y-3">
          <div className="max-w-[82%] rounded-lg bg-white px-4 py-3 text-sm leading-6 text-slate-700 shadow-sm">
            孩子三年级，数学基础一般，有没有短期能提分的课？
          </div>
          <div className="ml-auto max-w-[86%] rounded-lg bg-slate-950 px-4 py-3 text-sm leading-6 text-white shadow-sm">
            可以先判断年级、目标分数和可接受时间，再从产品库匹配课程，并补充是否需要人工老师跟进。
          </div>
        </div>
        <div className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
          <div className="rounded-md bg-white p-3">
            <p className="font-medium text-slate-950">识别意图</p>
            <p className="mt-1 text-xs text-slate-500">提分咨询 / 产品匹配</p>
          </div>
          <div className="rounded-md bg-white p-3">
            <p className="font-medium text-slate-950">缺失信息</p>
            <p className="mt-1 text-xs text-slate-500">预算、可上课时间</p>
          </div>
          <div className="rounded-md bg-white p-3">
            <p className="font-medium text-slate-950">下一步</p>
            <p className="mt-1 text-xs text-slate-500">推荐课程或转人工</p>
          </div>
        </div>
      </div>
    </section>
  );
}

function PlaybookPanel({
  signals,
  onConfigure,
}: {
  signals: PlaybookSignal[];
  onConfigure: () => void;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <SectionHeader
        title="销售 Playbook"
        description="把销售智能体要识别的信号、要追问的信息和转人工条件集中到一张规则摘要里。"
        action={
          <Button variant="outline" size="sm" onClick={onConfigure}>
            <WandSparkles className="size-4" />
            配置规则
          </Button>
        }
      />
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {signals.map((signal) => (
          <div
            key={signal.title}
            className="rounded-lg border border-slate-100 bg-slate-50 p-4"
          >
            <div className="text-sm font-medium text-slate-500">
              {signal.title}
            </div>
            <div className="mt-2 text-lg font-semibold text-slate-950">
              {signal.value}
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              {signal.description}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function LaunchChecklist({ checks }: { checks: LaunchCheck[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <SectionHeader
        title="上线检查"
        description="上线前先确认内容、流程、渠道和人工接管都能串起来。"
      />
      <div className="mt-4 space-y-3">
        {checks.map((check) => (
          <div
            key={check.title}
            className="flex items-start gap-3 rounded-lg border border-slate-100 bg-slate-50 p-3"
          >
            <span
              className={cn(
                'mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full',
                check.done
                  ? 'bg-emerald-50 text-emerald-700'
                  : 'bg-amber-50 text-amber-700',
              )}
            >
              {check.done ? (
                <CheckCircle2 className="size-4" />
              ) : (
                <CircleAlert className="size-4" />
              )}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-medium text-slate-950">{check.title}</h3>
                <Badge
                  variant="outline"
                  className={cn(
                    check.done
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border-amber-200 bg-amber-50 text-amber-700',
                  )}
                >
                  {check.done ? '通过' : '待完善'}
                </Badge>
              </div>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                {check.description}
              </p>
            </div>
            <Button
              variant={check.done ? 'ghost' : 'outline'}
              size="sm"
              onClick={check.onAction}
              className="shrink-0"
            >
              {check.actionLabel}
            </Button>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function SalesPage() {
  const navigate = useNavigate();
  const [overview, setOverview] = useState<SalesOverview | null>(null);
  const [products, setProducts] = useState<SalesProduct[]>([]);
  const [botsCount, setBotsCount] = useState(0);
  const [pipelinesCount, setPipelinesCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const hasCustomProduct = useMemo(
    () => hasCustomSalesProduct(products),
    [products],
  );

  const enabledProducts = useMemo(
    () => products.filter((product) => product.enabled),
    [products],
  );

  const goProductLibrary = () => navigate('/home/products');
  const goSalesChat = () => navigate('/home/sales-chat');
  const goPipelines = () => navigate('/home/pipelines');
  const goWorkflows = () => navigate('/home/workflows');
  const goKnowledge = () => navigate('/home/knowledge');

  const setupSteps: SetupStep[] = [
    {
      id: 'playbook',
      title: '销售 Playbook',
      description: '定义要收集的信息、线索判断标准和转人工条件。',
      detail:
        '当前先用产品库与数字员工配置承载规则，后续可升级为独立 Playbook 编辑器。',
      done: hasCustomProduct && pipelinesCount > 0,
      actionLabel: hasCustomProduct ? '配置数字员工' : '完善产品资料',
      icon: <ClipboardList className="size-5" />,
      onAction: hasCustomProduct ? goPipelines : goProductLibrary,
    },
    {
      id: 'content',
      title: '内容与知识',
      description: '准备产品卖点、价格、适用人群和异议处理素材。',
      detail: `${enabledProducts.length} 个启用产品可被销售智能体引用。`,
      done: hasCustomProduct,
      actionLabel: '管理产品库',
      icon: <FileText className="size-5" />,
      onAction: goProductLibrary,
    },
    {
      id: 'deploy',
      title: '渠道部署',
      description: '把智能体接入企业微信、私聊、群聊等真实客户入口。',
      detail: `${botsCount} 个渠道/机器人已接入。`,
      done: botsCount > 0,
      actionLabel: '配置渠道',
      icon: <Rocket className="size-5" />,
      onAction: openWeComWizard,
    },
    {
      id: 'analyze',
      title: '会话分析',
      description: '查看客户记忆、待人工接入和触达计划，持续优化转化。',
      detail: '客户收件箱中可查看真实会话、客户资料和 AI 推荐回复。',
      done:
        (overview?.customers_count || 0) > 0 ||
        (overview?.open_handoffs_count || 0) > 0,
      actionLabel: '进入会话工作台',
      icon: <BarChart3 className="size-5" />,
      onAction: goSalesChat,
    },
  ];

  const completedSteps = setupSteps.filter((step) => step.done).length;

  const playbookSignals: PlaybookSignal[] = [
    {
      title: '识别信号',
      value: '价格 / 产品 / 转人工',
      description: '从客户消息中判断咨询意图、高意向表达和需要人工介入的时机。',
    },
    {
      title: '追问字段',
      value: '年级 / 需求 / 预算',
      description: '在客户收件箱沉淀线索字段，帮助销售判断下一步动作。',
    },
    {
      title: '动作出口',
      value: '推荐产品 / 转人工 / 触达',
      description: '把不同线索分流到产品推荐、人工跟进或持续触达计划。',
    },
  ];

  const launchChecks: LaunchCheck[] = [
    {
      title: '产品内容可引用',
      description: `${enabledProducts.length} 个启用产品可供销售智能体生成回答。`,
      done: hasCustomProduct && enabledProducts.length > 0,
      actionLabel: '产品内容',
      onAction: goProductLibrary,
    },
    {
      title: '数字员工已配置',
      description: `${pipelinesCount} 个数字员工可承载销售 Playbook 和对话流程。`,
      done: pipelinesCount > 0,
      actionLabel: '数字员工',
      onAction: goPipelines,
    },
    {
      title: '真实渠道已接入',
      description: `${botsCount} 个机器人或渠道可接收客户真实消息。`,
      done: botsCount > 0,
      actionLabel: '发布渠道',
      onAction: openWeComWizard,
    },
    {
      title: '人工接管可复盘',
      description: `${overview?.open_handoffs_count || 0} 个待接入客户会出现在客户收件箱。`,
      done:
        (overview?.customers_count || 0) > 0 ||
        (overview?.open_handoffs_count || 0) > 0,
      actionLabel: '客户收件箱',
      onAction: goSalesChat,
    },
  ];

  const loadSalesData = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      await initializeUserInfo();
      const [overviewData, productResp, botsResp, pipelinesResp] =
        await Promise.all([
          httpClient.getSalesOverview(),
          httpClient.getSalesProducts(),
          httpClient.getBots(),
          httpClient.getPipelines(),
        ]);
      setOverview(overviewData);
      setProducts(productResp.products || []);
      setBotsCount(botsResp.bots?.length ?? 0);
      setPipelinesCount(pipelinesResp.pipelines?.length ?? 0);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  const refreshOverview = async () => {
    try {
      const overviewData = await httpClient.getSalesOverview();
      setOverview(overviewData);
    } catch {
      // Silent refresh for background polling
    }
  };

  useEffect(() => {
    void loadSalesData();
    const timer = window.setInterval(() => {
      void refreshOverview();
    }, 30000);
    return () => window.clearInterval(timer);
  }, []);

  const currentOverview = overview || {
    products_count: products.length,
    customers_count: 0,
    open_handoffs_count: 0,
    outreach_plans_count: 0,
    products: [],
    recent_memories: [],
    open_handoffs: [],
    outreach_plans: [],
  };

  const metrics: AgentMetric[] = [
    {
      label: '产品内容',
      value: currentOverview.products_count,
      icon: <Database className="size-4" />,
      tone: 'bg-sky-50 text-sky-700',
      description: '销售回答可引用的产品资料',
      onClick: goProductLibrary,
    },
    {
      label: '客户记忆',
      value: currentOverview.customers_count,
      icon: <BrainCircuit className="size-4" />,
      tone: 'bg-indigo-50 text-indigo-700',
      description: '已沉淀的客户画像和意图',
      onClick: goSalesChat,
    },
    {
      label: '待人工接入',
      value: currentOverview.open_handoffs_count,
      icon: <Handshake className="size-4" />,
      tone: 'bg-rose-50 text-rose-700',
      description: '需要销售跟进的高意向会话',
      onClick: goSalesChat,
    },
    {
      label: '触达计划',
      value: currentOverview.outreach_plans_count,
      icon: <CalendarClock className="size-4" />,
      tone: 'bg-amber-50 text-amber-700',
      description: '定时跟进与复购提醒任务',
      onClick: goSalesChat,
    },
  ];

  const journeyStages: JourneyStage[] = [
    {
      label: 'ENGAGE',
      title: '主动接待',
      description:
        '在真实渠道中接住客户问题，识别价格、产品、异议和转人工意图。',
      icon: <MessageSquareText className="size-5" />,
    },
    {
      label: 'DISCOVER',
      title: '产品发现',
      description: '基于产品库解释卖点、适用人群、课程价格和下一步推荐。',
      icon: <Database className="size-5" />,
    },
    {
      label: 'QUALIFY',
      title: '线索判断',
      description:
        '沉淀客户阶段、需求、预算、孩子年级等信息，辅助销售判断优先级。',
      icon: <Users className="size-5" />,
    },
    {
      label: 'CLOSE',
      title: '转化跟进',
      description: '高意向客户转人工，低意向客户进入触达计划或继续 AI 托管。',
      icon: <Handshake className="size-5" />,
    },
  ];

  const workflowTemplates: WorkflowTemplate[] = [
    {
      title: '高意向转人工',
      description: '当客户询价、要求老师跟进或表达购买意向时，推入待人工队列。',
      actionLabel: '查看会话队列',
      icon: <Route className="size-5" />,
      onAction: goSalesChat,
    },
    {
      title: '产品内容补全',
      description: '补齐价格、卖点、痛点、异议处理，让智能体回答更稳定。',
      actionLabel: '维护产品内容',
      icon: <ShieldCheck className="size-5" />,
      onAction: goProductLibrary,
    },
    {
      title: '持续触达',
      description: '把暂未成交客户放入触达计划，按照节奏继续唤醒和跟进。',
      actionLabel: '进入工作台',
      icon: <Send className="size-5" />,
      onAction: goSalesChat,
    },
  ];

  return (
    <div className="h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain bg-[#f5f7fb] p-3 text-slate-900 sm:p-4">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-4">
        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_420px]">
            <div className="p-5 sm:p-6">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-2 rounded-md border border-indigo-100 bg-indigo-50 px-3 py-1 text-sm font-medium text-indigo-700">
                  <Bot className="size-4" />
                  销售智能体
                </span>
                <Badge
                  variant="outline"
                  className="border-slate-200 bg-white text-slate-600"
                >
                  AI 托管 + 人工接管
                </Badge>
              </div>
              <h1 className="mt-5 max-w-3xl text-3xl font-semibold leading-tight text-slate-950 sm:text-4xl">
                一个智能体，覆盖获客、发现、判断和跟进
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600 sm:text-base">
                把配置入口收敛为
                Playbook、内容、部署、分析四件事；销售人员在客户收件箱里接管高意向客户。
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <Button
                  onClick={hasCustomProduct ? goPipelines : goProductLibrary}
                >
                  <Sparkles className="size-4" />
                  {hasCustomProduct ? '配置销售 Playbook' : '先完善产品资料'}
                </Button>
                <Button variant="outline" onClick={goSalesChat}>
                  <MessageSquareText className="size-4" />
                  进入会话工作台
                </Button>
                <Button variant="ghost" onClick={() => void loadSalesData()}>
                  <RefreshCw
                    className={cn('size-4', loading && 'animate-spin')}
                  />
                  刷新数据
                </Button>
              </div>
            </div>
            <div className="border-t border-slate-200 bg-slate-950 p-5 text-white lg:border-l lg:border-t-0 sm:p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-300">上线准备</p>
                  <p className="mt-1 text-2xl font-semibold">
                    {completedSteps}/{setupSteps.length} 已就绪
                  </p>
                </div>
                <span className="rounded-lg bg-white/10 p-3 text-indigo-200">
                  <BadgeDollarSign className="size-6" />
                </span>
              </div>
              <div className="mt-6">
                <ReadinessBar
                  completed={completedSteps}
                  total={setupSteps.length}
                />
              </div>
              <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-lg bg-white/10 p-3">
                  <p className="text-slate-300">启用产品</p>
                  <p className="mt-2 text-2xl font-semibold">
                    {enabledProducts.length}
                  </p>
                </div>
                <div className="rounded-lg bg-white/10 p-3">
                  <p className="text-slate-300">数字员工</p>
                  <p className="mt-2 text-2xl font-semibold">
                    {pipelinesCount}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => (
            <MetricCard key={metric.label} metric={metric} />
          ))}
        </section>

        <section className="grid gap-3 xl:grid-cols-4">
          {journeyStages.map((stage) => (
            <JourneyCard key={stage.label} stage={stage} />
          ))}
        </section>

        <section className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
          <PlaybookPanel signals={playbookSignals} onConfigure={goPipelines} />
          <LaunchChecklist checks={launchChecks} />
        </section>

        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(420px,0.8fr)]">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 shadow-sm">
            <SectionHeader
              title="搭建路径"
              description="从业务 Playbook 到真实渠道部署逐步完成。"
            />
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {setupSteps.map((step) => (
                <SetupStepCard key={step.id} step={step} />
              ))}
            </div>
          </div>
          <PreviewPanel onOpenChat={goSalesChat} />
        </section>

        <section className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
          <ProductReadiness products={products} />
          <section className="rounded-lg border border-slate-200 bg-slate-50 p-4 shadow-sm">
            <SectionHeader
              title="推荐工作流"
              description="先从销售场景模板开始，再逐步进入完整工作流画布。"
              action={
                <Button variant="outline" size="sm" onClick={goWorkflows}>
                  <Workflow className="size-4" />
                  打开工作流
                </Button>
              }
            />
            <div className="mt-4 grid gap-3">
              {workflowTemplates.map((template) => (
                <WorkflowTemplateCard
                  key={template.title}
                  template={template}
                />
              ))}
            </div>
          </section>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">
                下一步：把知识、流程和会话合成一个闭环
              </h2>
              <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
                产品资料负责回答，数字员工负责流程，客户收件箱负责人工接管和复盘。
                后续可以把 Playbook 独立成“自然语言生成规则”的配置页。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={goKnowledge}>
                <FileText className="size-4" />
                知识库
              </Button>
              <Button variant="outline" onClick={goPipelines}>
                <Workflow className="size-4" />
                数字员工
              </Button>
              <Button onClick={goSalesChat}>
                <Handshake className="size-4" />
                处理线索
              </Button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
