import { useEffect, useRef, useState, useMemo, type ElementType } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { GetPipelineResponseData, Pipeline } from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Input } from '@/components/ui/input';
import EmojiPicker from '@/components/ui/emoji-picker';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Info,
  Trash2,
  Copy,
  Workflow,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import PipelineTemplateConfigEditor from '@/app/home/pipelines/components/workflow-editor/PipelineTemplateConfigEditor';
import PipelineWorkflowEditor from '@/app/home/pipelines/components/workflow-editor/PipelineWorkflowEditor';
import {
  createDefaultWorkflow,
  createTaskAssistantTemplateConfig,
} from '@/app/home/pipelines/components/workflow-editor/workflowTemplates';
import {
  PipelineTemplateConfig,
  PipelineWorkflow,
} from '@/app/home/pipelines/components/workflow-editor/types';

function selectedWorkflowModelUuid(workflow?: PipelineWorkflow): string {
  const llmNode = workflow?.nodes?.find(
    (node) =>
      node.type === 'llm' &&
      typeof node.config?.model_uuid === 'string' &&
      node.config.model_uuid,
  );
  return typeof llmNode?.config.model_uuid === 'string'
    ? llmNode.config.model_uuid
    : '';
}

function syncWorkflowModelIntoAIConfig(
  workflow: PipelineWorkflow | undefined,
  aiConfig: Record<string, any> | undefined,
) {
  const selectedModelUuid = selectedWorkflowModelUuid(workflow);
  if (!selectedModelUuid) {
    return aiConfig || {};
  }

  const localAgentConfig = aiConfig?.['local-agent'] || {};
  const existingModelConfig = localAgentConfig.model;
  const fallbackModels =
    existingModelConfig &&
    typeof existingModelConfig === 'object' &&
    Array.isArray(existingModelConfig.fallbacks)
      ? existingModelConfig.fallbacks
      : [];

  return {
    ...(aiConfig || {}),
    runner: {
      ...(aiConfig?.runner || {}),
      runner: 'local-agent',
    },
    ['local-agent']: {
      ...localAgentConfig,
      model: {
        primary: selectedModelUuid,
        fallbacks: fallbackModels,
      },
    },
  };
}

function syncTemplateModelIntoAIConfig(
  templateConfig: PipelineTemplateConfig,
  aiConfig: Record<string, any> | undefined,
) {
  const selectedModelUuid = templateConfig.model_uuid;
  if (!selectedModelUuid) {
    return aiConfig || {};
  }

  const localAgentConfig = aiConfig?.['local-agent'] || {};
  const existingModelConfig = localAgentConfig.model;
  const fallbackModels =
    existingModelConfig && typeof existingModelConfig === 'object' && Array.isArray(existingModelConfig.fallbacks)
      ? existingModelConfig.fallbacks
      : [];

  return {
    ...(aiConfig || {}),
    runner: {
      ...(aiConfig?.runner || {}),
      runner: 'local-agent',
    },
    ['local-agent']: {
      ...localAgentConfig,
      model: {
        primary: selectedModelUuid,
        fallbacks: fallbackModels,
      },
    },
  };
}

function syncAIModelIntoWorkflow(
  workflow: PipelineWorkflow,
  aiConfig: Record<string, any> | undefined,
): PipelineWorkflow {
  const primaryModel = aiConfig?.['local-agent']?.model?.primary;
  if (!primaryModel || selectedWorkflowModelUuid(workflow)) {
    return workflow;
  }

  return {
    ...workflow,
    nodes: workflow.nodes.map((node) =>
      node.type === 'llm'
        ? {
            ...node,
            config: {
              ...node.config,
              model_uuid: primaryModel,
            },
          }
        : node,
    ),
  };
}

