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
  PackagePlus,
  RefreshCw,
  Save,
  Workflow,
} from 'lucide-react';
import { toast } from 'sonner';

import { SalesOverview, SalesProduct } from '@/app/infra/entities/api';
import { httpClient, initializeUserInfo } from '@/app/infra/http';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';

type ProductDraft = {
  name: string;
  category: string;
  price: string;
  link: string;
  description: string;
  selling_points: string;
  pain_points: string;
  objections: string;
  audience: string;
  enabled: boolean;
};

const emptyProduct: ProductDraft = {
  name: '',
  category: '',
  price: '',
  link: '',
  description: '',
  selling_points: '',
  pain_points: '',
  objections: '',
  audience: '',
  enabled: true,
};

const DEFAULT_PRODUCT_UUIDS = new Set([
  'sales-ai-assistant',
  'product-knowledge-base',
]);

const splitList = (value: string): string[] =>
  value
    .split(/[\n,，;；]/)
    .map((item) => item.trim())
    .filter(Boolean);

const joinList = (value?: string[]): string => (value || []).join('\n');

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

function SectionTitle({
  icon,
  title,
  action,
  subtitle,
}: {
  icon: ReactNode;
  title: string;
  action?: React.ReactNode;
  subtitle?: string;
}) {
  return (
    <div className="border-b border-slate-200 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="rounded-md bg-slate-100 p-2 text-slate-700">
            {icon}
          </span>
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-slate-950">
              {title}
            </h2>
            {subtitle && (
              <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
            )}
          </div>
        </div>
        {action}
      </div>
    </div>
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
  const [savingProduct, setSavingProduct] = useState(false);
  const [editingUuid, setEditingUuid] = useState<string | null>(null);
  const [productDraft, setProductDraft] = useState<ProductDraft>(emptyProduct);

  const hasCustomProduct = useMemo(
    () =>
      products.some(
        (product) =>
          product.uuid && !DEFAULT_PRODUCT_UUIDS.has(product.uuid),
      ),
    [products],
  );

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
        actionLabel: '填写产品资料',
        onAction: () => {
          document
            .getElementById('sales-product-section')
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        },
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

  const updateProductDraft = (
    key: keyof ProductDraft,
    value: string | boolean,
  ) => {
    setProductDraft((draft) => ({ ...draft, [key]: value }));
  };

  const saveProduct = async () => {
    if (!productDraft.name.trim()) {
      toast.error('产品名称不能为空');
      return;
    }
    setSavingProduct(true);
    try {
      const payload = {
        name: productDraft.name.trim(),
        category: productDraft.category.trim(),
        price: productDraft.price.trim(),
        link: productDraft.link.trim(),
        description: productDraft.description.trim(),
        selling_points: splitList(productDraft.selling_points),
        pain_points: splitList(productDraft.pain_points),
        objections: splitList(productDraft.objections),
        audience: splitList(productDraft.audience),
        enabled: productDraft.enabled,
      };
      if (editingUuid) {
        await httpClient.updateSalesProduct(editingUuid, payload);
        toast.success('产品已更新');
      } else {
        await httpClient.createSalesProduct(payload);
        toast.success('产品已入库');
      }
      setEditingUuid(null);
      setProductDraft(emptyProduct);
      await loadSalesData(false);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSavingProduct(false);
    }
  };

  const editProduct = (product: SalesProduct) => {
    setEditingUuid(product.uuid || null);
    setProductDraft({
      name: product.name,
      category: product.category,
      price: product.price,
      link: product.link,
      description: product.description,
      selling_points: joinList(product.selling_points),
      pain_points: joinList(product.pain_points),
      objections: joinList(product.objections),
      audience: joinList(product.audience),
      enabled: product.enabled,
    });
    document
      .getElementById('sales-product-section')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const deleteProduct = async (product: SalesProduct) => {
    if (!product.uuid) return;
    try {
      await httpClient.deleteSalesProduct(product.uuid);
      await loadSalesData(false);
      toast.success('产品已删除');
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

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
                在这里维护产品资料。客户会话、人工接入和触达计划请前往聚合聊天。
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => void loadSalesData()}
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
            hint="在本页维护"
            onClick={() =>
              document
                .getElementById('sales-product-section')
                ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
            }
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

        <section
          id="sales-product-section"
          className="rounded-lg border border-slate-200 bg-white shadow-sm"
        >
          <SectionTitle
            icon={<PackagePlus className="size-4" />}
            title="产品数据库"
            subtitle="数字员工回复客户时会引用这里的产品资料"
            action={
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <span>启用</span>
                <Switch
                  checked={productDraft.enabled}
                  onCheckedChange={(checked) =>
                    updateProductDraft('enabled', checked)
                  }
                />
              </div>
            }
          />
          <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-[0.95fr_1.05fr]">
            <div className="space-y-3">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <Input
                  value={productDraft.name}
                  onChange={(event) =>
                    updateProductDraft('name', event.target.value)
                  }
                  placeholder="产品名称"
                />
                <Input
                  value={productDraft.category}
                  onChange={(event) =>
                    updateProductDraft('category', event.target.value)
                  }
                  placeholder="分类"
                />
                <Input
                  value={productDraft.price}
                  onChange={(event) =>
                    updateProductDraft('price', event.target.value)
                  }
                  placeholder="价格或套餐"
                />
                <Input
                  value={productDraft.link}
                  onChange={(event) =>
                    updateProductDraft('link', event.target.value)
                  }
                  placeholder="产品链接"
                />
              </div>
              <Textarea
                value={productDraft.description}
                onChange={(event) =>
                  updateProductDraft('description', event.target.value)
                }
                placeholder="产品描述"
                className="min-h-20"
              />
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <Textarea
                  value={productDraft.selling_points}
                  onChange={(event) =>
                    updateProductDraft('selling_points', event.target.value)
                  }
                  placeholder="卖点，一行一个"
                  className="min-h-28"
                />
                <Textarea
                  value={productDraft.pain_points}
                  onChange={(event) =>
                    updateProductDraft('pain_points', event.target.value)
                  }
                  placeholder="客户痛点，一行一个"
                  className="min-h-28"
                />
                <Textarea
                  value={productDraft.objections}
                  onChange={(event) =>
                    updateProductDraft('objections', event.target.value)
                  }
                  placeholder="常见异议，一行一个"
                  className="min-h-24"
                />
                <Textarea
                  value={productDraft.audience}
                  onChange={(event) =>
                    updateProductDraft('audience', event.target.value)
                  }
                  placeholder="适用客户，一行一个"
                  className="min-h-24"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={saveProduct} disabled={savingProduct}>
                  <Save className="size-4" />
                  {editingUuid ? '保存修改' : '入库'}
                </Button>
                {editingUuid && (
                  <Button
                    variant="outline"
                    onClick={() => {
                      setEditingUuid(null);
                      setProductDraft(emptyProduct);
                    }}
                  >
                    取消
                  </Button>
                )}
              </div>
            </div>

            <div className="min-h-[360px] overflow-hidden rounded-lg border border-slate-200">
              <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-3 py-2">
                <span className="text-sm font-medium text-slate-700">
                  已入库产品
                </span>
                {loading && (
                  <Badge variant="outline" className="text-slate-500">
                    加载中
                  </Badge>
                )}
              </div>
              <div className="max-h-[520px] divide-y divide-slate-200 overflow-auto">
                {products.map((product) => (
                  <div key={product.uuid || product.name} className="p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-semibold text-slate-950">
                            {product.name}
                          </p>
                          <Badge
                            variant="outline"
                            className={
                              product.enabled
                                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                : 'border-slate-200 bg-slate-50 text-slate-500'
                            }
                          >
                            {product.enabled ? '启用' : '停用'}
                          </Badge>
                          {product.uuid &&
                            DEFAULT_PRODUCT_UUIDS.has(product.uuid) && (
                              <Badge
                                variant="outline"
                                className="text-slate-500"
                              >
                                示例
                              </Badge>
                            )}
                        </div>
                        <p className="mt-1 line-clamp-2 text-sm text-slate-600">
                          {product.description || '暂无描述'}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {(product.selling_points || [])
                            .slice(0, 3)
                            .map((point) => (
                              <Badge
                                key={point}
                                variant="secondary"
                                className="bg-sky-50 text-sky-700"
                              >
                                {point}
                              </Badge>
                            ))}
                        </div>
                      </div>
                      <div className="flex shrink-0 gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => editProduct(product)}
                        >
                          编辑
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteProduct(product)}
                        >
                          删除
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
                {!products.length && (
                  <div className="p-6 text-center text-sm text-slate-500">
                    暂无产品，请先录入你在售的产品资料
                  </div>
                )}
              </div>
            </div>
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
