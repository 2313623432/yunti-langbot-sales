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
  RadioTower,
  SendHorizontal,
  ShieldCheck,
  Trash2,
  Upload,
  UserRound,
  Wrench,
  type LucideIcon,
} from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { LLMModel, SalesProduct } from '@/app/infra/entities/api';
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
import AgentAvatarPicker from '@/app/home/pipelines/components/agent-avatar/AgentAvatarPicker';
import { agentAvatarUrl } from '@/app/home/pipelines/components/agent-avatar/agentAvatar';
import {
  PipelineTemplateConfig,
  PipelineTemplateImageTextBinding,
} from './types';
import { createBlankAgentTemplateConfig } from './workflowTemplates';

interface PipelineTemplateConfigEditorProps {
  value?: PipelineTemplateConfig;
  onChange: (value: PipelineTemplateConfig) => void;
  pipelineName?: string;
  pipelineDescription?: string;
  pipelineAvatar?: string;
  onPipelineNameChange?: (value: string) => void;
  onPipelineDescriptionChange?: (value: string) => void;
  onPipelineAvatarChange?: (value: string) => void;
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
  { id: 'radar', label: '雷达跟进', icon: MousePointerClick },
  { id: 'push', label: '定时推送', icon: CalendarClock },
  { id: 'media', label: '图文素材', icon: ImageIcon },
];

const RADAR_EVENT_OPTIONS = [
  { value: 'link_open', label: '客户打开链接', description: '客户点开报名页后，马上轻量追问。' },
  { value: 'browse_30s', label: '客户浏览了一会儿', description: '客户停留一段时间后，主动询问卡点。' },
  { value: 'click_apply_button', label: '客户点击报名按钮', description: '客户进入报名动作后，提醒完成支付并发截图。' },
  { value: 'no_payment_after_click', label: '点击后暂未支付', description: '客户点了报名但没有支付时，提醒截图或帮看页面。' },
];

type VoiceToneOption = {
  value: string;
  label: string;
};

function radarEventOption(event?: string) {
  const value = String(event || '');
  return RADAR_EVENT_OPTIONS.find((option) => option.value === value) || {
    value,
    label: value || '自定义客户动作',
    description: '自定义工作流事件。',
  };
}

function modelExtraArgs(model?: LLMModel): Record<string, unknown> {
  const extraArgs = model?.extra_args;
  if (!extraArgs || typeof extraArgs !== 'object' || Array.isArray(extraArgs)) {
    return {};
  }
  return extraArgs as Record<string, unknown>;
}

function stringExtraArg(extraArgs: Record<string, unknown>, key: string): string {
  const value = extraArgs[key];
  return typeof value === 'string' ? value : '';
}

function voiceToneOptionsFromModel(model?: LLMModel): VoiceToneOption[] {
  const extraArgs = modelExtraArgs(model);
  const rawVoices = extraArgs.voices;
  const voices = Array.isArray(rawVoices) ? rawVoices : [];
  const options = voices
    .map((voice): VoiceToneOption | null => {
      if (typeof voice === 'string') {
        return { value: voice, label: voice };
      }
      if (!voice || typeof voice !== 'object' || Array.isArray(voice)) {
        return null;
      }
      const item = voice as Record<string, unknown>;
      const value = String(item.value || item.id || item.voice_type || '');
      if (!value) {
        return null;
      }
      return {
        value,
        label: String(item.label || item.name || value),
      };
    })
    .filter((option): option is VoiceToneOption => Boolean(option));

  const defaultVoiceType =
    stringExtraArg(extraArgs, 'voice_type') ||
    stringExtraArg(extraArgs, 'default_voice_type');
  if (
    defaultVoiceType &&
    !options.some((option) => option.value === defaultVoiceType)
  ) {
    options.unshift({ value: defaultVoiceType, label: defaultVoiceType });
  }
  return options;
}

