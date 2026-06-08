import { useEffect, useState, type ChangeEvent, type ReactNode } from 'react';
import {
  Bot,
  Brain,
  CalendarClock,
  Database,
  Handshake,
  Image as ImageIcon,
  Link2,
  MessageCircleMore,
  MessageSquareText,
  Mic2,
  MousePointerClick,
  Plus,
  Radio,
  RadioTower,
  SendHorizontal,
  ShieldCheck,
  Sparkles,
  Upload,
  UserRound,
  Wrench,
  type LucideIcon,
} from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { SalesProduct } from '@/app/infra/entities/api';
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
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import {
  PipelineTemplateConfig,
  PipelineTemplateImageTextBinding,
} from './types';
import { createTaskAssistantTemplateConfig } from './workflowTemplates';

interface PipelineTemplateConfigEditorProps {
  value?: PipelineTemplateConfig;
  onChange: (value: PipelineTemplateConfig) => void;
}

type TemplateConfigTab =
  | 'basic'
  | 'role'
  | 'model'
  | 'tools'
  | 'knowledge'
  | 'memory'
  | 'radar'
  | 'push'
  | 'media';

const CONFIG_TABS: Array<{
  id: TemplateConfigTab;
  label: string;
  icon: LucideIcon;
}> = [
  { id: 'basic', label: '基本信息', icon: UserRound },
  { id: 'role', label: '角色设定', icon: MessageSquareText },
  { id: 'model', label: '模型能力', icon: Brain },
  { id: 'tools', label: '工具配置', icon: Wrench },
  { id: 'knowledge', label: '知识和数据', icon: Database },
  { id: 'memory', label: '记忆', icon: Bot },
  { id: 'radar', label: '互动雷达', icon: MousePointerClick },
  { id: 'push', label: '定时推送', icon: CalendarClock },
  { id: 'media', label: '图文语音', icon: ImageIcon },
];

function normalizeTemplateConfig(value?: PipelineTemplateConfig): PipelineTemplateConfig {
  const defaults = createTaskAssistantTemplateConfig();
  return {
    ...defaults,
    ...(value || {}),
    tools: {
      ...defaults.tools,
      ...(value?.tools || {}),
    },
    memory: {
      ...defaults.memory,
      ...(value?.memory || {}),
    },
    voice: {
      ...defaults.voice,
      ...(value?.voice || {}),
    },
    scheduled_push: {
      ...defaults.scheduled_push,
      ...(value?.scheduled_push || {}),
    },
    interaction_radar: {
      ...defaults.interaction_radar,
      ...(value?.interaction_radar || {}),
    },
    image_text_bindings:
      value?.image_text_bindings?.length ? value.image_text_bindings : defaults.image_text_bindings,
    sales_links: value?.sales_links?.length ? value.sales_links : defaults.sales_links || [],
    radar: {
      ...(defaults.radar || {
        enabled: false,
        link_title: '',
        link_url: '',
        tracking_fields: [],
        rules: [],
      }),
      ...(value?.radar || {}),
    },
    followup_sequences:
      value?.followup_sequences?.length ? value.followup_sequences : defaults.followup_sequences || [],
    long_term_broadcasts:
      value?.long_term_broadcasts?.length ? value.long_term_broadcasts : defaults.long_term_broadcasts || [],
    stop_rules: {
      ...(defaults.stop_rules || {
        stop_keywords: [],
        stop_tags: [],
        message: '',
      }),
      ...(value?.stop_rules || {}),
    },
  };
}

function Section({
  title,
  description,
  icon: Icon,
  right,
  children,
}: {
  title: string;
  description?: string;
  icon: LucideIcon;
  right?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-md bg-indigo-50 text-indigo-600">
            <Icon className="size-4" />
          </span>
          <div className="min-w-0">
            <h3 className="text-base font-semibold leading-5 text-slate-950">{title}</h3>
            {description && (
              <p className="mt-1 text-sm leading-5 text-muted-foreground">{description}</p>
            )}
          </div>
        </div>
        {right}
      </div>
      <div className="space-y-4 px-5 py-4">{children}</div>
    </section>
  );
}

function FieldLabel({
  children,
  required,
  hint,
}: {
  children: ReactNode;
  required?: boolean;
  hint?: string;
}) {
  return (
    <div className="mb-1.5 flex items-center gap-2 text-sm font-medium text-slate-700">
      <span>
        {children}
        {required && <span className="ml-1 text-red-500">*</span>}
      </span>
      {hint && <span className="text-xs font-normal text-muted-foreground">{hint}</span>}
    </div>
  );
}

function ToggleRow({
  label,
  checked,
  onCheckedChange,
  description,
}: {
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  description?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-slate-200 bg-white px-3 py-2.5 transition-colors hover:border-indigo-200 hover:bg-indigo-50/30">
      <div className="min-w-0">
        <p className="text-sm font-medium text-slate-900">{label}</p>
        {description && (
          <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{description}</p>
        )}
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  );
}

function SummaryPill({
  active,
  children,
}: {
  active: boolean;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium',
        active
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
          : 'border-slate-200 bg-slate-50 text-muted-foreground',
      )}
    >
      {children}
    </span>
  );
}

function imageAssetUrl(fileKey: string) {
  const baseUrl = httpClient.getBaseUrl();
  const prefix = baseUrl === '/' ? '' : baseUrl.replace(/\/$/, '');
  return `${prefix}/api/v1/files/image/${encodeURIComponent(fileKey)}`;
}

function makeCustomImageBinding(): PipelineTemplateImageTextBinding {
  const suffix = Date.now().toString(36);
  return {
    step_id: `custom_${suffix}`,
    title: '新图文步骤',
    text: '',
    file_key: '',
    image_url: '',
    trigger_intents: [],
    enabled: true,
  };
}

