import { type ReactNode, useEffect, useMemo, useState } from 'react';
import {
  BadgeDollarSign,
  Bot,
  BrainCircuit,
  Building2,
  CalendarClock,
  Database,
  Handshake,
  LinkIcon,
  MessageSquareReply,
  PackagePlus,
  PlugZap,
  RefreshCw,
  Save,
  Send,
  Sparkles,
  UserRoundCheck,
} from 'lucide-react';
import { toast } from 'sonner';

import {
  SalesCustomerMemory,
  SalesHandoff,
  SalesIntent,
  SalesOutreachPlan,
  SalesOverview,
  SalesProduct,
} from '@/app/infra/entities/api';
import { httpClient, initializeUserInfo } from '@/app/infra/http';
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

type OutreachDraft = {
  name: string;
  product_uuid: string;
  bot_uuid: string;
  target_type: 'person' | 'group';
  target_id: string;
  segment: string;
  message_template: string;
  scheduled_at: string;
  interval_minutes: number;
  enabled: boolean;
};

const toDatetimeLocalValue = (date = new Date()): string => {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate(),
  )}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
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

const emptyOutreach: OutreachDraft = {
  name: '',
  product_uuid: '',
  bot_uuid: '',
  target_type: 'person',
  target_id: '',
  segment: '',
  message_template:
    '给你推荐一个适合当前需求的方案：{product_name}。核心卖点：{selling_points}。详情：{link}',
  scheduled_at: toDatetimeLocalValue(),
  interval_minutes: 0,
  enabled: true,
};

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

const formatDate = (value?: string | null): string => {
  if (!value) return '未触达';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN');
};

const intentStyle = (intent?: string): string => {
  if (intent === 'handoff') return 'border-red-200 bg-red-50 text-red-700';
  if (intent === 'purchase' || intent === 'price') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  }
  if (intent === 'comparison' || intent === 'objection') {
    return 'border-amber-200 bg-amber-50 text-amber-700';
  }
  return 'border-slate-200 bg-slate-50 text-slate-700';
};

const intentLabel = (intent?: string): string =>
  (
    ({
      handoff: '转人工',
      price: '价格咨询',
      purchase: '购买意向',
      comparison: '对比咨询',
      objection: '异议处理',
      product_interest: '产品兴趣',
      general: '普通咨询',
    }) as Record<string, string>
  )[intent || ''] || '未识别';

const stageLabel = (stage?: string): string =>
  (
    ({
      new: '新客户',
      consideration: '考虑中',
      high_intent: '高意向',
      handoff: '已转人工',
    }) as Record<string, string>
  )[stage || ''] ||
  stage ||
  '新客户';

const handoffStatusLabel = (status?: string): string =>
  (
    ({
      open: '待接入',
      handled: '已处理',
      closed: '已关闭',
    }) as Record<string, string>
  )[status || ''] ||
  status ||
  '待接入';

const targetTypeLabel = (targetType?: string): string =>
  targetType === 'group' ? '群组' : '个人';

const openWeComWizard = () => {
  window.location.href = '/wizard';
};

function Metric({
  icon,
  label,
  value,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: number;
  tone: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-slate-500">{label}</span>
        <span className={`rounded-md p-2 ${tone}`}>{icon}</span>
      </div>
      <div className="mt-3 text-3xl font-semibold text-slate-950">{value}</div>
    </div>
  );
}

function SectionTitle({
  icon,
  title,
  action,
}: {
  icon: ReactNode;
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
      <div className="flex min-w-0 items-center gap-2">
        <span className="rounded-md bg-slate-100 p-2 text-slate-700">
          {icon}
        </span>
        <h2 className="truncate text-base font-semibold text-slate-950">
          {title}
        </h2>
      </div>
      {action}
    </div>
  );
}

