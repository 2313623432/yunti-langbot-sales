import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  BadgeDollarSign,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  Circle,
  Database,
  Handshake,
  RefreshCw,
  Workflow,
} from 'lucide-react';
import { toast } from 'sonner';

import { SalesOverview, SalesProduct } from '@/app/infra/entities/api';
import { httpClient, initializeUserInfo } from '@/app/infra/http';
import { hasCustomSalesProduct } from '@/app/home/products/components/ProductLibraryManager';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

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

function Metric({
  icon,
  label,
  value,
  tone,
  hint,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  value: number;
  tone: string;
  hint?: string;
  onClick?: () => void;
}) {
  const clickable = Boolean(onClick);
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!clickable}
      className={`rounded-lg border border-slate-200 bg-white px-4 py-3 text-left shadow-sm transition ${
        clickable
          ? 'cursor-pointer hover:border-emerald-300 hover:shadow-md'
          : 'cursor-default'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-slate-500">{label}</span>
        <span className={`rounded-md p-2 ${tone}`}>{icon}</span>
      </div>
      <div className="mt-3 text-3xl font-semibold text-slate-950">{value}</div>
      {hint && (
        <p className="mt-2 text-xs text-slate-500">
          {hint}
          {clickable && (
            <ArrowRight className="ml-1 inline size-3 align-middle" />
          )}
        </p>
      )}
    </button>
  );
}

type OnboardingStep = {
  id: string;
  title: string;
  description: string;
  done: boolean;
  actionLabel: string;
  onAction: () => void;
};

function OnboardingChecklist({ steps }: { steps: OnboardingStep[] }) {
  const completed = steps.filter((step) => step.done).length;
  if (completed === steps.length) return null;

  return (
    <section className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-950">
            开始使用 AI 销售
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            完成以下步骤后，数字员工即可基于你的产品资料自动接待客户。
          </p>
        </div>
        <Badge
          variant="outline"
          className="border-emerald-300 bg-white text-emerald-700"
        >
          {completed}/{steps.length} 已完成
        </Badge>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {steps.map((step) => (
          <div
            key={step.id}
            className="rounded-lg border border-white/80 bg-white p-3 shadow-sm"
          >
            <div className="flex items-start gap-2">
              {step.done ? (
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
              ) : (
                <Circle className="mt-0.5 size-4 shrink-0 text-slate-400" />
              )}
              <div className="min-w-0">
                <p className="text-sm font-semibold text-slate-950">
                  {step.title}
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-600">
                  {step.description}
                </p>
                {!step.done && (
                  <Button
                    variant="link"
                    size="sm"
                    className="mt-2 h-auto p-0 text-emerald-700"
                    onClick={step.onAction}
                  >
                    {step.actionLabel}
                    <ArrowRight className="size-3.5" />
                  </Button>
                )}
              </div>
            </div>
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

  const goProductLibrary = () => navigate('/home/products');

  const onboardingSteps = useMemo<OnboardingStep[]>(
    () => [
      {
        id: 'channel',
        title: '接入沟通渠道',
        description: '连接企业微信客服、智能机器人或应用，接收客户消息。',
        done: botsCount > 0,
        actionLabel: '去配置渠道',
        onAction: openWeComWizard,
      },
      {
        id: 'product',
        title: '录入在售产品',
        description: '填写真实产品卖点、价格和链接，供 AI 回复时引用。',
        done: hasCustomProduct,
        actionLabel: '前往产品库',
        onAction: goProductLibrary,
      },
      {
        id: 'pipeline',
        title: '创建数字员工',
        description: '配置销售流程与自动回复，让 AI 在渠道里真正跑起来。',
        done: pipelinesCount > 0,
        actionLabel: '去创建数字员工',
        onAction: () => navigate('/home/pipelines'),
      },
    ],
    [botsCount, hasCustomProduct, pipelinesCount, navigate],
  );

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

  const goSalesChat = () => navigate('/home/sales-chat');

  const currentOverview = overview || {
    products_count: products.length,
    customers_count: 0,
    open_handoffs_count: 0,
    outreach_plans_count: 0,
  };

  return (
    <div className="h-full min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain bg-[#f6f5ef] p-3 text-slate-900 sm:p-4">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-3 sm:gap-4">
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-3 inline-flex flex-wrap items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700">
                <span className="rounded-sm border border-slate-950 bg-white px-1.5 py-0.5 text-[10px] font-black leading-none text-slate-950">
                  云梯
                </span>
                <BadgeDollarSign className="size-4" />
                <span>云梯科技 · AI销售系统</span>
              </div>
              <h1 className="text-2xl font-semibold text-slate-950 sm:text-3xl">
                云梯 AI销售工作台
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                查看销售运营概览。产品资料请在产品库维护；客户会话、人工接入和触达计划请前往聚合聊天。
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => void loadSalesData()}
              disabled={loading}
              className="w-full sm:w-auto"
            >
              <RefreshCw className="size-4" />
              刷新
            </Button>
          </div>
        </section>

        <OnboardingChecklist steps={onboardingSteps} />

        <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Metric
            label="产品库"
            value={currentOverview.products_count}
            icon={<Database className="size-4" />}
            tone="bg-sky-50 text-sky-700"
            hint="前往产品库管理"
            onClick={goProductLibrary}
          />
          <Metric
            label="客户记忆"
            value={currentOverview.customers_count}
            icon={<BrainCircuit className="size-4" />}
            tone="bg-emerald-50 text-emerald-700"
            hint="去聚合聊天查看"
            onClick={goSalesChat}
          />
          <Metric
            label="待人工接入"
            value={currentOverview.open_handoffs_count}
            icon={<Handshake className="size-4" />}
            tone="bg-red-50 text-red-700"
            hint="去聚合聊天处理"
            onClick={goSalesChat}
          />
          <Metric
            label="触达计划"
            value={currentOverview.outreach_plans_count}
            icon={<CalendarClock className="size-4" />}
            tone="bg-amber-50 text-amber-700"
            hint="去聚合聊天管理"
            onClick={goSalesChat}
          />
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-950">
                产品资料管理
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                维护在售产品、课程资料与卖点信息。数字员工回复客户时会引用产品库中的内容。
              </p>
            </div>
            <Button onClick={goProductLibrary}>
              <Database className="size-4" />
              前往产品库管理
            </Button>
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-950">
                会话运营与触达
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                查看客户聊天、处理人工接入、管理触达计划，统一在聚合聊天完成。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={goSalesChat}>
                <Handshake className="size-4" />
                打开聚合聊天
              </Button>
              <Button
                variant="outline"
                onClick={() => navigate('/home/pipelines')}
              >
                <Workflow className="size-4" />
                配置数字员工
              </Button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