function textToList(value: string): string[] {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function PipelineTemplateConfigEditor({
  value,
  onChange,
}: PipelineTemplateConfigEditorProps) {
  const config = normalizeTemplateConfig(value);
  const { knowledgeBases } = useSidebarData();
  const [activeTab, setActiveTab] = useState<TemplateConfigTab>('role');
  const [salesProducts, setSalesProducts] = useState<SalesProduct[]>([]);
  const [uploadingBindingId, setUploadingBindingId] = useState('');

  useEffect(() => {
    httpClient
      .getSalesProducts()
      .then((resp) => setSalesProducts(resp.products || []))
      .catch((error) => console.warn('Failed to load sales products', error));
  }, []);

  function patch(next: Partial<PipelineTemplateConfig>) {
    onChange({ ...config, ...next });
  }

  function patchVoice(next: Partial<PipelineTemplateConfig['voice']>) {
    patch({ voice: { ...config.voice, ...next } });
  }

  function patchScheduledPush(next: Partial<PipelineTemplateConfig['scheduled_push']>) {
    const scheduledPush = { ...config.scheduled_push, ...next };
    if (next.message !== undefined) {
      scheduledPush.push_message = next.message;
    }
    patch({ scheduled_push: scheduledPush });
  }

  function patchInteractionRadar(next: Partial<PipelineTemplateConfig['interaction_radar']>) {
    patch({
      interaction_radar: {
        ...config.interaction_radar,
        ...next,
      },
    });
  }

  function patchRadar(next: Partial<NonNullable<PipelineTemplateConfig['radar']>>) {
    patch({ radar: { ...config.radar!, ...next } });
  }

  function patchStopRules(next: Partial<NonNullable<PipelineTemplateConfig['stop_rules']>>) {
    patch({ stop_rules: { ...config.stop_rules!, ...next } });
  }

  function patchMemory(next: Partial<PipelineTemplateConfig['memory']>) {
    patch({ memory: { ...config.memory, ...next } });
  }

  function patchTool(key: string, enabled: boolean) {
    patch({ tools: { ...config.tools, [key]: enabled } });
  }

  function patchBinding(index: number, next: Partial<PipelineTemplateImageTextBinding>) {
    patch({
      image_text_bindings: config.image_text_bindings.map((binding, bindingIndex) =>
        bindingIndex === index ? { ...binding, ...next } : binding,
      ),
    });
  }

  function toggleTemplateListValue(
    key: 'knowledge_base_uuids' | 'product_uuids',
    value: string,
  ) {
    if (!value) return;
    const current = Array.isArray(config[key]) ? config[key] : [];
    const next = current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value];
    patch({ [key]: next } as Partial<PipelineTemplateConfig>);
  }

  function patchRecommendedQuestions(text: string) {
    patch({
      recommended_questions: text
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean),
    });
  }

  function addImageTextBinding() {
    patch({
      image_text_bindings: [
        ...config.image_text_bindings,
        makeCustomImageBinding(),
      ],
    });
  }

  function addSalesLink() {
    patch({
      sales_links: [
        ...(config.sales_links || []),
        {
          id: `link_${Date.now().toString(36)}`,
          title: '新的报名链接',
          url: 'https://m.yuanfudao.com/primary/templates/package?pageId=6641&solutionId=27246&keyfrom=yfd-qudaohezuo-xiaoxue-9yyy-CPA-yunti9-siyu-yangzy-jiawen&reduceProxy=true',
          description: '',
          radar_enabled: true,
        },
      ],
    });
  }

  function patchSalesLink(index: number, next: Record<string, unknown>) {
    patch({
      sales_links: (config.sales_links || []).map((link, linkIndex) =>
        linkIndex === index ? { ...link, ...next } : link,
      ),
    });
  }

  function addRadarRule() {
    patchRadar({
      rules: [
        ...(config.radar?.rules || []),
        {
          event: 'link_open',
          delay_minutes: 0,
          message: '家长，看您进入报名通道了，支付以后截图发我，我给您登记开课。',
        },
      ],
    });
  }

  function patchRadarRule(index: number, next: Record<string, unknown>) {
    patchRadar({
      rules: (config.radar?.rules || []).map((rule, ruleIndex) =>
        ruleIndex === index ? { ...rule, ...next } : rule,
      ),
    });
  }

  function addFollowupSequence() {
    patch({
      followup_sequences: [
        ...(config.followup_sequences || []),
        {
          stage: 'custom',
          label: '自定义跟进',
          messages: [{ delay_minutes: 5, message: '家长领取到了吗？' }],
        },
      ],
    });
  }

  function patchFollowupSequence(index: number, next: Record<string, unknown>) {
    patch({
      followup_sequences: (config.followup_sequences || []).map((sequence, sequenceIndex) =>
        sequenceIndex === index ? { ...sequence, ...next } : sequence,
      ),
    });
  }

  function addLongTermBroadcast() {
    patch({
      long_term_broadcasts: [
        ...(config.long_term_broadcasts || []),
        {
          day: (config.long_term_broadcasts?.length || 0) + 1,
          title: '新的长期群发',
          time: '10:05',
          message: '',
          image_key: '',
        },
      ],
    });
  }

  function patchLongTermBroadcast(index: number, next: Record<string, unknown>) {
    patch({
      long_term_broadcasts: (config.long_term_broadcasts || []).map((broadcast, broadcastIndex) =>
        broadcastIndex === index ? { ...broadcast, ...next } : broadcast,
      ),
    });
  }

  async function uploadImageForBinding(
    index: number,
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];
    if (!file) return;

    const binding = config.image_text_bindings[index];
    const bindingId = binding?.step_id || `binding-${index}`;
    try {
      setUploadingBindingId(bindingId);
      const result = await httpClient.uploadImage(file);
      patchBinding(index, { file_key: result.file_key, image_url: '' });
      toast.success('图片已上传并绑定');
    } catch (error) {
      console.error('Template image upload failed:', error);
      toast.error('图片上传失败');
    } finally {
      setUploadingBindingId('');
      event.target.value = '';
    }
  }

  const scheduledMessage =
    config.scheduled_push.message || config.scheduled_push.push_message || '';
  const enabledToolCount = Object.values(config.tools).filter(Boolean).length;
  const enabledImageBindings = config.image_text_bindings.filter(
    (binding) => binding.enabled !== false,
  );

  function renderBasicInfo() {
    return (
      <Section
        icon={UserRound}
        title="基本信息"
        description="设置业务团队看到的数字员工名称、开场话术和常用引导问题。"
      >
        <div className="grid gap-4 md:grid-cols-2">
          <label>
            <FieldLabel required>数字员工名称</FieldLabel>
            <Input
              value={config.name}
              onChange={(event) => patch({ name: event.target.value })}
              className="h-11"
              maxLength={30}
              placeholder="例如：课程顾问"
            />
          </label>
          <label>
            <FieldLabel>默认模型</FieldLabel>
            <Input
              value={config.model_uuid}
              onChange={(event) => patch({ model_uuid: event.target.value })}
              className="h-11"
              placeholder="模型 UUID"
            />
          </label>
        </div>
        <label className="block">
          <FieldLabel hint="用户加好友/首次进线先发这段文字；资源卡片单独通过报名链接里的图书配套学习资源卡片发送。">首次开场白</FieldLabel>
          <Textarea
            value={config.opening_message}
            onChange={(event) => patch({ opening_message: event.target.value })}
            className="min-h-36 resize-none leading-6"
            placeholder="请输入首次开场白"
          />
        </label>
        <label className="block">
          <FieldLabel hint="每行一个问题">推荐问题</FieldLabel>
          <Textarea
            value={config.recommended_questions.join('\n')}
            onChange={(event) => patchRecommendedQuestions(event.target.value)}
            className="min-h-28 resize-none leading-6"
            placeholder={'我应该怎么完成这个任务？\n我卡在这一步了怎么办？'}
          />
        </label>
      </Section>
    );
  }

  function renderRoleSettings() {
    return (
      <Section
        icon={MessageSquareText}
        title="角色设定"
        description="定义数字员工的人设、说话边界和业务执行规则。"
        right={<Badge variant="secondary" className="rounded-md">核心配置</Badge>}
      >
        <label className="block">
          <FieldLabel required>角色自定义提示</FieldLabel>
          <Textarea
            value={config.role_prompt}
            onChange={(event) => patch({ role_prompt: event.target.value })}
            className="min-h-[420px] resize-none rounded-md bg-slate-50/70 text-sm leading-7 shadow-none focus-visible:bg-white"
            placeholder="请输入角色指令"
          />
        </label>
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-muted-foreground">
          <span>可在提示词中引入：</span>
          <Badge variant="outline" className="rounded bg-white">@ 工具</Badge>
          <Badge variant="outline" className="rounded bg-white">{'{变量值}'}</Badge>
          <Badge variant="outline" className="rounded bg-white">知识库结果</Badge>
        </div>
      </Section>
    );
  }

  function renderModelSettings() {
    return (
      <Section
        icon={Brain}
        title="模型能力"
        description="控制模型、思考次数和上下文参考范围。"
      >
        <label className="block">
          <FieldLabel required>模型</FieldLabel>
          <Input
            value={config.model_uuid}
            onChange={(event) => patch({ model_uuid: event.target.value })}
            className="h-11"
            placeholder="模型 UUID"
          />
        </label>
        <div className="grid gap-4 md:grid-cols-2">
          <label>
            <FieldLabel>最大思考次数</FieldLabel>
            <Input
              type="number"
              min={1}
              max={12}
              value={config.max_reasoning_steps}
              onChange={(event) => patch({ max_reasoning_steps: Number(event.target.value || 1) })}
              className="h-11"
            />
          </label>
          <label>
            <FieldLabel>参考对话轮数</FieldLabel>
            <Input
              type="number"
              min={1}
              max={20}
              value={config.reference_rounds}
              onChange={(event) => patch({ reference_rounds: Number(event.target.value || 1) })}
              className="h-11"
            />
          </label>
        </div>
      </Section>
    );
  }

  function renderToolSettings() {
    return (
      <Section
        icon={Wrench}
        title="工具配置"
        description="开启后，数字员工可以在对话中调用对应能力。"
        right={<Badge variant="outline" className="rounded-md">{enabledToolCount} 项已开启</Badge>}
      >
        <div className="grid gap-3 md:grid-cols-2">
          {[
            ['intent_recognition', '意图识别', '识别咨询、报价、售后、截图等客户意图。'],
            ['knowledge_base', '知识库', '从企业知识库中检索回答依据。'],
            ['product_database', '产品数据库', '结合产品信息推荐课程、服务或方案。'],
            ['image_recognition', '截图识别', '识别用户截图，并判断卡在哪一步。'],
            ['voice_reply', '语音回复（课程销售请关闭）', '将关键回复转换成语音消息。'],
          ].map(([key, label, description]) => (
            <ToggleRow
              key={key}
              label={label}
              description={description}
              checked={Boolean(config.tools[key])}
              onCheckedChange={(checked) => patchTool(key, checked)}
            />
          ))}
        </div>
      </Section>
    );
  }

  function renderKnowledgeSettings() {
    return (
      <Section
        icon={Database}
        title="知识和数据"
        description="配置知识库与产品库，让业务人员不用接触低代码节点。"
      >
        <div className="grid gap-3 md:grid-cols-2">
          <ToggleRow
            label="启用知识库"
            description="客户问到文档、规则、流程时优先检索资料。"
            checked={Boolean(config.tools.knowledge_base)}
            onCheckedChange={(checked) => patchTool('knowledge_base', checked)}
          />
          <ToggleRow
            label="启用产品数据库"
            description="客户问课程、价格、权益时引用产品资料。"
            checked={Boolean(config.tools.product_database)}
            onCheckedChange={(checked) => patchTool('product_database', checked)}
          />
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-md border border-slate-200 bg-slate-50/70 p-4">
            <div className="mb-3 flex items-center justify-between">
              <FieldLabel>关联知识库</FieldLabel>
              <Badge variant="outline" className="rounded bg-white">
                {config.knowledge_base_uuids.length} 个已选
              </Badge>
            </div>
            <div className="grid gap-2">
              {knowledgeBases.map((kb) => (
                <button
                  key={kb.id}
                  type="button"
                  onClick={() =>
                    toggleTemplateListValue('knowledge_base_uuids', kb.id)
                  }
                  className={cn(
                    'flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors',
                    config.knowledge_base_uuids.includes(kb.id)
                      ? 'border-indigo-300 bg-indigo-50 text-indigo-950'
                      : 'border-slate-200 bg-white hover:bg-slate-50',
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate">{kb.name}</span>
                    {kb.description && (
                      <span className="block truncate text-xs text-muted-foreground">
                        {kb.description}
                      </span>
                    )}
                  </span>
                  {config.knowledge_base_uuids.includes(kb.id) && (
                    <Badge className="rounded">已选</Badge>
                  )}
                </button>
              ))}
              {!knowledgeBases.length && (
                <div className="rounded-md border border-dashed border-slate-300 bg-white p-4 text-sm text-muted-foreground">
                  暂无知识库，请先在左侧知识库中创建
                </div>
              )}
            </div>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50/70 p-4">
            <div className="mb-3 flex items-center justify-between">
              <FieldLabel>关联产品</FieldLabel>
              <Badge variant="outline" className="rounded bg-white">
                {config.product_uuids.length} 个已选
              </Badge>
            </div>
            <div className="grid gap-2">
              {salesProducts.map((product) => (
                <button
                  key={product.uuid}
                  type="button"
                  onClick={() =>
                    toggleTemplateListValue('product_uuids', product.uuid || '')
                  }
                  className={cn(
                    'flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors',
                    config.product_uuids.includes(product.uuid || '')
                      ? 'border-indigo-300 bg-indigo-50 text-indigo-950'
                      : 'border-slate-200 bg-white hover:bg-slate-50',
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate">{product.name}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {product.price || product.category || product.description}
                    </span>
                  </span>
                  {config.product_uuids.includes(product.uuid || '') && (
                    <Badge className="rounded">已选</Badge>
                  )}
                </button>
              ))}
              {!salesProducts.length && (
                <div className="rounded-md border border-dashed border-slate-300 bg-white p-4 text-sm text-muted-foreground">
                  暂无产品，请先在销售工作台中创建
                </div>
              )}
            </div>
          </div>
        </div>
      </Section>
    );
  }

  function renderMemorySettings() {
    return (
      <Section
        icon={Bot}
        title="记忆"
        description="记录客户偏好、阶段和长期上下文，让数字员工越聊越懂客户。"
      >
        <div className="grid gap-3">
          {[
            ['variables_enabled', '记忆变量', '记录聊天对话中的一维、单个的应用信息或用户信息。'],
            ['table_enabled', '记忆表', '记录聊天对话中的多维、大量的应用信息或用户信息。'],
            ['segments_enabled', '记忆片段', '记录用户偏好、计划和长期上下文。'],
          ].map(([key, label, description]) => (
            <ToggleRow
              key={key}
              label={label}
              description={description}
              checked={Boolean(config.memory[key as keyof typeof config.memory])}
              onCheckedChange={(checked) =>
                patchMemory({
                  [key]: checked,
                } as Partial<PipelineTemplateConfig['memory']>)
              }
            />
          ))}
        </div>
      </Section>
    );
  }

  function renderRadarSettings() {
    return (
      <div className="space-y-4">
        <Section
          icon={MousePointerClick}
          title="互动雷达"
          description="配置数字员工主动发送的雷达链接，以及用户点击后的自动回复。"
          right={
            <SummaryPill active={config.interaction_radar.enabled}>
              {config.interaction_radar.enabled ? '已启用' : '未启用'}
            </SummaryPill>
          }
        >
          <ToggleRow
            label="启用互动雷达"
            description="用户点击链接后，数字员工自动感知并回复。"
            checked={config.interaction_radar.enabled}
            onCheckedChange={(checked) =>
              patchInteractionRadar({ enabled: checked })
            }
          />
          <label className="block">
            <FieldLabel required>雷达链接</FieldLabel>
            <Input
              type="url"
              value={config.interaction_radar.link_url}
              onChange={(event) =>
                patchInteractionRadar({ link_url: event.target.value })
              }
              className="h-11"
              placeholder="https://example.com/course"
            />
          </label>
          <label className="block">
            <FieldLabel required>点击后 AI 行为回复</FieldLabel>
            <Textarea
              value={config.interaction_radar.click_reply}
              onChange={(event) =>
                patchInteractionRadar({ click_reply: event.target.value })
              }
              className="min-h-32 resize-none leading-6"
              placeholder="我看到您刚刚点开了链接，如果有问题可以直接问我。"
            />
          </label>
        </Section>

        <Section
          icon={Link2}
          title="报名链接"
          description="可配置普通链接或带雷达参数的假链接，发送后由雷达规则继续跟进。"
          right={
            <Badge variant="outline" className="rounded-md">
              {(config.sales_links || []).length} 个链接
            </Badge>
          }
        >
          <Button type="button" variant="outline" className="h-10 w-full justify-center rounded-md" onClick={addSalesLink}>
            <Plus className="mr-1.5 size-4" />
            新增报名链接
          </Button>
          <div className="grid gap-3">
            {(config.sales_links || []).map((link, index) => (
              <div key={link.id || index} className="space-y-3 rounded-md border border-slate-200 bg-slate-50/70 p-3">
                <div className="flex items-center gap-3">
                  <Input
                    value={link.title}
                    onChange={(event) => patchSalesLink(index, { title: event.target.value })}
                    className="h-10 bg-white"
                    placeholder="链接标题"
                  />
                  <Switch
                    checked={link.radar_enabled !== false}
                    onCheckedChange={(checked) => patchSalesLink(index, { radar_enabled: checked })}
                  />
                </div>
                <Input
                  value={link.url}
                  onChange={(event) => patchSalesLink(index, { url: event.target.value })}
                  className="h-10 bg-white"
                  placeholder="https://m.yuanfudao.com/primary/templates/package?pageId=6641&solutionId=27246&keyfrom=yfd-qudaohezuo-xiaoxue-9yyy-CPA-yunti9-siyu-yangzy-jiawen&reduceProxy=true"
                />
                <Textarea
                  value={link.description || ''}
                  onChange={(event) => patchSalesLink(index, { description: event.target.value })}
                  className="min-h-20 resize-none bg-white leading-6"
                  placeholder="链接用途说明"
                />
              </div>
            ))}
          </div>
        </Section>

        <Section
          icon={RadioTower}
          title="模拟雷达"
          description="模拟用户点击链接、浏览时长、点击报名按钮和点击后未支付等事件。"
          right={
            <SummaryPill active={config.radar?.enabled !== false}>
              {config.radar?.enabled !== false ? '已启用' : '未启用'}
            </SummaryPill>
          }
        >
          <ToggleRow
            label="启用模拟雷达"
            description="根据配置的事件规则自动触发跟进消息。"
            checked={config.radar?.enabled !== false}
            onCheckedChange={(checked) => patchRadar({ enabled: checked })}
          />
          <div className="grid gap-4 md:grid-cols-2">
            <label>
              <FieldLabel>雷达链接标题</FieldLabel>
              <Input
                value={config.radar?.link_title || ''}
                onChange={(event) => patchRadar({ link_title: event.target.value })}
                className="h-11"
                placeholder="雷达链接标题"
              />
            </label>
            <label>
              <FieldLabel>雷达链接 URL</FieldLabel>
              <Input
                value={config.radar?.link_url || ''}
                onChange={(event) => patchRadar({ link_url: event.target.value })}
                className="h-11"
                placeholder="雷达链接 URL"
              />
            </label>
          </div>
          <label className="block">
            <FieldLabel hint="可用换行、逗号或顿号分隔">追踪字段</FieldLabel>
            <Input
              value={(config.radar?.tracking_fields || []).join('，')}
              onChange={(event) => patchRadar({ tracking_fields: textToList(event.target.value) })}
              className="h-11"
              placeholder="追踪字段"
            />
          </label>
          <Button type="button" variant="outline" className="h-10 w-full justify-center rounded-md" onClick={addRadarRule}>
            <Plus className="mr-1.5 size-4" />
            新增雷达规则
          </Button>
          <div className="grid gap-3">
            {(config.radar?.rules || []).map((rule, index) => (
              <div key={`${rule.event}-${index}`} className="space-y-3 rounded-md border border-slate-200 bg-slate-50/70 p-3">
                <div className="grid gap-3 md:grid-cols-3">
                  <Input
                    value={rule.event}
                    onChange={(event) => patchRadarRule(index, { event: event.target.value })}
                    className="h-10 bg-white"
                    placeholder="事件，如 browse_30s"
                  />
                  <Input
                    type="number"
                    min={0}
                    value={rule.delay_minutes}
                    onChange={(event) =>
                      patchRadarRule(index, { delay_minutes: Number(event.target.value || 0) })
                    }
                    className="h-10 bg-white"
                    placeholder="延迟分钟"
                  />
                  <Input
                    type="number"
                    min={0}
                    value={rule.min_browse_seconds || 0}
                    onChange={(event) =>
                      patchRadarRule(index, { min_browse_seconds: Number(event.target.value || 0) })
                    }
                    className="h-10 bg-white"
                    placeholder="最少浏览秒数"
                  />
                </div>
                <Textarea
                  value={rule.message}
                  onChange={(event) => patchRadarRule(index, { message: event.target.value })}
                  className="min-h-24 resize-none bg-white leading-6"
                  placeholder="触发后发送的消息"
                />
              </div>
            ))}
          </div>
        </Section>
      </div>
    );
  }

  function renderPushSettings() {
    return (
      <div className="space-y-4">
        <Section
          icon={CalendarClock}
          title="定时推送"
          description="设置数字员工定时提醒客户继续完成任务或查看资料。"
          right={
            <SummaryPill active={config.scheduled_push.enabled}>
              {config.scheduled_push.enabled ? '已启用' : '未启用'}
            </SummaryPill>
          }
        >
          <ToggleRow
            label="启用定时推送"
            description="按指定时间主动发送消息。"
            checked={config.scheduled_push.enabled}
            onCheckedChange={(checked) => patchScheduledPush({ enabled: checked })}
          />
          <div className="grid gap-4 md:grid-cols-2">
            <label>
              <FieldLabel>推送方式</FieldLabel>
              <Select
                value={config.scheduled_push.mode}
                onValueChange={(mode) =>
                  patchScheduledPush({ mode: mode as 'daily' | 'single_day' })
                }
              >
                <SelectTrigger className="h-11 w-full bg-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">每天推送</SelectItem>
                  <SelectItem value="single_day">指定单天</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <label>
              <FieldLabel>推送时间</FieldLabel>
              <Input
                type="time"
                value={config.scheduled_push.time}
                onChange={(event) => patchScheduledPush({ time: event.target.value })}
                className="h-11"
              />
            </label>
          </div>
          {config.scheduled_push.mode === 'single_day' && (
            <label className="block">
              <FieldLabel>指定日期</FieldLabel>
              <Input
                type="date"
                value={config.scheduled_push.single_date}
                onChange={(event) => patchScheduledPush({ single_date: event.target.value })}
                className="h-11"
              />
            </label>
          )}
          <label className="block">
            <FieldLabel>推送消息</FieldLabel>
            <Textarea
              value={scheduledMessage}
              onChange={(event) => patchScheduledPush({ message: event.target.value })}
              className="min-h-32 resize-none leading-6"
              placeholder="请输入定时推送的消息"
            />
          </label>
        </Section>

        <Section icon={MessageSquareText} title="主动跟进话术矩阵">
          <Button type="button" variant="outline" className="h-10 w-full justify-center rounded-md" onClick={addFollowupSequence}>
            <Plus className="mr-1.5 size-4" />
            新增跟进场景
          </Button>
          <div className="grid gap-3">
            {(config.followup_sequences || []).map((sequence, index) => (
              <div key={`${sequence.stage}-${index}`} className="space-y-3 rounded-md border border-slate-200 bg-slate-50/70 p-3">
                <div className="grid gap-3 md:grid-cols-2">
                  <Input
                    value={sequence.label}
                    onChange={(event) => patchFollowupSequence(index, { label: event.target.value })}
                    className="h-10 bg-white"
                    placeholder="场景名称"
                  />
                  <Input
                    value={sequence.stage}
                    onChange={(event) => patchFollowupSequence(index, { stage: event.target.value })}
                    className="h-10 bg-white"
                    placeholder="阶段标识"
                  />
                </div>
                <Textarea
                  value={JSON.stringify(sequence.messages, null, 2)}
                  onChange={(event) => {
                    try {
                      patchFollowupSequence(index, { messages: JSON.parse(event.target.value) });
                    } catch {
                      patchFollowupSequence(index, { messages_text: event.target.value });
                    }
                  }}
                  className="min-h-28 font-mono text-xs leading-5"
                  placeholder="跟进消息 JSON"
                />
              </div>
            ))}
          </div>
        </Section>

        <Section icon={CalendarClock} title="长期群发">
          <Button type="button" variant="outline" className="h-10 w-full justify-center rounded-md" onClick={addLongTermBroadcast}>
            <Plus className="mr-1.5 size-4" />
            新增长期群发
          </Button>
          <div className="grid gap-3">
            {(config.long_term_broadcasts || []).map((broadcast, index) => (
              <div key={`${broadcast.day}-${index}`} className="space-y-3 rounded-md border border-slate-200 bg-slate-50/70 p-3">
                <div className="grid gap-3 md:grid-cols-[100px_minmax(0,1fr)_120px]">
                  <Input
                    type="number"
                    min={1}
                    value={broadcast.day}
                    onChange={(event) => patchLongTermBroadcast(index, { day: Number(event.target.value || 1) })}
                    className="h-10 bg-white"
                  />
                  <Input
                    value={broadcast.title}
                    onChange={(event) => patchLongTermBroadcast(index, { title: event.target.value })}
                    className="h-10 bg-white"
                    placeholder="标题"
                  />
                  <Input
                    type="time"
                    value={broadcast.time}
                    onChange={(event) => patchLongTermBroadcast(index, { time: event.target.value })}
                    className="h-10 bg-white"
                  />
                </div>
                <Textarea
                  value={broadcast.message}
                  onChange={(event) => patchLongTermBroadcast(index, { message: event.target.value })}
                  className="min-h-24 resize-none bg-white leading-6"
                  placeholder="群发消息"
                />
                <Input
                  value={broadcast.image_key || ''}
                  onChange={(event) => patchLongTermBroadcast(index, { image_key: event.target.value })}
                  className="h-10 bg-white"
                  placeholder="图片 file_key"
                />
              </div>
            ))}
          </div>
        </Section>

        <Section
          icon={ShieldCheck}
          title="停发规则"
          description="命中拒绝、投诉、已报名、人工接管等状态后停止营销触达。"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <label>
              <FieldLabel hint="每行一个">停发关键词</FieldLabel>
              <Textarea
                value={(config.stop_rules?.stop_keywords || []).join('\n')}
                onChange={(event) => patchStopRules({ stop_keywords: textToList(event.target.value) })}
                className="min-h-28 resize-none leading-6"
                placeholder="停发关键词"
              />
            </label>
            <label>
              <FieldLabel hint="每行一个">停发标签</FieldLabel>
              <Textarea
                value={(config.stop_rules?.stop_tags || []).join('\n')}
                onChange={(event) => patchStopRules({ stop_tags: textToList(event.target.value) })}
                className="min-h-28 resize-none leading-6"
                placeholder="停发标签"
              />
            </label>
          </div>
          <label className="block">
            <FieldLabel>停发确认话术</FieldLabel>
            <Textarea
              value={config.stop_rules?.message || ''}
              onChange={(event) => patchStopRules({ message: event.target.value })}
              className="min-h-20 resize-none leading-6"
              placeholder="停发确认话术"
            />
          </label>
        </Section>
      </div>
    );
  }

  function renderMediaSettings() {
    return (
      <div className="space-y-4">
        <Section
          icon={ImageIcon}
          title="图片文字绑定"
          description="按任务步骤绑定图片、说明文字和触发意图。"
          right={<Badge variant="outline" className="rounded-md">{enabledImageBindings.length} 步启用</Badge>}
        >
          <Button
            type="button"
            variant="outline"
            className="h-10 w-full justify-center rounded-md"
            onClick={addImageTextBinding}
          >
            <Plus className="mr-1.5 size-4" />
            新增图文绑定
          </Button>
          <div className="grid gap-3">
            {config.image_text_bindings.map((binding, index) => (
              <div key={binding.step_id || index} className="rounded-md border border-slate-200 bg-slate-50/70 p-3">
                <div className="mb-3 flex items-center gap-3">
                  <Badge variant="outline" className="rounded bg-white">
                    {String(index + 1).padStart(2, '0')}
                  </Badge>
                  <Input
                    value={binding.title}
                    onChange={(event) => patchBinding(index, { title: event.target.value })}
                    className="h-10 bg-white"
                    placeholder="步骤标题"
                  />
                  <Switch
                    checked={binding.enabled !== false}
                    onCheckedChange={(checked) => patchBinding(index, { enabled: checked })}
                  />
                </div>
                <Textarea
                  value={binding.text}
                  onChange={(event) => patchBinding(index, { text: event.target.value })}
                  className="mb-3 min-h-20 resize-none bg-white leading-6"
                  placeholder="步骤说明"
                />
                <input
                  id={`template-image-${binding.step_id || index}`}
                  className="hidden"
                  type="file"
                  accept="image/*"
                  onChange={(event) => uploadImageForBinding(index, event)}
                />
                <div className="mb-3 grid gap-2 md:grid-cols-[auto_minmax(0,1fr)]">
                  <Button
                    type="button"
                    variant="outline"
                    className="h-10 rounded-md bg-white"
                    disabled={
                      uploadingBindingId === (binding.step_id || `binding-${index}`)
                    }
                    onClick={() =>
                      document
                        .getElementById(`template-image-${binding.step_id || index}`)
                        ?.click()
                    }
                  >
                    <Upload className="mr-1.5 size-4" />
                    {uploadingBindingId === (binding.step_id || `binding-${index}`)
                      ? '上传中'
                      : '上传图片'}
                  </Button>
                  <Input
                    value={binding.image_url || ''}
                    onChange={(event) =>
                      patchBinding(index, { image_url: event.target.value })
                    }
                    className="h-10 bg-white"
                    placeholder="图片 URL（可选）"
                  />
                </div>
                {(binding.image_url || binding.file_key) && (
                  <div className="mb-3 overflow-hidden rounded-md border bg-white">
                    <img
                      src={binding.image_url || imageAssetUrl(binding.file_key)}
                      alt={binding.title}
                      className="max-h-40 w-full object-contain"
                    />
                  </div>
                )}
                <Input
                  value={binding.file_key}
                  onChange={(event) => patchBinding(index, { file_key: event.target.value })}
                  className="h-10 bg-white"
                  placeholder="图片 file_key 或上传后的素材路径"
                />
              </div>
            ))}
          </div>
        </Section>

        <Section
          icon={Mic2}
          title="声音和形象"
          description="控制语音回复开关、音色和输出编码。"
          right={
            <SummaryPill active={config.voice.enabled}>
              {config.voice.enabled ? '语音已启用' : '语音未启用'}
            </SummaryPill>
          }
        >
          <ToggleRow
            label="语音回复"
            description="开启后，数字员工可把关键回复转换成语音。"
            checked={config.voice.enabled}
            onCheckedChange={(checked) => patchVoice({ enabled: checked })}
          />
          <div className="grid gap-4 md:grid-cols-3">
            <label>
              <FieldLabel>语音服务</FieldLabel>
              <Input
                value={config.voice.provider}
                onChange={(event) => patchVoice({ provider: event.target.value })}
                className="h-11"
                placeholder="provider"
              />
            </label>
            <label>
              <FieldLabel>音色 ID</FieldLabel>
              <Input
                value={config.voice.voice_type}
                onChange={(event) => patchVoice({ voice_type: event.target.value })}
                className="h-11"
                placeholder="音色ID"
              />
            </label>
            <label>
              <FieldLabel>音频编码</FieldLabel>
              <Input
                value={config.voice.encoding}
                onChange={(event) => patchVoice({ encoding: event.target.value })}
                className="h-11"
                placeholder="音频编码"
              />
            </label>
          </div>
        </Section>
      </div>
    );
  }

  function renderActivePanel() {
    switch (activeTab) {
      case 'basic':
        return renderBasicInfo();
      case 'role':
        return renderRoleSettings();
      case 'model':
        return renderModelSettings();
      case 'tools':
        return renderToolSettings();
      case 'knowledge':
        return renderKnowledgeSettings();
      case 'memory':
        return renderMemorySettings();
      case 'radar':
        return renderRadarSettings();
      case 'push':
        return renderPushSettings();
      case 'media':
        return renderMediaSettings();
      default:
        return renderRoleSettings();
    }
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="grid min-h-[720px] grid-cols-1 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div className="min-w-0 border-r border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-5 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold tracking-normal text-slate-950">Agent配置</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  用表单方式配置数字员工，适合业务团队快速上手。
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <SummaryPill active>{enabledToolCount} 个工具</SummaryPill>
                <SummaryPill active={config.interaction_radar.enabled}>互动雷达</SummaryPill>
                <SummaryPill active={config.scheduled_push.enabled}>定时推送</SummaryPill>
              </div>
            </div>
            <div className="mt-4 overflow-x-auto rounded-md border border-slate-200 bg-slate-50 p-1">
              <div className="flex min-w-max gap-1">
                {CONFIG_TABS.map((tab) => {
                  const Icon = tab.icon;
                  const active = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveTab(tab.id)}
                      className={cn(
                        'inline-flex h-9 items-center gap-1.5 rounded px-3 text-sm font-medium transition-colors',
                        active
                          ? 'bg-indigo-100 text-indigo-700 shadow-sm'
                          : 'text-slate-600 hover:bg-white hover:text-slate-950',
                      )}
                    >
                      <Icon className="size-4" />
                      {tab.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="space-y-4 bg-slate-50/60 p-5">
            {renderActivePanel()}
          </div>
        </div>

        <aside className="flex min-h-0 min-w-0 flex-col bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div>
              <h2 className="text-base font-semibold text-slate-950">预览调试</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                模拟客户看到的开场、雷达与回复效果
              </p>
            </div>
            <span className="grid size-9 place-items-center rounded-md border border-slate-200 bg-white text-slate-600">
              <Sparkles className="size-4" />
            </span>
          </div>

          <div className="flex min-h-0 flex-1 flex-col bg-slate-50/70 p-5">
            <div className="mb-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <span className="grid size-11 shrink-0 place-items-center rounded-md bg-gradient-to-br from-indigo-500 to-sky-400 text-white shadow-sm">
                  <Bot className="size-5" />
                </span>
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-slate-950">
                    {config.name || '未命名数字员工'}
                  </h3>
                  <p className="text-xs text-emerald-600">在线 · 可调试</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <SummaryPill active={config.tools.intent_recognition}>意图识别</SummaryPill>
                <SummaryPill active={config.tools.knowledge_base}>知识库</SummaryPill>
                <SummaryPill active={config.tools.image_recognition}>截图识别</SummaryPill>
                <SummaryPill active={config.voice.enabled}>语音</SummaryPill>
              </div>
            </div>

            <div className="min-h-[460px] flex-1 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <div className="space-y-4">
                <div className="flex gap-3">
                  <span className="grid size-8 shrink-0 place-items-center rounded-md bg-indigo-50 text-indigo-600">
                    <Bot className="size-4" />
                  </span>
                  <div className="max-w-[82%] rounded-lg rounded-tl-sm bg-slate-100 px-4 py-3 text-sm leading-6 text-slate-800">
                    {config.opening_message || '您好，我是您的数字员工，可以帮您介绍课程、解答问题。'}
                  </div>
                </div>

                {config.recommended_questions.length > 0 && (
                  <div className="ml-11 flex flex-wrap gap-2">
                    {config.recommended_questions.map((question) => (
                      <Badge
                        key={question}
                        variant="outline"
                        className="max-w-[230px] truncate rounded-md border-indigo-100 bg-indigo-50 text-indigo-700"
                      >
                        {question}
                      </Badge>
                    ))}
                  </div>
                )}

                {config.interaction_radar.enabled && config.interaction_radar.link_url && (
                  <>
                    <div className="ml-11 rounded-lg border border-indigo-100 bg-indigo-50/80 p-3 text-left">
                      <div className="flex items-center gap-2 text-xs font-medium text-indigo-700">
                        <MousePointerClick className="size-3.5" />
                        互动雷达链接
                      </div>
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {config.interaction_radar.link_url}
                      </p>
                    </div>
                    <div className="flex justify-end">
                      <div className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white">
                        客户已点击链接
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <span className="grid size-8 shrink-0 place-items-center rounded-md bg-indigo-50 text-indigo-600">
                        <Radio className="size-4" />
                      </span>
                      <div className="max-w-[82%] rounded-lg rounded-tl-sm bg-slate-100 px-4 py-3 text-sm leading-6 text-slate-800">
                        {config.interaction_radar.click_reply}
                      </div>
                    </div>
                  </>
                )}

                {enabledImageBindings[0] && (
                  <div className="ml-11 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
                    <div className="flex items-center gap-2 text-xs font-medium text-slate-700">
                      <ImageIcon className="size-3.5" />
                      {enabledImageBindings[0].title}
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                      {enabledImageBindings[0].text}
                    </p>
                  </div>
                )}
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-slate-200 bg-white p-2 shadow-sm">
              <div className="flex items-center gap-2 rounded-md bg-slate-50 px-3 py-2.5">
                <span className="flex-1 truncate text-left text-sm text-muted-foreground">
                  在此提问，测试基于配置的回答效果
                </span>
                <Mic2 className={cn('size-4 shrink-0', config.voice.enabled ? 'text-indigo-600' : 'text-muted-foreground')} />
                <Button type="button" size="sm" className="h-8 rounded-md px-3">
                  <SendHorizontal className="mr-1.5 size-3.5" />
                  发送
                </Button>
              </div>
            </div>

            <div className="mt-4 grid gap-2 text-xs text-muted-foreground">
              <div className="flex items-center gap-2">
                <Handshake className="size-3.5" />
                <span>转人工、群聊回复等复杂能力可在工作流编排中继续扩展。</span>
              </div>
              <div className="flex items-center gap-2">
                <MessageCircleMore className="size-3.5" />
                <span>这里展示Agent配置的实时效果，页面右上角保存后生效。</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