function normalizeTemplateConfig(value?: PipelineTemplateConfig): PipelineTemplateConfig {
  const defaults = createBlankAgentTemplateConfig();
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
    course_profiles:
      value?.course_profiles?.length ? value.course_profiles : defaults.course_profiles || [],
    source_materials:
      value?.source_materials?.length ? value.source_materials : defaults.source_materials || [],
    stop_rules: {
      ...(defaults.stop_rules || {
        stop_keywords: [],
        stop_tags: [],
        message: '',
      }),
      ...(value?.stop_rules || {}),
    },
    stop_policy: {
      ...(defaults.stop_policy || {
        explicit_rejection_threshold: 1,
        explicit_rejection_keywords: [],
        immediate_stop_keywords: [],
      }),
      ...(value?.stop_policy || {}),
    },
  };
}

function Section({
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
      <div className="space-y-4 px-5 py-4">{children}</div>
    </section>
  );
}

function FieldLabel({
  children,
  required,
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
    </div>
  );
}

function ToggleRow({
  label,
  checked,
  onCheckedChange,
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
  const encodedKey = fileKey.split('/').map(encodeURIComponent).join('/');
  return `${prefix}/api/v1/files/image/${encodedKey}`;
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
  pipelineName,
  pipelineDescription,
  pipelineAvatar,
  onPipelineNameChange,
  onPipelineDescriptionChange,
  onPipelineAvatarChange,
}: PipelineTemplateConfigEditorProps) {
  const config = normalizeTemplateConfig(value);
  const { knowledgeBases } = useSidebarData();
  const [activeTab, setActiveTab] = useState<TemplateConfigTab>('basic');
  const [salesProducts, setSalesProducts] = useState<SalesProduct[]>([]);
  const [llmModels, setLlmModels] = useState<LLMModel[]>([]);
  const [voiceModels, setVoiceModels] = useState<LLMModel[]>([]);
  const [uploadingBindingId, setUploadingBindingId] = useState('');
  const [previewQuestion, setPreviewQuestion] = useState('');
  const [showAdvancedRadar, setShowAdvancedRadar] = useState(false);
  const [showAdvancedStopRules, setShowAdvancedStopRules] = useState(false);

  useEffect(() => {
    httpClient
      .getSalesProducts()
      .then((resp) => setSalesProducts(resp.products || []))
      .catch((error) => console.warn('Failed to load sales products', error));
    httpClient
      .getProviderLLMModels(undefined, {
        include_space_models: false,
        include_system_models: false,
        model_category: 'text',
      })
      .then((resp) => setLlmModels(resp.models || []))
      .catch((error) => console.warn('Failed to load LLM models', error));
    httpClient
      .getProviderLLMModels(undefined, {
        include_space_models: false,
        include_system_models: false,
        model_category: 'voice',
      })
      .then((resp) => setVoiceModels(resp.models || []))
      .catch((error) => console.warn('Failed to load voice models', error));
  }, []);

  function patch(next: Partial<PipelineTemplateConfig>) {
    onChange({ ...config, ...next });
  }

  function handleNameChange(name: string) {
    onPipelineNameChange?.(name);
    patch({ name });
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

  function patchRadar(next: Partial<NonNullable<PipelineTemplateConfig['radar']>>) {
    patch({ radar: { ...config.radar!, ...next } });
  }

  function patchStopRules(next: Partial<NonNullable<PipelineTemplateConfig['stop_rules']>>) {
    patch({ stop_rules: { ...config.stop_rules!, ...next } });
  }

  function patchStopPolicy(next: Partial<NonNullable<PipelineTemplateConfig['stop_policy']>>) {
    patch({ stop_policy: { ...config.stop_policy!, ...next } });
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

  function removeImageTextBinding(index: number) {
    patch({
      image_text_bindings: config.image_text_bindings.filter(
        (_, bindingIndex) => bindingIndex !== index,
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

  function removeSalesLink(index: number) {
    patch({
      sales_links: (config.sales_links || []).filter(
        (_, linkIndex) => linkIndex !== index,
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

  function removeRadarRule(index: number) {
    patchRadar({
      rules: (config.radar?.rules || []).filter(
        (_, ruleIndex) => ruleIndex !== index,
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

  function removeFollowupSequence(index: number) {
    patch({
      followup_sequences: (config.followup_sequences || []).filter(
        (_, sequenceIndex) => sequenceIndex !== index,
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

  function removeLongTermBroadcast(index: number) {
    patch({
      long_term_broadcasts: (config.long_term_broadcasts || []).filter(
        (_, broadcastIndex) => broadcastIndex !== index,
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
  const visibleToolKeys = [
    'intent_recognition',
    'knowledge_base',
    'product_database',
    'image_recognition',
  ];
  const enabledToolCount = visibleToolKeys.filter((key) => Boolean(config.tools[key])).length;
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
        <div>
          <FieldLabel>Agent头像</FieldLabel>
          <AgentAvatarPicker
            value={pipelineAvatar}
            onChange={(avatar) => onPipelineAvatarChange?.(avatar)}
            uploadInputId="agent-avatar-upload"
          />
        </div>
        <label className="block">
          <FieldLabel required>数字员工名称</FieldLabel>
          <Input
            value={pipelineName ?? config.name}
            onChange={(event) => handleNameChange(event.target.value)}
            className="h-11"
            maxLength={30}
            placeholder="请输入数字员工名称，例如：课程顾问"
          />
        </label>
        <label className="block">
          <FieldLabel>描述</FieldLabel>
          <Input
            value={pipelineDescription ?? ''}
            onChange={(event) =>
              onPipelineDescriptionChange?.(event.target.value)
            }
            className="h-11"
            placeholder="请输入数字员工描述，例如：负责售前咨询和线索跟进"
          />
        </label>
        <label className="block">
          <FieldLabel hint="用户加好友/首次进线先发这段文字；资源卡片单独通过报名链接里的图书配套学习资源卡片发送。">首次开场白</FieldLabel>
          <Textarea
            value={config.opening_message}
            onChange={(event) => patch({ opening_message: event.target.value })}
            className="min-h-36 resize-none leading-6"
            placeholder="请输入客户首次进线时看到的开场白，例如：您好，我是您的课程顾问，可以帮您介绍课程并解答报名问题。"
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
    const chatLlmModels = llmModels.filter(
      (model) => model.provider?.requester !== 'space-chat-completions',
    );
    const visibleVoiceModels = voiceModels.filter(
      (model) => model.provider?.requester !== 'space-chat-completions',
    );
    const selectedModel = chatLlmModels.find(
      (model) => model.uuid === config.model_uuid,
    );
    const selectedVoiceModel = visibleVoiceModels.find(
      (model) => model.uuid === config.voice.model_uuid,
    );
    const responseDiversity = Number.isFinite(config.response_diversity)
      ? config.response_diversity
      : 0.3;
    const voiceToneOptions = voiceToneOptionsFromModel(selectedVoiceModel);
    const selectedVoiceTone = voiceToneOptions.find(
      (option) => option.value === config.voice.voice_type,
    );

    function handleVoiceModelChange(modelUuid: string) {
      const model = visibleVoiceModels.find((item) => item.uuid === modelUuid);
      if (!model) {
        return;
      }
      const extraArgs = modelExtraArgs(model);
      const options = voiceToneOptionsFromModel(model);
      patch({
        voice: {
          ...config.voice,
          enabled: true,
          model_uuid: model.uuid,
          provider:
            stringExtraArg(extraArgs, 'provider') ||
            model.provider?.requester ||
            model.provider?.name ||
            config.voice.provider,
          voice_type: options[0]?.value || '',
          encoding: stringExtraArg(extraArgs, 'encoding') || config.voice.encoding || 'ogg_opus',
        },
        tools: { ...config.tools, voice_reply: true },
      });
    }

    return (
      <div className="grid gap-5">
        <Section
          icon={Brain}
          title="模型能力"
          description="控制模型、上下文语义识别和回复表达变化。"
        >
          <label className="block">
            <FieldLabel required>选择模型</FieldLabel>
            <Select
              value={selectedModel?.uuid}
              onValueChange={(modelUuid) => patch({ model_uuid: modelUuid })}
              disabled={!chatLlmModels.length}
            >
              <SelectTrigger className="h-11 w-full bg-white">
                <SelectValue
                  placeholder={
                    chatLlmModels.length ? '请选择模型' : '请先在模型配置中添加模型'
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {chatLlmModels.map((model) => (
                  <SelectItem
                    key={model.uuid}
                    value={model.uuid}
                    description={model.provider?.name}
                  >
                    {model.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
          <div className="grid gap-4 md:grid-cols-2">
            <label>
              <FieldLabel>识别上下文语义</FieldLabel>
              <Input
                type="number"
                min={1}
                max={20}
                value={config.reference_rounds}
                onChange={(event) => patch({ reference_rounds: Number(event.target.value || 1) })}
                className="h-11"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                识别最近 {config.reference_rounds || 1} 条对话
              </p>
            </label>
            <label>
              <FieldLabel>回复多样性</FieldLabel>
              <Input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={responseDiversity}
                onChange={(event) =>
                  patch({ response_diversity: Number(event.target.value) })
                }
                className="h-11 accent-indigo-600"
              />
              <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground">
                <span>每次回复都一样</span>
                <span className="font-medium text-slate-700">
                  {responseDiversity.toFixed(1)}
                </span>
                <span>每次回复不一样</span>
              </div>
            </label>
          </div>
        </Section>

        <Section
          icon={Mic2}
          title="语音回复模型"
          description="配置用户发语音时使用的语音模型和音色。"
          right={
            <SummaryPill active={config.voice.enabled}>
              {config.voice.enabled ? '语音已启用' : '语音未启用'}
            </SummaryPill>
          }
        >
          <ToggleRow
            label="语音回复"
            description="开启后，用户用语音咨询时，数字员工会把关键回复转换成语音。"
            checked={config.voice.enabled}
            onCheckedChange={(checked) => {
              patch({
                voice: { ...config.voice, enabled: checked },
                tools: { ...config.tools, voice_reply: checked },
              });
            }}
          />
          <div className="grid gap-4 md:grid-cols-2">
            <label>
              <FieldLabel>语音模型</FieldLabel>
              <Select
                value={selectedVoiceModel?.uuid}
                onValueChange={handleVoiceModelChange}
                disabled={!visibleVoiceModels.length}
              >
                <SelectTrigger className="h-11 w-full bg-white">
                  <SelectValue
                    placeholder={
                      visibleVoiceModels.length
                        ? '请选择语音模型'
                        : '请先在模型配置中添加语音模型'
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {visibleVoiceModels.map((model) => (
                    <SelectItem
                      key={model.uuid}
                      value={model.uuid}
                      description={model.provider?.name}
                    >
                      {model.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <label>
              <FieldLabel>选择音色</FieldLabel>
              <Select
                value={selectedVoiceTone?.value}
                onValueChange={(voiceType) => patchVoice({ voice_type: voiceType })}
                disabled={!selectedVoiceModel || !voiceToneOptions.length}
              >
                <SelectTrigger className="h-11 w-full bg-white">
                  <SelectValue
                    placeholder={
                      selectedVoiceModel
                        ? '请选择音色'
                        : '请先选择语音模型'
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {voiceToneOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
          </div>
        </Section>
      </div>
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
    const courseProfiles = config.course_profiles || [];
    const sourceMaterials = config.source_materials || [];
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
        {(courseProfiles.length > 0 || sourceMaterials.length > 0) && (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
            {courseProfiles.length > 0 && (
              <div className="rounded-md border border-indigo-100 bg-indigo-50/50 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <FieldLabel>已接入业务产品线</FieldLabel>
                  <Badge variant="outline" className="rounded bg-white">
                    {courseProfiles.length} 条
                  </Badge>
                </div>
                <div className="grid gap-3">
                  {courseProfiles.map((profile) => {
                    const facts = profile.facts || {};
                    return (
                      <div key={profile.key} className="rounded-md border border-indigo-100 bg-white p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-slate-900">
                              {profile.name || facts.course_name || profile.key}
                            </p>
                            <p className="mt-1 text-xs leading-5 text-muted-foreground">
                              {[facts.price, facts.duration || facts.lesson_count, facts.target_grade]
                                .filter(Boolean)
                                .join(' · ')}
                            </p>
                          </div>
                          <Badge className="shrink-0 rounded" variant="secondary">
                            业务线
                          </Badge>
                        </div>
                        {facts.selling_point && (
                          <p className="mt-2 text-xs leading-5 text-slate-600">{facts.selling_point}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            {sourceMaterials.length > 0 && (
              <div className="rounded-md border border-slate-200 bg-slate-50/70 p-4">
                <FieldLabel>业务资料来源</FieldLabel>
                <div className="mt-3 grid gap-2">
                  {sourceMaterials.map((source, index) => (
                    <div key={`${source}-${index}`} className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
                      {source}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
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
          title="雷达总开关"
          description="客户点击链接后的行为，会按下方跟进场景自动触发消息。"
          right={
            <SummaryPill active={config.radar?.enabled !== false}>
              {config.radar?.enabled !== false ? '已启用' : '未启用'}
            </SummaryPill>
          }
        >
          <ToggleRow
            label="启用自动跟进雷达"
            description="开启后，客户打开链接、浏览、点击报名或未支付时可以自动追访。"
            checked={config.radar?.enabled !== false}
            onCheckedChange={(checked) => patchRadar({ enabled: checked })}
          />
        </Section>

        <Section
          icon={Link2}
          title="客户可点击的链接"
          description="配置数字员工会发给客户的报名页、资料页或活动页。"
          right={
            <Badge variant="outline" className="rounded-md">
              {(config.sales_links || []).length} 个链接
            </Badge>
          }
        >
          <Button type="button" variant="outline" className="h-10 w-full justify-center rounded-md" onClick={addSalesLink}>
            <Plus className="mr-1.5 size-4" />
            新增客户链接
          </Button>
          <div className="grid gap-3">
            {(config.sales_links || []).map((link, index) => (
              <div key={link.id || index} className="space-y-3 rounded-md border border-slate-200 bg-slate-50/70 p-3">
                <div className="flex items-center gap-3">
                  <Input
                    value={link.title}
                    onChange={(event) => patchSalesLink(index, { title: event.target.value })}
                    className="h-10 bg-white"
                    placeholder="客户看到的链接标题"
                  />
                  <span className="text-xs text-muted-foreground">点击后自动追访</span>
                  <Switch
                    checked={link.radar_enabled !== false}
                    onCheckedChange={(checked) => patchSalesLink(index, { radar_enabled: checked })}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-10 shrink-0 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    title="删除报名链接"
                    onClick={() => removeSalesLink(index)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
                <Input
                  value={link.url}
                  onChange={(event) => patchSalesLink(index, { url: event.target.value })}
                  className="h-10 bg-white"
                  placeholder="粘贴客户要打开的页面地址"
                />
                <Textarea
                  value={link.description || ''}
                  onChange={(event) => patchSalesLink(index, { description: event.target.value })}
                  className="min-h-20 resize-none bg-white leading-6"
                  placeholder="这条链接适合什么时候发送，比如：用户要报名、用户要看资料、用户点不开时备用。"
                />
              </div>
            ))}
          </div>
        </Section>

        <Section
          icon={RadioTower}
          title="点击后的自动跟进"
          description="配置客户点击链接后，数字员工在不同动作下怎么追问。"
          right={
            <Badge variant="outline" className="rounded-md">
              {(config.radar?.rules || []).length} 个场景
            </Badge>
          }
        >
          <Button type="button" variant="outline" className="h-10 w-full justify-center rounded-md" onClick={addRadarRule}>
            <Plus className="mr-1.5 size-4" />
            新增自动跟进场景
          </Button>
          <div className="grid gap-3">
            {(config.radar?.rules || []).map((rule, index) => (
              <div key={`${rule.event}-${index}`} className="space-y-3 rounded-md border border-slate-200 bg-slate-50/70 p-3">
                <div className="grid gap-3 md:grid-cols-[minmax(0,1.4fr)_minmax(0,0.8fr)_auto]">
                  <label className="block">
                    <FieldLabel>客户动作</FieldLabel>
                    <Select
                      value={rule.event || 'link_open'}
                      onValueChange={(value) => patchRadarRule(index, { event: value })}
                    >
                      <SelectTrigger className="h-10 bg-white">
                        <SelectValue placeholder="选择客户动作" />
                      </SelectTrigger>
                      <SelectContent>
                        {RADAR_EVENT_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {radarEventOption(rule.event).description}
                    </p>
                  </label>
                  <label className="block">
                    <FieldLabel>几分钟后发送</FieldLabel>
                    <Input
                      type="number"
                      min={0}
                      value={rule.delay_minutes}
                      onChange={(event) =>
                        patchRadarRule(index, { delay_minutes: Number(event.target.value || 0) })
                      }
                      className="h-10 bg-white"
                      placeholder="分钟"
                    />
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">单位：分钟，0 表示立即发送</p>
                  </label>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="mt-6 size-10 shrink-0 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    title="删除雷达规则"
                    onClick={() => removeRadarRule(index)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
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
          <Button
            type="button"
            variant="ghost"
            className="h-9 px-2 text-sm text-muted-foreground"
            onClick={() => setShowAdvancedRadar((visible) => !visible)}
          >
            {showAdvancedRadar ? '收起高级工作流参数' : '展开高级工作流参数'}
          </Button>
          {showAdvancedRadar && (
            <div className="space-y-3 rounded-md border border-dashed border-slate-300 bg-slate-50/70 p-3">
              <div className="grid gap-3 md:grid-cols-2">
                <label>
                  <FieldLabel>默认雷达链接标题</FieldLabel>
                  <Input
                    value={config.radar?.link_title || ''}
                    onChange={(event) => patchRadar({ link_title: event.target.value })}
                    className="h-10 bg-white"
                    placeholder="例如：9元体验课报名通道"
                  />
                </label>
                <label>
                  <FieldLabel>默认雷达页面地址</FieldLabel>
                  <Input
                    value={config.radar?.link_url || ''}
                    onChange={(event) => patchRadar({ link_url: event.target.value })}
                    className="h-10 bg-white"
                    placeholder="粘贴报名页或活动页地址"
                  />
                </label>
              </div>
              <label className="block">
                <FieldLabel hint="可用换行、逗号或顿号分隔">追踪字段</FieldLabel>
                <Input
                  value={(config.radar?.tracking_fields || []).join('，')}
                  onChange={(event) => patchRadar({ tracking_fields: textToList(event.target.value) })}
                  className="h-10 bg-white"
                  placeholder="session_id，campaign，clicked_at，browse_seconds，paid"
                />
              </label>
              {(config.radar?.rules || []).map((rule, index) => (
                <div key={`advanced-${rule.event}-${index}`} className="grid gap-3 md:grid-cols-2">
                  <label className="block">
                    <FieldLabel>事件代号</FieldLabel>
                    <Input
                      value={rule.event}
                      onChange={(event) => patchRadarRule(index, { event: event.target.value })}
                      className="h-10 bg-white"
                      placeholder="例如 browse_30s"
                    />
                  </label>
                  <label className="block">
                    <FieldLabel>浏览时长门槛（秒）</FieldLabel>
                    <Input
                      type="number"
                      min={0}
                      value={rule.min_browse_seconds || 0}
                      onChange={(event) =>
                        patchRadarRule(index, { min_browse_seconds: Number(event.target.value || 0) })
                      }
                      className="h-10 bg-white"
                      placeholder="0"
                    />
                  </label>
                </div>
              ))}
            </div>
          )}
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
                <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
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
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-10 shrink-0 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    title="删除跟进场景"
                    onClick={() => removeFollowupSequence(index)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
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

        <Section icon={CalendarClock} title="SOP定时群发">
          <Button type="button" variant="outline" className="h-10 w-full justify-center rounded-md" onClick={addLongTermBroadcast}>
            <Plus className="mr-1.5 size-4" />
            新增长期群发
          </Button>
          <div className="grid gap-3">
            {(config.long_term_broadcasts || []).map((broadcast, index) => (
              <div key={`${broadcast.day}-${index}`} className="space-y-3 rounded-md border border-slate-200 bg-slate-50/70 p-3">
                <div className="grid gap-3 md:grid-cols-[100px_minmax(0,1fr)_120px_auto]">
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
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-10 shrink-0 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    title="删除长期群发"
                    onClick={() => removeLongTermBroadcast(index)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
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
          description="控制客户拒绝或投诉后的主动触达边界。"
        >
          <label className="block max-w-md">
            <FieldLabel>客户明确拒绝几次后停止主动触达</FieldLabel>
            <Input
              type="number"
              min={1}
              value={config.stop_policy?.explicit_rejection_threshold || 1}
              onChange={(event) =>
                patchStopPolicy({
                  explicit_rejection_threshold: Math.max(1, Number(event.target.value || 1)),
                })
              }
              className="h-11"
              placeholder="2"
            />
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              例如设置为 2：客户连续两次明确说不需要、不买或别推了，数字员工才停止后续主动消息。
            </p>
          </label>
          <label className="block">
            <FieldLabel>停发确认话术</FieldLabel>
            <Textarea
              value={config.stop_rules?.message || ''}
              onChange={(event) => patchStopRules({ message: event.target.value })}
              className="min-h-20 resize-none leading-6"
              placeholder="停发确认话术"
            />
          </label>
          <Button
            type="button"
            variant="ghost"
            className="h-9 px-2 text-sm text-muted-foreground"
            onClick={() => setShowAdvancedStopRules((visible) => !visible)}
          >
            {showAdvancedStopRules ? '收起关键词配置' : '展开关键词配置'}
          </Button>
          {showAdvancedStopRules && (
            <div className="grid gap-4 md:grid-cols-2">
              <label>
                <FieldLabel hint="每行一个">明确拒绝关键词</FieldLabel>
                <Textarea
                  value={(config.stop_policy?.explicit_rejection_keywords || []).join('\n')}
                  onChange={(event) =>
                    patchStopPolicy({ explicit_rejection_keywords: textToList(event.target.value) })
                  }
                  className="min-h-28 resize-none leading-6"
                  placeholder="不需要&#10;不买&#10;没兴趣"
                />
              </label>
              <label>
                <FieldLabel hint="每行一个">立即停发关键词</FieldLabel>
                <Textarea
                  value={(config.stop_policy?.immediate_stop_keywords || []).join('\n')}
                  onChange={(event) =>
                    patchStopPolicy({ immediate_stop_keywords: textToList(event.target.value) })
                  }
                  className="min-h-28 resize-none leading-6"
                  placeholder="投诉&#10;没有孩子&#10;打错"
                />
              </label>
              <label>
                <FieldLabel hint="每行一个">兼容停发关键词</FieldLabel>
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
          )}
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
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-10 shrink-0 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    title="删除图文绑定"
                    onClick={() => removeImageTextBinding(index)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
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

      </div>
    );
  }

  function renderPanelByTab(tabId: TemplateConfigTab) {
    switch (tabId) {
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

  const currentAvatarUrl = agentAvatarUrl(pipelineAvatar);
  const previewRadarLink =
    config.radar?.link_url ||
    (config.sales_links || []).find((link) => link.radar_enabled !== false)?.url ||
    '';
  const previewRadarReply =
    config.radar?.rules?.[0]?.message ||
    '客户点击链接后，数字员工会按自动跟进场景发送消息。';

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm lg:h-[calc(100vh-220px)]">
      <div className="grid min-h-[720px] grid-cols-1 lg:h-full lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div className="flex min-w-0 flex-col border-r border-slate-200 bg-white lg:min-h-0 lg:overflow-hidden">
          <div className="shrink-0 border-b border-slate-200 px-5 py-4">
            <div className="overflow-x-auto rounded-md border border-slate-200 bg-slate-50 p-1">
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

          <div className="min-h-0 flex-1 overflow-y-auto bg-slate-50/60 p-5">
            {renderPanelByTab(activeTab)}
          </div>
        </div>

        <aside className="flex min-h-0 min-w-0 flex-col bg-white lg:sticky lg:top-0 lg:h-full lg:overflow-hidden">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="text-base font-semibold text-slate-950">预览调试</h2>
          </div>

          <div className="flex min-h-0 flex-1 flex-col bg-slate-50/70 p-5">
            <div className="mb-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <img
                  src={currentAvatarUrl}
                  alt="Agent头像"
                  className="size-11 shrink-0 rounded-full border border-white bg-white object-cover shadow-sm"
                />
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-slate-950">
                    {config.name || '未命名数字员工'}
                  </h3>
                </div>
              </div>
            </div>

            <div className="min-h-[460px] flex-1 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <div className="space-y-4">
                <div className="flex gap-3">
                  <img
                    src={currentAvatarUrl}
                    alt="Agent头像"
                    className="size-8 shrink-0 rounded-full border border-white bg-white object-cover shadow-sm"
                  />
                  <div className="max-w-[82%] rounded-lg rounded-tl-sm bg-slate-100 px-4 py-3 text-sm leading-6 text-slate-800">
                    {config.opening_message.trim() ? (
                      config.opening_message
                    ) : (
                      <span className="text-slate-400">
                        开场白会显示在这里
                      </span>
                    )}
                  </div>
                </div>

                {config.radar?.enabled !== false && previewRadarLink && (
                  <>
                    <div className="ml-11 rounded-lg border border-indigo-100 bg-indigo-50/80 p-3 text-left">
                      <div className="flex items-center gap-2 text-xs font-medium text-indigo-700">
                        <MousePointerClick className="size-3.5" />
                        自动跟进链接
                      </div>
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {previewRadarLink}
                      </p>
                    </div>
                    <div className="flex justify-end">
                      <div className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white">
                        客户已点击链接
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <img
                        src={currentAvatarUrl}
                        alt="Agent头像"
                        className="size-8 shrink-0 rounded-full border border-white bg-white object-cover shadow-sm"
                      />
                      <div className="max-w-[82%] rounded-lg rounded-tl-sm bg-slate-100 px-4 py-3 text-sm leading-6 text-slate-800">
                        {previewRadarReply}
                      </div>
                    </div>
                  </>
                )}

                {enabledImageBindings[0] && (
                  <div className="ml-11 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
                    {(enabledImageBindings[0].image_url ||
                      enabledImageBindings[0].file_key) && (
                      <img
                        src={
                          enabledImageBindings[0].image_url ||
                          imageAssetUrl(enabledImageBindings[0].file_key)
                        }
                        alt={enabledImageBindings[0].title}
                        className="max-h-48 w-full object-contain"
                      />
                    )}
                    <div className="p-3">
                      <div className="flex items-center gap-2 text-xs font-medium text-slate-700">
                        <ImageIcon className="size-3.5" />
                        {enabledImageBindings[0].title}
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                        {enabledImageBindings[0].text}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-slate-200 bg-white p-2 shadow-sm">
              <div className="flex items-center gap-2 rounded-md bg-slate-50 px-3 py-2.5">
                <Input
                  value={previewQuestion}
                  onChange={(event) => setPreviewQuestion(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                    }
                  }}
                  className="h-8 flex-1 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
                  placeholder="在此提问，测试基于配置的回答效果"
                />
                <Mic2 className={cn('size-4 shrink-0', config.voice.enabled ? 'text-indigo-600' : 'text-muted-foreground')} />
                <Button
                  type="button"
                  size="sm"
                  className="h-8 rounded-md px-3"
                  disabled={!previewQuestion.trim()}
                >
                  <SendHorizontal className="mr-1.5 size-3.5" />
                  发送
                </Button>
              </div>
            </div>

            <div className="mt-4 grid gap-2 text-xs text-muted-foreground">
              <div className="flex items-center gap-2">
                <Handshake className="size-3.5" />
                <span>转人工、群聊回复等复杂能力可在独立工作流页面中继续扩展。</span>
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