export default function PipelineFormComponent({
  onFinish,
  onNewPipelineCreated,
  isEditMode,
  pipelineId,
  showButtons = true,
  onDeletePipeline,
  onCancel,
  onDirtyChange,
}: {
  pipelineId?: string;
  isEditMode: boolean;
  disableForm: boolean;
  showButtons?: boolean;
  onFinish: () => void;
  onNewPipelineCreated: (pipelineId: string) => void;
  onDeletePipeline: () => void;
  onCancel?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const { t } = useTranslation();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showCopyConfirm, setShowCopyConfirm] = useState(false);
  const [isDefaultPipeline, setIsDefaultPipeline] = useState<boolean>(false);

  const formSchema = isEditMode
    ? z.object({
        basic: z.object({
          name: z.string().min(1, { message: t('pipelines.nameRequired') }),
          description: z.string().optional(),
          emoji: z.string().optional(),
        }),
        ai: z.record(z.string(), z.any()),
        trigger: z.record(z.string(), z.any()),
        safety: z.record(z.string(), z.any()),
        output: z.record(z.string(), z.any()),
        config_mode: z.enum(['template', 'workflow']).optional(),
        template_config: z.any().optional(),
        workflow: z.any(),
      })
    : z.object({
        basic: z.object({
          name: z.string().min(1, { message: t('pipelines.nameRequired') }),
          description: z.string().optional(),
          emoji: z.string().optional(),
        }),
        ai: z.record(z.string(), z.any()).optional(),
        trigger: z.record(z.string(), z.any()).optional(),
        safety: z.record(z.string(), z.any()).optional(),
        output: z.record(z.string(), z.any()).optional(),
        config_mode: z.enum(['template', 'workflow']).optional(),
        template_config: z.any().optional(),
        workflow: z.any().optional(),
      });

  type FormValues = z.infer<typeof formSchema>;
  // Section navigation items with icons
  const SECTION_ICONS: Record<string, ElementType> = {
    basic: Info,
    workflow: Workflow,
  };

  const formLabelList: SectionItem[] = isEditMode
    ? [
        {
          label: t('pipelines.basicInfo'),
          name: 'basic',
          icon: SECTION_ICONS.basic,
        },
        {
          label: '数字员工配置',
          name: 'workflow',
          icon: SECTION_ICONS.workflow,
        },
      ]
    : [
        {
          label: t('pipelines.basicInfo'),
          name: 'basic',
          icon: SECTION_ICONS.basic,
        },
      ];

  const [activeSection, setActiveSection] = useState(formLabelList[0].name);
  const [sectionNavCollapsed, setSectionNavCollapsed] = useState(false);
  const compactSectionNav = activeSection === 'workflow';

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      basic: {
        emoji: '⚙️',
      },
      ai: {},
      trigger: {},
      safety: {},
      output: {},
      config_mode: 'workflow',
      template_config: createTaskAssistantTemplateConfig(),
      workflow: createDefaultWorkflow(),
    },
  });

  // Track unsaved changes by comparing current form values against a saved snapshot
  const savedSnapshotRef = useRef<string>('');
  const watchedValues = form.watch();
  const hasUnsavedChanges = useMemo(() => {
    if (!isEditMode || !savedSnapshotRef.current) return false;
    return JSON.stringify(watchedValues) !== savedSnapshotRef.current;
  }, [isEditMode, watchedValues]);

  // Notify parent when dirty state changes
  useEffect(() => {
    onDirtyChange?.(hasUnsavedChanges);
  }, [hasUnsavedChanges, onDirtyChange]);

  useEffect(() => {
    if (isEditMode) {
      httpClient
        .getPipeline(pipelineId || '')
        .then((resp: GetPipelineResponseData) => {
          setIsDefaultPipeline(resp.pipeline.is_default ?? false);
          const pipelineConfig = resp.pipeline.config as Record<string, any>;
          const aiConfig = pipelineConfig.ai || {};
          const configMode: 'template' | 'workflow' =
            pipelineConfig.config_mode === 'template' ? 'template' : 'workflow';
          const templateConfig =
            (pipelineConfig.template_config as PipelineTemplateConfig | undefined) ||
            createTaskAssistantTemplateConfig();
          const workflowConfig = syncAIModelIntoWorkflow(
            (pipelineConfig.workflow as PipelineWorkflow | undefined) ||
              createDefaultWorkflow(),
            aiConfig,
          );
          const loadedValues = {
            basic: {
              name: resp.pipeline.name,
              description: resp.pipeline.description,
              emoji: resp.pipeline.emoji || '⚙️',
            },
            ai: aiConfig,
            trigger: pipelineConfig.trigger || {},
            safety: pipelineConfig.safety || {},
            output: pipelineConfig.output || {},
            config_mode: configMode,
            template_config: templateConfig,
            workflow: workflowConfig,
          };
          form.reset(loadedValues);
          savedSnapshotRef.current = JSON.stringify(loadedValues);
        });
    }
  }, []);

  useEffect(() => {
    if (!isEditMode) {
      form.reset({
        basic: {
          name: '',
          description: '',
          emoji: '⚙️',
        },
        config_mode: 'workflow',
        template_config: createTaskAssistantTemplateConfig(),
        workflow: createDefaultWorkflow(),
      });
    }
  }, [form, isEditMode]);

  function handleFormSubmit(values: FormValues) {
    if (isEditMode) {
      handleModify(values);
    } else {
      handleCreate(values);
    }
  }

  function handleCreate(values: FormValues) {
    const pipeline: Pipeline = {
      config: {},
      description: values.basic.description ?? '',
      name: values.basic.name,
      emoji: values.basic.emoji,
    };
    httpClient
      .createPipeline(pipeline)
      .then((resp) => {
        onFinish();
        onNewPipelineCreated(resp.uuid);
        toast.success(t('pipelines.createSuccess'));
      })
      .catch((err) => {
        toast.error(t('pipelines.createError') + err.msg);
      });
  }

  function handleModify(values: FormValues) {
    const configMode = values.config_mode || 'workflow';
    const templateConfig =
      (values.template_config as PipelineTemplateConfig | undefined) ||
      createTaskAssistantTemplateConfig();
    const baseWorkflow = (values.workflow as PipelineWorkflow | undefined) || createDefaultWorkflow();
    const workflow = baseWorkflow;
    const realConfig = {
      ai:
        configMode === 'template'
          ? syncTemplateModelIntoAIConfig(templateConfig, values.ai)
          : syncWorkflowModelIntoAIConfig(workflow, values.ai),
      trigger: values.trigger,
      safety: values.safety,
      output: values.output,
      config_mode: configMode,
      template_config: templateConfig,
      workflow,
    };

    const pipeline: Pipeline = {
      config: realConfig,
      // created_at: '',
      description: values.basic.description ?? '',
      // for_version: '',
      name: values.basic.name,
      emoji: values.basic.emoji,
      // stages: [],
      // updated_at: '',
      // uuid: pipelineId || '',
      // is_default: false,
    };
    httpClient
      .updatePipeline(pipelineId || '', pipeline)
      .then(() => {
        savedSnapshotRef.current = JSON.stringify(form.getValues());
        onFinish();
        toast.success(t('pipelines.saveSuccess'));
      })
      .catch((err) => {
        toast.error(t('pipelines.saveError') + err.msg);
      });
  }

  const handleDelete = () => {
    setShowDeleteConfirm(true);
  };

  const confirmDelete = () => {
    if (pipelineId) {
      httpClient
        .deletePipeline(pipelineId)
        .then(() => {
          onDeletePipeline();
          setShowDeleteConfirm(false);
          toast.success(t('pipelines.deleteSuccess'));
        })
        .catch((err) => {
          toast.error(t('pipelines.deleteError') + err.msg);
        });
    }
  };

  const handleCopy = () => {
    setShowCopyConfirm(true);
  };

  const confirmCopy = () => {
    if (pipelineId) {
      httpClient
        .copyPipeline(pipelineId)
        .then(() => {
          onFinish();
          toast.success(t('common.copySuccess'));
          setShowCopyConfirm(false);
          onCancel?.();
        })
        .catch((err) => {
          toast.error(t('pipelines.createError') + err.msg);
        });
    }
  };

  function getTemplateConfigValue(): PipelineTemplateConfig {
    return (
      (form.getValues('template_config') as PipelineTemplateConfig | undefined) ||
      createTaskAssistantTemplateConfig()
    );
  }

  function setWorkflowValue(workflow: PipelineWorkflow) {
    form.setValue('workflow', workflow, { shouldDirty: true });
    form.setValue(
      'ai',
      syncWorkflowModelIntoAIConfig(workflow, form.getValues('ai')),
      { shouldDirty: true },
    );
  }

  function handleConfigModeChange(mode: 'template' | 'workflow') {
    form.setValue('config_mode', mode, { shouldDirty: true });
    if (mode === 'template') {
      const templateConfig = getTemplateConfigValue();
      form.setValue('template_config', templateConfig, { shouldDirty: true });
    }
  }

  function handleTemplateConfigChange(templateConfig: PipelineTemplateConfig) {
    form.setValue('template_config', templateConfig, { shouldDirty: true });
  }

  const selectedConfigMode = (form.watch('config_mode') || 'workflow') as
    | 'template'
    | 'workflow';

  return (
    <>
      <div className="h-full p-0 flex flex-col">
        <Form {...form}>
          <form
            id="pipeline-form"
            onSubmit={form.handleSubmit(handleFormSubmit)}
            className="h-full flex flex-col flex-1 min-h-0 mb-2"
          >
            <div className="flex-1 flex flex-col md:flex-row min-h-0 gap-3">
              {/* Vertical section navigation (only show when multiple sections) */}
              {formLabelList.length > 1 && !sectionNavCollapsed && (
                <nav
                  className={cn(
                    'mb-2 shrink-0 overflow-x-auto md:mb-0 md:overflow-x-visible md:overflow-y-auto',
                    compactSectionNav ? 'md:w-11' : 'md:w-48',
                  )}
                >
                  {!compactSectionNav && (
                    <div className="mb-2 hidden items-center justify-between px-1 md:flex">
                      <span className="text-xs font-semibold text-muted-foreground">
                        配置分区
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="size-7 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                        title="收起配置面板"
                        onClick={() => setSectionNavCollapsed(true)}
                      >
                        <PanelLeftClose className="size-4" />
                      </Button>
                    </div>
                  )}
                  <ul
                    className={cn(
                      'flex gap-1 rounded-xl bg-slate-100 p-1 md:flex-col md:space-y-1',
                      compactSectionNav && 'md:items-center',
                    )}
                  >
                    {formLabelList.map((section) => {
                      const Icon = section.icon;
                      return (
                        <li key={section.name}>
                          <button
                            type="button"
                            title={section.label}
                            onClick={() => setActiveSection(section.name)}
                            className={cn(
                              'w-full flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors text-left cursor-pointer whitespace-nowrap',
                              compactSectionNav &&
                                'md:size-9 md:justify-center md:px-0',
                              activeSection === section.name
                                ? 'bg-white text-slate-950 shadow-sm'
                                : 'text-slate-500 hover:bg-white/60 hover:text-slate-900',
                            )}
                          >
                            <Icon className="size-4 shrink-0" />
                            <span
                              className={cn(compactSectionNav && 'md:hidden')}
                            >
                              {section.label}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </nav>
              )}

              {formLabelList.length > 1 && sectionNavCollapsed && (
                <div className="hidden shrink-0 flex-col items-center gap-2 rounded-xl bg-slate-100 p-1 md:flex">
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="size-8 rounded-lg border-slate-200 bg-white"
                    title="展开配置面板"
                    onClick={() => setSectionNavCollapsed(false)}
                  >
                    <PanelLeftOpen className="size-4" />
                  </Button>
                  {formLabelList.map((section) => {
                    const Icon = section.icon;
                    return (
                      <button
                        key={section.name}
                        type="button"
                        title={section.label}
                        onClick={() => setActiveSection(section.name)}
                        className={cn(
                          'flex size-8 items-center justify-center rounded-lg transition-colors',
                          activeSection === section.name
                            ? 'bg-white text-slate-950 shadow-sm'
                            : 'text-slate-500 hover:bg-white/60 hover:text-slate-900',
                        )}
                      >
                        <Icon className="size-4" />
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Content panel */}
              <div
                className={cn(
                  'flex-1 min-h-0',
                  activeSection === 'workflow'
                    ? selectedConfigMode === 'template'
                      ? 'overflow-y-auto'
                      : 'flex flex-col overflow-hidden'
                    : 'overflow-y-auto',
                )}
              >
                {/* Basic info section */}
                {activeSection === 'basic' && (
                  <div className="space-y-6">
                    {/* Basic Information Card */}
                    <Card>
                      <CardHeader>
                        <CardTitle>{t('pipelines.basicInfo')}</CardTitle>
                        <CardDescription>
                          {t('pipelines.basicInfoDescription')}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {/* Name and Emoji in same row */}
                        <div className="flex gap-4 items-start">
                          <FormField
                            control={form.control}
                            name="basic.name"
                            render={({ field }) => (
                              <FormItem className="flex-1">
                                <FormLabel>
                                  {t('common.name')}
                                  <span className="text-destructive">*</span>
                                </FormLabel>
                                <FormControl>
                                  <Input {...field} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name="basic.emoji"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>{t('common.icon')}</FormLabel>
                                <FormControl>
                                  <EmojiPicker
                                    value={field.value}
                                    onChange={field.onChange}
                                  />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>

                        <FormField
                          control={form.control}
                          name="basic.description"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>{t('common.description')}</FormLabel>
                              <FormControl>
                                <Input {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        {/* Copy pipeline (edit mode only) */}
                        {isEditMode && (
                          <div className="flex items-center justify-between rounded-lg border p-4">
                            <div className="space-y-0.5">
                              <p className="text-sm font-medium">
                                {t('pipelines.copyPipelineAction')}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                {t('pipelines.copyPipelineHint')}
                              </p>
                            </div>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={handleCopy}
                            >
                              <Copy className="size-4 mr-1.5" />
                              {t('common.copy')}
                            </Button>
                          </div>
                        )}
                      </CardContent>
                    </Card>

                    {/* Danger Zone (edit mode only) */}
                    {isEditMode && (
                      <Card className="border-destructive/50">
                        <CardHeader>
                          <CardTitle className="text-destructive">
                            {t('pipelines.dangerZone')}
                          </CardTitle>
                          <CardDescription>
                            {t('pipelines.dangerZoneDescription')}
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="flex items-center justify-between">
                            <div className="space-y-1">
                              <p className="text-sm font-medium">
                                {t('pipelines.deletePipelineAction')}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                {isDefaultPipeline
                                  ? t('pipelines.defaultPipelineCannotDelete')
                                  : t('pipelines.deletePipelineHint')}
                              </p>
                            </div>
                            <Button
                              type="button"
                              variant="destructive"
                              size="sm"
                              disabled={isDefaultPipeline}
                              onClick={handleDelete}
                            >
                              <Trash2 className="size-4 mr-1.5" />
                              {t('common.delete')}
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                )}

                {isEditMode && activeSection === 'workflow' && (
                  <div className="space-y-4">
                    <Card>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-base">数字员工配置方式</CardTitle>
                        <CardDescription>
                          模板配置是简单 Agent 配置，适合业务团队快速上手；工作流编排适合精细调整节点和连线。
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="inline-flex rounded-lg border bg-muted/40 p-1">
                          {[
                            ['template', '模板配置'],
                            ['workflow', '工作流编排'],
                          ].map(([mode, label]) => (
                            <Button
                              key={mode}
                              type="button"
                              size="sm"
                              variant={
                                selectedConfigMode === mode
                                  ? 'default'
                                  : 'ghost'
                              }
                              onClick={() =>
                                handleConfigModeChange(mode as 'template' | 'workflow')
                              }
                            >
                              {label}
                            </Button>
                          ))}
                        </div>
                      </CardContent>
                    </Card>

                    {selectedConfigMode === 'template' ? (
                      <PipelineTemplateConfigEditor
                        value={form.watch('template_config') as PipelineTemplateConfig}
                        onChange={handleTemplateConfigChange}
                      />
                    ) : (
                      <PipelineWorkflowEditor
                        value={form.watch('workflow') as PipelineWorkflow}
                        onChange={setWorkflowValue}
                      />
                    )}
                  </div>
                )}
              </div>
            </div>
          </form>
          {/* Button bar pinned to bottom */}
          {showButtons && (
            <div className="flex justify-end items-center gap-2 pt-4 border-t mb-0 sticky bottom-0 z-10">
              {isEditMode && hasUnsavedChanges && (
                <div className="text-amber-600 dark:text-amber-400 text-sm flex items-center gap-1.5 mr-auto">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500" />
                  {t('pipelines.unsavedChanges')}
                </div>
              )}

              {isEditMode && !isDefaultPipeline && (
                <Button
                  type="button"
                  variant="destructive"
                  onClick={handleDelete}
                >
                  {t('common.delete')}
                </Button>
              )}

              {isEditMode && isDefaultPipeline && (
                <div className="text-muted-foreground text-sm h-full flex items-center mr-2">
                  {t('pipelines.defaultPipelineCannotDelete')}
                </div>
              )}

              {isEditMode && (
                <Button
                  type="button"
                  variant="default"
                  onClick={handleCopy}
                  className="bg-green-600 hover:bg-green-700 text-white"
                >
                  {t('common.copy')}
                </Button>
              )}

              <Button type="submit" form="pipeline-form">
                {isEditMode ? t('common.save') : t('common.submit')}
              </Button>
            </div>
          )}
        </Form>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">{t('pipelines.deleteConfirmation')}</div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirm(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Copy confirmation dialog */}
      <Dialog open={showCopyConfirm} onOpenChange={setShowCopyConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('pipelines.copyConfirmTitle')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">{t('pipelines.copyConfirmation')}</div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCopyConfirm(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={confirmCopy}>{t('common.confirm')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
interface SectionItem {
  label: string;
  name: string;
  icon: ElementType;
}