export default function SalesPage() {
  const [overview, setOverview] = useState<SalesOverview | null>(null);
  const [products, setProducts] = useState<SalesProduct[]>([]);
  const [memories, setMemories] = useState<SalesCustomerMemory[]>([]);
  const [handoffs, setHandoffs] = useState<SalesHandoff[]>([]);
  const [outreachPlans, setOutreachPlans] = useState<SalesOutreachPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingProduct, setSavingProduct] = useState(false);
  const [editingUuid, setEditingUuid] = useState<string | null>(null);
  const [productDraft, setProductDraft] = useState<ProductDraft>(emptyProduct);
  const [leadText, setLeadText] = useState(
    '客户想了解你们的 AI 销售系统，问能不能接入微信和网站客服，并希望有人给报价。',
  );
  const [customerProfile, setCustomerProfile] = useState(
    'B2B 团队，线索多，客服和销售分散在多个平台。',
  );
  const [selectedProductUuid, setSelectedProductUuid] = useState('');
  const [intent, setIntent] = useState<SalesIntent | null>(null);
  const [pitch, setPitch] = useState('');
  const [pitching, setPitching] = useState(false);
  const [handoffReply, setHandoffReply] = useState<Record<number, string>>({});
  const [replyingId, setReplyingId] = useState<number | null>(null);
  const [outreachDraft, setOutreachDraft] =
    useState<OutreachDraft>(emptyOutreach);
  const [creatingOutreach, setCreatingOutreach] = useState(false);

  const activeProduct = useMemo(
    () =>
      products.find((product) => product.uuid === selectedProductUuid) ||
      products[0],
    [products, selectedProductUuid],
  );

  useEffect(() => {
    void loadSalesData();
    const timer = window.setInterval(() => {
      void loadSalesData(false);
    }, 5000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!selectedProductUuid && products[0]?.uuid) {
      setSelectedProductUuid(products[0].uuid);
    }
    if (!outreachDraft.product_uuid && products[0]?.uuid) {
      setOutreachDraft((draft) => ({
        ...draft,
        product_uuid: products[0].uuid || '',
      }));
    }
  }, [outreachDraft.product_uuid, products, selectedProductUuid]);

  const loadSalesData = async (showLoading = true) => {
    if (showLoading) {
      setLoading(true);
    }
    try {
      await initializeUserInfo();
      const [overviewData, productResp, memoryResp, handoffResp, planResp] =
        await Promise.all([
          httpClient.getSalesOverview(),
          httpClient.getSalesProducts(),
          httpClient.getSalesMemories(),
          httpClient.getSalesHandoffs('open'),
          httpClient.getSalesOutreachPlans(),
        ]);
      setOverview(overviewData);
      setProducts(productResp.products || []);
      setMemories(memoryResp.memories || []);
      setHandoffs(handoffResp.handoffs || []);
      setOutreachPlans(planResp.plans || []);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  };

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
        const created = await httpClient.createSalesProduct(payload);
        setSelectedProductUuid(created.uuid);
        toast.success('产品已入库');
      }
      setEditingUuid(null);
      setProductDraft(emptyProduct);
      await loadSalesData();
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
  };

  const deleteProduct = async (product: SalesProduct) => {
    if (!product.uuid) return;
    try {
      await httpClient.deleteSalesProduct(product.uuid);
      if (selectedProductUuid === product.uuid) setSelectedProductUuid('');
      await loadSalesData();
      toast.success('产品已删除');
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  const generatePitch = async () => {
    if (!leadText.trim()) {
      toast.error('客户消息不能为空');
      return;
    }
    setPitching(true);
    try {
      const classified = await httpClient.classifySalesIntent(leadText);
      const generated = await httpClient.generateSalesPitch({
        message: leadText,
        product_uuid: activeProduct?.uuid,
        customer_profile: customerProfile,
        intent: classified.intent,
        tone: 'consultative',
      });
      setIntent(classified);
      setPitch(generated.pitch.message);
      if (generated.product?.uuid) {
        setSelectedProductUuid(generated.product.uuid);
      }
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setPitching(false);
    }
  };

  const replyHandoff = async (handoff: SalesHandoff) => {
    const reply = (handoffReply[handoff.id] || '').trim();
    if (!reply) {
      toast.error('接入回复不能为空');
      return;
    }
    setReplyingId(handoff.id);
    try {
      await httpClient.replySalesHandoff(handoff.id, reply, 'sales-admin');
      setHandoffReply((current) => ({ ...current, [handoff.id]: '' }));
      await loadSalesData();
      toast.success('人工回复已发送');
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setReplyingId(null);
    }
  };

  const createOutreachPlan = async () => {
    if (!outreachDraft.product_uuid || !outreachDraft.target_id.trim()) {
      toast.error('请选择产品并填写目标 ID');
      return;
    }
    setCreatingOutreach(true);
    try {
      await httpClient.createSalesOutreachPlan({
        ...outreachDraft,
        name: outreachDraft.name || '产品触达计划',
        target_id: outreachDraft.target_id.trim(),
        bot_uuid: outreachDraft.bot_uuid.trim(),
        scheduled_at: outreachDraft.scheduled_at
          ? `${outreachDraft.scheduled_at}:00`
          : toDatetimeLocalValue(),
      });
      setOutreachDraft({
        ...emptyOutreach,
        product_uuid: outreachDraft.product_uuid,
        scheduled_at: toDatetimeLocalValue(),
      });
      await loadSalesData();
      toast.success('触达计划已创建');
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setCreatingOutreach(false);
    }
  };

  const runDueOutreach = async () => {
    try {
      const result = await httpClient.runDueSalesOutreach();
      await loadSalesData();
      toast.success(`已执行 ${result.sent} 条触达`);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  const currentOverview = overview || {
    products_count: products.length,
    customers_count: memories.length,
    open_handoffs_count: handoffs.length,
    outreach_plans_count: outreachPlans.length,
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
                <span className="text-xs font-semibold tracking-wide text-emerald-600">
                  YUN TI TECHNOLOGY
                </span>
              </div>
              <h1 className="text-2xl font-semibold text-slate-950 sm:text-3xl">
                云梯 AI销售工作台
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                线索、产品、话术和人工接入集中在同一个运营界面。
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:flex sm:flex-wrap">
              <Button
                variant="outline"
                onClick={() => void loadSalesData()}
                className="w-full sm:w-auto"
              >
                <RefreshCw className="size-4" />
                刷新
              </Button>
              <Button
                onClick={generatePitch}
                disabled={pitching}
                className="w-full sm:w-auto"
              >
                <Sparkles className="size-4" />
                生成销售话术
              </Button>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Metric
            label="产品库"
            value={currentOverview.products_count}
            icon={<Database className="size-4" />}
            tone="bg-sky-50 text-sky-700"
          />
          <Metric
            label="客户记忆"
            value={currentOverview.customers_count}
            icon={<BrainCircuit className="size-4" />}
            tone="bg-emerald-50 text-emerald-700"
          />
          <Metric
            label="待人工接入"
            value={currentOverview.open_handoffs_count}
            icon={<Handshake className="size-4" />}
            tone="bg-red-50 text-red-700"
          />
          <Metric
            label="触达计划"
            value={currentOverview.outreach_plans_count}
            icon={<CalendarClock className="size-4" />}
            tone="bg-amber-50 text-amber-700"
          />
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr] lg:items-center">
            <div>
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-emerald-700">
                <Building2 className="size-4" />
                企业微信接入
              </div>
              <h2 className="text-xl font-semibold text-slate-950">
                已内置企微应用、企微智能机器人、企业微信客服三种接入方式
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                推荐销售场景优先使用“企业微信客服”或“企业微信智能机器人”。需要公网
                Webhook 时，创建机器人后复制回调地址到企微后台即可。
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              {[
                ['企业微信客服', '对外获客、售前咨询、转人工'],
                ['企微智能机器人', '群聊/内部协同、支持长连接'],
                ['企业微信应用', '企业内部应用消息回调'],
              ].map(([name, desc]) => (
                <button
                  key={name}
                  type="button"
                  onClick={openWeComWizard}
                  className="rounded-lg border border-slate-200 bg-[#fbfbf7] p-3 text-left transition hover:border-emerald-300 hover:bg-emerald-50"
                >
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                    <PlugZap className="size-4 text-emerald-700" />
                    {name}
                  </div>
                  <p className="mt-2 text-xs leading-5 text-slate-600">
                    {desc}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <SectionTitle
              icon={<PackagePlus className="size-4" />}
              title="产品数据库"
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
                            <button
                              className="truncate text-left text-sm font-semibold text-slate-950 hover:text-sky-700"
                              onClick={() =>
                                setSelectedProductUuid(product.uuid || '')
                              }
                            >
                              {product.name}
                            </button>
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
                      暂无产品
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <SectionTitle
              icon={<Bot className="size-4" />}
              title="AI销售辅助"
            />
            <div className="space-y-3 p-4">
              <Select
                value={activeProduct?.uuid || ''}
                onValueChange={setSelectedProductUuid}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择产品" />
                </SelectTrigger>
                <SelectContent>
                  {products.map((product) => (
                    <SelectItem
                      key={product.uuid || product.name}
                      value={product.uuid || product.name}
                    >
                      {product.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Textarea
                value={leadText}
                onChange={(event) => setLeadText(event.target.value)}
                placeholder="客户消息"
                className="min-h-28"
              />
              <Textarea
                value={customerProfile}
                onChange={(event) => setCustomerProfile(event.target.value)}
                placeholder="客户画像"
                className="min-h-20"
              />
              <Button onClick={generatePitch} disabled={pitching}>
                <Sparkles className="size-4" />
                {pitching ? '生成中' : '识别意图并生成话术'}
              </Button>

              <div className="rounded-lg border border-slate-200 bg-[#fbfbf7] p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    className={intentStyle(intent?.intent)}
                    variant="outline"
                  >
                    {intentLabel(intent?.intent)}
                  </Badge>
                  {intent && (
                    <span className="text-sm text-slate-500">
                      置信度 {Math.round(intent.confidence * 100)}%
                    </span>
                  )}
                  {intent?.requires_handoff && (
                    <Badge className="border-red-200 bg-red-50 text-red-700">
                      需要人工
                    </Badge>
                  )}
                </div>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-800">
                  {pitch || '暂无话术'}
                </p>
                {activeProduct?.link && (
                  <a
                    href={activeProduct.link}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-sky-700 hover:text-sky-900"
                  >
                    <LinkIcon className="size-4" />
                    {activeProduct.link}
                  </a>
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <SectionTitle
              icon={<BrainCircuit className="size-4" />}
              title="客户记忆"
            />
            <div className="max-h-[470px] divide-y divide-slate-200 overflow-auto">
              {memories.map((memory) => (
                <div key={memory.id || memory.session_id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-950">
                        {memory.customer_name ||
                          memory.user_id ||
                          memory.session_id}
                      </p>
                      <p className="mt-1 text-sm leading-6 text-slate-600">
                        {memory.summary || '暂无摘要'}
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className={intentStyle(memory.last_intent)}
                    >
                      {stageLabel(memory.stage || memory.last_intent)}
                    </Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span>{memory.platform || '未知平台'}</span>
                    <span>{formatDate(memory.last_seen_at)}</span>
                  </div>
                </div>
              ))}
              {!memories.length && (
                <div className="p-6 text-center text-sm text-slate-500">
                  暂无客户记忆
                </div>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <SectionTitle
              icon={<UserRoundCheck className="size-4" />}
              title="人工接入"
            />
            <div className="max-h-[470px] divide-y divide-slate-200 overflow-auto">
              {handoffs.map((handoff) => (
                <div key={handoff.id} className="space-y-3 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-950">
                        {handoff.user_id || handoff.session_id}
                      </p>
                      <p className="mt-1 text-sm leading-6 text-slate-600">
                        {handoff.reason}
                      </p>
                    </div>
                    <Badge className="border-red-200 bg-red-50 text-red-700">
                      {handoffStatusLabel(handoff.status)}
                    </Badge>
                  </div>
                  <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-700">
                    {handoff.last_message}
                  </div>
                  <Textarea
                    value={handoffReply[handoff.id] || ''}
                    onChange={(event) =>
                      setHandoffReply((current) => ({
                        ...current,
                        [handoff.id]: event.target.value,
                      }))
                    }
                    placeholder="人工回复"
                    className="min-h-20"
                  />
                  <Button
                    onClick={() => replyHandoff(handoff)}
                    disabled={replyingId === handoff.id}
                  >
                    <MessageSquareReply className="size-4" />
                    发送并关闭
                  </Button>
                </div>
              ))}
              {!handoffs.length && (
                <div className="p-6 text-center text-sm text-slate-500">
                  当前无待接入客户
                </div>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <SectionTitle
              icon={<CalendarClock className="size-4" />}
              title="定时推送"
              action={
                <Button variant="outline" size="sm" onClick={runDueOutreach}>
                  <Send className="size-4" />
                  执行
                </Button>
              }
            />
            <div className="space-y-3 p-4">
              <Input
                value={outreachDraft.name}
                onChange={(event) =>
                  setOutreachDraft((draft) => ({
                    ...draft,
                    name: event.target.value,
                  }))
                }
                placeholder="计划名称"
              />
              <Select
                value={outreachDraft.product_uuid}
                onValueChange={(value) =>
                  setOutreachDraft((draft) => ({
                    ...draft,
                    product_uuid: value,
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="推送产品" />
                </SelectTrigger>
                <SelectContent>
                  {products.map((product) => (
                    <SelectItem
                      key={product.uuid || product.name}
                      value={product.uuid || product.name}
                    >
                      {product.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="grid grid-cols-[0.8fr_1.2fr] gap-3">
                <Select
                  value={outreachDraft.target_type}
                  onValueChange={(value) =>
                    setOutreachDraft((draft) => ({
                      ...draft,
                      target_type: value === 'group' ? 'group' : 'person',
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="person">个人</SelectItem>
                    <SelectItem value="group">群组</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  value={outreachDraft.target_id}
                  onChange={(event) =>
                    setOutreachDraft((draft) => ({
                      ...draft,
                      target_id: event.target.value,
                    }))
                  }
                  placeholder="目标 ID"
                />
              </div>
              <Input
                value={outreachDraft.bot_uuid}
                onChange={(event) =>
                  setOutreachDraft((draft) => ({
                    ...draft,
                    bot_uuid: event.target.value,
                  }))
                }
                placeholder="机器人 UUID"
              />
              <div className="grid gap-1.5">
                <span className="text-xs font-medium text-slate-500">
                  首次推送时间
                </span>
                <Input
                  type="datetime-local"
                  value={outreachDraft.scheduled_at}
                  onChange={(event) =>
                    setOutreachDraft((draft) => ({
                      ...draft,
                      scheduled_at: event.target.value,
                    }))
                  }
                  aria-label="首次推送时间"
                />
              </div>
              <Input
                type="number"
                min={0}
                value={outreachDraft.interval_minutes}
                onChange={(event) =>
                  setOutreachDraft((draft) => ({
                    ...draft,
                    interval_minutes: Number(event.target.value || 0),
                  }))
                }
                placeholder="循环间隔分钟，0 为一次"
              />
              <Textarea
                value={outreachDraft.message_template}
                onChange={(event) =>
                  setOutreachDraft((draft) => ({
                    ...draft,
                    message_template: event.target.value,
                  }))
                }
                placeholder="推送模板"
                className="min-h-24"
              />
              <Button onClick={createOutreachPlan} disabled={creatingOutreach}>
                <CalendarClock className="size-4" />
                创建计划
              </Button>
            </div>
            <div className="max-h-[230px] divide-y divide-slate-200 overflow-auto border-t border-slate-200">
              {outreachPlans.map((plan) => (
                <div key={plan.id} className="p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-950">
                        {plan.name}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {targetTypeLabel(plan.target_type)} / {plan.target_id}
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className={
                        plan.enabled
                          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                          : 'border-slate-200 bg-slate-50 text-slate-500'
                      }
                    >
                      {plan.enabled ? '启用' : '停用'}
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    下次推送：{formatDate(plan.scheduled_at)}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    上次触达：{formatDate(plan.last_sent_at)}
                  </p>
                </div>
              ))}
              {!outreachPlans.length && (
                <div className="p-6 text-center text-sm text-slate-500">
                  暂无触达计划
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
