import { useEffect, useState, type ChangeEvent, type ReactNode } from 'react';
import {
  Bot,
  CalendarClock,
  Image as ImageIcon,
  MessageSquareText,
  Mic2,
  Plus,
  Sparkles,
  Upload,
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
    image_text_bindings:
      value?.image_text_bindings?.length ? value.image_text_bindings : defaults.image_text_bindings,
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
    <section className="border-b px-5 py-4 last:border-b-0">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <Icon className="mt-0.5 size-4 text-muted-foreground" />
          <div>
            <h3 className="text-sm font-semibold leading-5">{title}</h3>
            {description && (
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
            )}
          </div>
        </div>
        {right}
      </div>
      {children}
    </section>
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

export default function PipelineTemplateConfigEditor({
  value,
  onChange,
}: PipelineTemplateConfigEditorProps) {
  const config = normalizeTemplateConfig(value);
  const { knowledgeBases } = useSidebarData();
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

  function addImageTextBinding() {
    patch({
      image_text_bindings: [
        ...config.image_text_bindings,
        makeCustomImageBinding(),
      ],
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

  return (
    <div className="min-h-[720px] overflow-hidden rounded-lg border bg-background">
      <div className="grid min-h-[720px] grid-cols-1 lg:grid-cols-[1.05fr_1.1fr_0.9fr]">
        <div className="flex min-h-0 flex-col border-r">
          <div className="border-b px-5 py-4">
            <div className="flex items-center gap-2">
              <Bot className="size-4" />
              <h2 className="text-base font-semibold">Agent配置</h2>
              <Badge variant="secondary">模板配置</Badge>
            </div>
          </div>
          <Section
            icon={MessageSquareText}
            title="角色指令"
            description="该章节主题内容、行为逻辑等，支持接入知识库和数据库。"
          >
            <Textarea
              value={config.role_prompt}
              onChange={(event) => patch({ role_prompt: event.target.value })}
              className="min-h-[320px] resize-none"
              placeholder="请输入角色指令"
            />
          </Section>
          <div className="mt-auto flex items-center gap-2 border-t px-5 py-3 text-xs text-muted-foreground">
            <span>输入或点击引入：</span>
            <Badge variant="outline">@ 工具</Badge>
            <Badge variant="outline">{'{变量值}'}</Badge>
            <button type="button" className="text-primary">示例</button>
          </div>
        </div>

        <div className="min-h-0 overflow-y-auto">
          <Section
            icon={Sparkles}
            title="能力扩展"
            description="模型、工具、知识、数据库、记忆、图片和语音都可以在这里傻瓜式配置。"
          >
            <div className="space-y-3">
              <label className="block text-xs font-medium text-muted-foreground">模型</label>
              <Input
                value={config.model_uuid}
                onChange={(event) => patch({ model_uuid: event.target.value })}
                placeholder="模型 UUID"
              />
              <div className="grid grid-cols-2 gap-3">
                <label className="space-y-1">
                  <span className="text-xs text-muted-foreground">最大思考次数</span>
                  <Input
                    type="number"
                    min={1}
                    max={12}
                    value={config.max_reasoning_steps}
                    onChange={(event) => patch({ max_reasoning_steps: Number(event.target.value || 1) })}
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-muted-foreground">参考对话轮数</span>
                  <Input
                    type="number"
                    min={1}
                    max={20}
                    value={config.reference_rounds}
                    onChange={(event) => patch({ reference_rounds: Number(event.target.value || 1) })}
                  />
                </label>
              </div>
            </div>
          </Section>

          <Section icon={Bot} title="工具">
            <div className="grid gap-3">
              {[
                ['intent_recognition', '意图识别'],
                ['knowledge_base', '知识库'],
                ['product_database', '产品数据库'],
                ['image_recognition', '截图识别'],
                ['voice_reply', '语音回复'],
              ].map(([key, label]) => (
                <div key={key} className="flex items-center justify-between rounded-md border px-3 py-2">
                  <span className="text-sm">{label}</span>
                  <Switch
                    checked={Boolean(config.tools[key])}
                    onCheckedChange={(checked) => patchTool(key, checked)}
                  />
                </div>
              ))}
            </div>
          </Section>

          {(config.tools.knowledge_base || config.tools.product_database) && (
            <Section
              icon={Bot}
              title="知识和数据"
              description="开关打开后直接选择已有知识库和产品库，不需要手填 ID。"
            >
              <div className="grid gap-3">
                {config.tools.knowledge_base && (
                  <div className="space-y-2">
                    <span className="text-xs font-medium text-muted-foreground">
                      关联知识库
                    </span>
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
                              ? 'border-blue-300 bg-blue-50 text-blue-950'
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
                            <Badge>已选</Badge>
                          )}
                        </button>
                      ))}
                      {!knowledgeBases.length && (
                        <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                          暂无知识库，请先在左侧知识库中创建
                        </div>
                      )}
                    </div>
                  </div>
                )}
                {config.tools.product_database && (
                  <div className="space-y-2">
                    <span className="text-xs font-medium text-muted-foreground">
                      关联产品
                    </span>
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
                              ? 'border-blue-300 bg-blue-50 text-blue-950'
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
                            <Badge>已选</Badge>
                          )}
                        </button>
                      ))}
                      {!salesProducts.length && (
                        <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                          暂无产品，请先在销售工作台中创建
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </Section>
          )}

          <Section icon={Bot} title="记忆">
            <div className="space-y-3">
              {[
                ['variables_enabled', '记忆变量', '记录聊天对话中的一维、单个的应用信息或用户信息。'],
                ['table_enabled', '记忆表', '记录聊天对话中的多维、大量的应用信息或用户信息。'],
                ['segments_enabled', '记忆片段', '记录用户偏好、计划和长期上下文。'],
              ].map(([key, label, description]) => (
                <div key={key} className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium">{label}</p>
                    <p className="text-xs text-muted-foreground">{description}</p>
                  </div>
                  <Switch
                    checked={Boolean(config.memory[key as keyof typeof config.memory])}
                    onCheckedChange={(checked) =>
                      patchMemory({
                        [key]: checked,
                      } as Partial<PipelineTemplateConfig['memory']>)
                    }
                  />
                </div>
              ))}
            </div>
          </Section>

          <Section icon={CalendarClock} title="定时推送">
            <div className="grid gap-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">启用定时推送</span>
                <Switch
                  checked={config.scheduled_push.enabled}
                  onCheckedChange={(checked) => patchScheduledPush({ enabled: checked })}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Select
                  value={config.scheduled_push.mode}
                  onValueChange={(mode) =>
                    patchScheduledPush({ mode: mode as 'daily' | 'single_day' })
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">每天推送</SelectItem>
                    <SelectItem value="single_day">指定单天</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  type="time"
                  value={config.scheduled_push.time}
                  onChange={(event) => patchScheduledPush({ time: event.target.value })}
                />
              </div>
              {config.scheduled_push.mode === 'single_day' && (
                <Input
                  type="date"
                  value={config.scheduled_push.single_date}
                  onChange={(event) => patchScheduledPush({ single_date: event.target.value })}
                />
              )}
              <Textarea
                value={scheduledMessage}
                onChange={(event) => patchScheduledPush({ message: event.target.value })}
                className="min-h-24"
                placeholder="请输入定时推送的消息"
              />
            </div>
          </Section>

          <Section icon={ImageIcon} title="图片文字绑定">
            <div className="space-y-3">
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={addImageTextBinding}
              >
                <Plus className="mr-1.5 size-4" />
                新增图文绑定
              </Button>
              {config.image_text_bindings.map((binding, index) => (
                <div key={binding.step_id || index} className="rounded-md border p-3">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <Input
                      value={binding.title}
                      onChange={(event) => patchBinding(index, { title: event.target.value })}
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
                    className="mb-2 min-h-20"
                    placeholder="步骤说明"
                  />
                  <input
                    id={`template-image-${binding.step_id || index}`}
                    className="hidden"
                    type="file"
                    accept="image/*"
                    onChange={(event) => uploadImageForBinding(index, event)}
                  />
                  <div className="mb-2 flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
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
                        : '直接上传图片'}
                    </Button>
                    <Input
                      value={binding.image_url || ''}
                      onChange={(event) =>
                        patchBinding(index, { image_url: event.target.value })
                      }
                      placeholder="图片 URL（可选）"
                    />
                  </div>
                  {(binding.image_url || binding.file_key) && (
                    <div className="mb-2 overflow-hidden rounded-md border bg-muted">
                      <img
                        src={binding.image_url || imageAssetUrl(binding.file_key)}
                        alt={binding.title}
                        className="max-h-36 w-full object-contain"
                      />
                    </div>
                  )}
                  <Input
                    value={binding.file_key}
                    onChange={(event) => patchBinding(index, { file_key: event.target.value })}
                    placeholder="图片 file_key 或上传后的素材路径"
                  />
                </div>
              ))}
            </div>
          </Section>

          <Section icon={Mic2} title="声音和形象">
            <div className="grid gap-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">语音回复</span>
                <Switch
                  checked={config.voice.enabled}
                  onCheckedChange={(checked) => patchVoice({ enabled: checked })}
                />
              </div>
              <Input
                value={config.voice.voice_type}
                onChange={(event) => patchVoice({ voice_type: event.target.value })}
                placeholder="音色ID"
              />
              <Input
                value={config.voice.encoding}
                onChange={(event) => patchVoice({ encoding: event.target.value })}
                placeholder="音频编码"
              />
            </div>
          </Section>
        </div>

        <div className="flex min-h-0 flex-col bg-muted/40">
          <div className="border-b px-5 py-4">
            <h2 className="text-base font-semibold">预览与调试</h2>
          </div>
          <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
            <div className="mb-5 grid size-16 place-items-center rounded-2xl bg-gradient-to-br from-sky-400 via-blue-300 to-amber-200 text-white shadow-sm">
              <Bot className="size-8" />
            </div>
            <h3 className="mb-2 text-xl font-semibold">{config.name || '未命名流水线'}</h3>
            <p className="max-w-sm text-sm leading-6 text-muted-foreground">
              {config.opening_message}
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {config.recommended_questions.map((question) => (
                <Badge key={question} variant="outline" className="max-w-[220px] truncate">
                  {question}
                </Badge>
              ))}
            </div>
          </div>
          <div className="border-t bg-background/80 p-5">
            <div className="flex items-center gap-2 rounded-full border bg-background px-4 py-3 shadow-sm">
              <span className="flex-1 text-left text-sm text-muted-foreground">
                请输入你的问题 支持对上传文件内容进行提问
              </span>
              <Mic2 className={cn('size-4', config.voice.enabled ? 'text-primary' : 'text-muted-foreground')} />
              <Button type="button" size="sm" className="rounded-full">
                发送
              </Button>
            </div>
            <p className="mt-3 text-center text-xs text-muted-foreground">以上内容均由AI生成，仅供参考</p>
          </div>
        </div>
      </div>
    </div>
  );
}
