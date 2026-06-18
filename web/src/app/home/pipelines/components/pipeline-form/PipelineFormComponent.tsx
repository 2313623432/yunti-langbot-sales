import { useEffect, useRef, useState, useMemo, type ElementType } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  GetPipelineResponseData,
  Pipeline,
  WorkflowProject,
} from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
  Workflow,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import PipelineTemplateConfigEditor from '@/app/home/pipelines/components/workflow-editor/PipelineTemplateConfigEditor';
import {
  createBlankAgentTemplateConfig,
  createDefaultWorkflow,
} from '@/app/home/pipelines/components/workflow-editor/workflowTemplates';
import {
  PipelineTemplateConfig,
  PipelineWorkflow,
} from '@/app/home/pipelines/components/workflow-editor/types';
import AgentAvatarPicker from '@/app/home/pipelines/components/agent-avatar/AgentAvatarPicker';
import { DEFAULT_AGENT_AVATAR } from '@/app/home/pipelines/components/agent-avatar/agentAvatar';

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

type PipelineCreateMode = 'custom' | 'workflow';

type WorkflowSource = {
  workflow_uuid?: string;
  workflow_name?: string;
  workflow_folder?: string;
};

function cloneWorkflow(workflow: PipelineWorkflow): PipelineWorkflow {
  if (typeof structuredClone === 'function') {
    return structuredClone(workflow);
  }
  return JSON.parse(JSON.stringify(workflow)) as PipelineWorkflow;
}

function applyRolePromptToWorkflow(
  workflow: PipelineWorkflow,
  rolePrompt: string,
): PipelineWorkflow {
  const nextWorkflow = cloneWorkflow(workflow);
  const normalizedRolePrompt = rolePrompt.trim();
  if (!normalizedRolePrompt) {
    return nextWorkflow;
  }

  nextWorkflow.metadata = {
    ...(nextWorkflow.metadata || {}),
    role_prompt: normalizedRolePrompt,
  };
  nextWorkflow.variables = {
    ...(nextWorkflow.variables || {}),
    role_prompt: normalizedRolePrompt,
  };
  nextWorkflow.nodes = nextWorkflow.nodes.map((node) => {
    if (node.type !== 'llm') {
      return node;
    }
    return {
      ...node,
      config: {
        ...node.config,
        prompt: normalizedRolePrompt,
      },
    };
  });
  return nextWorkflow;
}

async function syncRealScheduledPushBackend(templateConfig: PipelineTemplateConfig) {
  const backendSynced = templateConfig.metadata?.scheduled_push_backend_synced === true;
  const scheduledPush = templateConfig.scheduled_push;
  const items = scheduledPush?.items || [];
  if (!backendSynced || !items.length) {
    return;
  }

  const backendContext =
    (templateConfig.metadata?.scheduled_push_backend_context as
      | Record<string, unknown>
      | undefined) || {};
  await httpClient.saveSalesScheduledPushConfig({
    ...backendContext,
    scheduled_push: scheduledPush,
  });
}

export default function PipelineFormComponent({
  onFinish,
  onNewPipelineCreated,
  isEditMode,
  createMode = 'custom',
  pipelineId,
  showButtons = true,
  onDeletePipeline,
  onCancel,
  onDirtyChange,
}: {
  pipelineId?: string;
  isEditMode: boolean;
  createMode?: PipelineCreateMode;
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
  const [isWorkflowAnswerMode, setIsWorkflowAnswerMode] = useState(
    createMode === 'workflow',
  );
  const [workflowProjects, setWorkflowProjects] = useState<WorkflowProject[]>(
    [],
  );
  const [workflowProjectsLoading, setWorkflowProjectsLoading] = useState(false);

  const formSchema = isEditMode
    ? z.object({
        basic: z.object({
          name: z.string().min(1, { message: t('pipelines.nameRequired') }),
          description: z.string().optional(),
          emoji: z.string().optional(),
          avatar: z.string().optional(),
        }),
        ai: z.record(z.string(), z.any()),
        trigger: z.record(z.string(), z.any()),
        safety: z.record(z.string(), z.any()),
        output: z.record(z.string(), z.any()),
        config_mode: z.enum(['template', 'workflow']).optional(),
        template_config: z.any().optional(),
        role_prompt: z.string().optional(),
        workflow_source: z
          .object({
            workflow_uuid: z.string().optional(),
            workflow_name: z.string().optional(),
            workflow_folder: z.string().optional(),
          })
          .optional(),
        workflow: z.any(),
      })
    : z.object({
        basic: z.object({
          name: z.string().min(1, { message: t('pipelines.nameRequired') }),
          description: z.string().optional(),
          emoji: z.string().optional(),
          avatar: z.string().optional(),
        }),
        ai: z.record(z.string(), z.any()).optional(),
        trigger: z.record(z.string(), z.any()).optional(),
        safety: z.record(z.string(), z.any()).optional(),
        output: z.record(z.string(), z.any()).optional(),
        config_mode: z.enum(['template', 'workflow']).optional(),
        template_config: z.any().optional(),
        role_prompt: z.string().optional(),
        workflow_source: z
          .object({
            workflow_uuid: z.string().optional(),
            workflow_name: z.string().optional(),
            workflow_folder: z.string().optional(),
          })
          .optional(),
        workflow: z.any().optional(),
      });

  type FormValues = z.infer<typeof formSchema>;
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      basic: {
        name: '',
        description: '',
        emoji: createMode === 'workflow' ? '🔁' : '⚙️',
        avatar: DEFAULT_AGENT_AVATAR,
      },
      ai: {},
      trigger: {},
      safety: {},
      output: {},
      config_mode: createMode === 'workflow' ? 'workflow' : 'template',
      template_config: createBlankAgentTemplateConfig(),
      role_prompt: '',
      workflow_source: {
        workflow_uuid: '',
        workflow_name: '',
        workflow_folder: '',
      },
      workflow: createDefaultWorkflow(),
    },
  });

  // Section navigation items with icons
  const SECTION_ICONS: Record<string, ElementType> = {
    basic: Info,
    workflow: Workflow,
  };

  const formLabelList: SectionItem[] = isWorkflowAnswerMode
    ? [
        {
          label: '基本信息',
          name: 'basic',
          icon: SECTION_ICONS.basic,
        },
        {
          label: '工作流绑定',
          name: 'workflow',
          icon: SECTION_ICONS.workflow,
        },
      ]
    : isEditMode
      ? [
          {
            label: 'Agent配置',
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
  const workflowSource = form.watch('workflow_source') as
    | WorkflowSource
    | undefined;
  const selectedWorkflowUuid = workflowSource?.workflow_uuid || '';
  const selectedWorkflowProject = workflowProjects.find(
    (project) => project.uuid === selectedWorkflowUuid,
  );
  const currentTemplateConfig =
    (form.watch('template_config') as PipelineTemplateConfig | undefined) ||
    createBlankAgentTemplateConfig();
  const boundWorkflowName =
    selectedWorkflowProject?.name || workflowSource?.workflow_name || '';
  const boundWorkflowFolder =
    selectedWorkflowProject?.folder || workflowSource?.workflow_folder || '';

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
    if (!formLabelList.some((section) => section.name === activeSection)) {
      setActiveSection(formLabelList[0].name);
    }
  }, [activeSection, formLabelList]);

  useEffect(() => {
    if (isEditMode) {
      return;
    }
    setIsWorkflowAnswerMode(createMode === 'workflow');
    setActiveSection('basic');
  }, [createMode, isEditMode]);

  useEffect(() => {
    if (!isWorkflowAnswerMode) {
      return;
    }

    let cancelled = false;
    setWorkflowProjectsLoading(true);
    httpClient
      .getWorkflows()
      .then((data) => {
        if (cancelled) return;
        setWorkflowProjects(data.workflows || []);
      })
      .catch((error) => {
        toast.error(`工作流加载失败${error?.msg ? `：${error.msg}` : ''}`);
      })
      .finally(() => {
        if (!cancelled) {
          setWorkflowProjectsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isWorkflowAnswerMode]);

  useEffect(() => {
    if (!isEditMode || !pipelineId) {
      return;
    }

    let cancelled = false;
    httpClient
      .getPipeline(pipelineId || '')
      .then((resp: GetPipelineResponseData) => {
        if (cancelled) {
          return;
        }

        setIsDefaultPipeline(resp.pipeline.is_default ?? false);
        const pipelineConfig = resp.pipeline.config as Record<string, any>;
        const basicConfig = pipelineConfig.basic || {};
        const aiConfig = pipelineConfig.ai || {};
        const configMode: 'template' | 'workflow' =
          pipelineConfig.config_mode === 'workflow' ? 'workflow' : 'template';
        setIsWorkflowAnswerMode(configMode === 'workflow');
        const templateConfig =
          (pipelineConfig.template_config as PipelineTemplateConfig | undefined) ||
          createBlankAgentTemplateConfig();
        const workflowConfig =
          (pipelineConfig.workflow as PipelineWorkflow | undefined) ||
          createDefaultWorkflow();
        const workflowSource =
          (pipelineConfig.workflow_source as WorkflowSource | undefined) || {};
        const rolePrompt =
          typeof pipelineConfig.role_prompt === 'string'
            ? pipelineConfig.role_prompt
            : templateConfig.role_prompt || '';
        const loadedValues = {
          basic: {
            name: resp.pipeline.name,
            description: resp.pipeline.description,
            emoji: resp.pipeline.emoji || '⚙️',
            avatar: basicConfig.avatar || DEFAULT_AGENT_AVATAR,
          },
          ai: aiConfig,
          trigger: pipelineConfig.trigger || {},
          safety: pipelineConfig.safety || {},
          output: pipelineConfig.output || {},
          config_mode: configMode,
          template_config: templateConfig,
          role_prompt: rolePrompt,
          workflow_source: {
            workflow_uuid: workflowSource.workflow_uuid || '',
            workflow_name: workflowSource.workflow_name || '',
            workflow_folder: workflowSource.workflow_folder || '',
          },
          workflow: workflowConfig,
        };
        form.reset(loadedValues);
        savedSnapshotRef.current = JSON.stringify(loadedValues);
      });

    return () => {
      cancelled = true;
    };
  }, [form, isEditMode, pipelineId]);

  useEffect(() => {
    if (!isEditMode) {
      form.reset({
        basic: {
          name: '',
          description: '',
          emoji: createMode === 'workflow' ? '🔁' : '⚙️',
          avatar: DEFAULT_AGENT_AVATAR,
        },
        config_mode: createMode === 'workflow' ? 'workflow' : 'template',
        template_config: createBlankAgentTemplateConfig(),
        role_prompt: '',
        workflow_source: {
          workflow_uuid: '',
          workflow_name: '',
          workflow_folder: '',
        },
        workflow: createDefaultWorkflow(),
      });
    }
  }, [createMode, form, isEditMode]);

  function handleFormSubmit(values: FormValues) {
    if (isEditMode) {
      handleModify(values);
    } else {
      handleCreate(values);
    }
  }

  function handleCreate(values: FormValues) {
    if (createMode === 'workflow') {
      const templateConfig =
        (values.template_config as PipelineTemplateConfig | undefined) ||
        createBlankAgentTemplateConfig();
      const rolePrompt = values.role_prompt || '';
      const baseWorkflow =
        (selectedWorkflowProject?.workflow as PipelineWorkflow | undefined) ||
        (values.workflow as PipelineWorkflow | undefined) ||
        createDefaultWorkflow();
      const pipeline: Pipeline = {
        config: {
          basic: {
            avatar: values.basic.avatar || DEFAULT_AGENT_AVATAR,
          },
          ai: syncTemplateModelIntoAIConfig(templateConfig, values.ai),
          config_mode: 'workflow',
          template_config: templateConfig,
          role_prompt: rolePrompt,
          workflow_source: {
            workflow_uuid: selectedWorkflowProject?.uuid || '',
            workflow_name: selectedWorkflowProject?.name || '',
            workflow_folder: selectedWorkflowProject?.folder || '',
          },
          workflow: applyRolePromptToWorkflow(baseWorkflow, rolePrompt),
        },
        description: values.basic.description ?? '',
        name: values.basic.name,
        emoji: values.basic.emoji,
      };
      httpClient
        .createPipeline(pipeline)
        .then(async (resp) => {
          await syncRealScheduledPushBackend(templateConfig);
          onFinish();
          onNewPipelineCreated(resp.uuid);
          toast.success(t('pipelines.createSuccess'));
        })
        .catch((err) => {
          toast.error(t('pipelines.createError') + err.msg);
        });
      return;
    }

    const templateConfig =
      (values.template_config as PipelineTemplateConfig | undefined) ||
      createBlankAgentTemplateConfig();
    const pipeline: Pipeline = {
      config: {
        basic: {
          avatar: values.basic.avatar || DEFAULT_AGENT_AVATAR,
        },
        config_mode: 'template',
        template_config: templateConfig,
        workflow: (values.workflow as PipelineWorkflow | undefined) || createDefaultWorkflow(),
      },
      description: values.basic.description ?? '',
      name: values.basic.name,
      emoji: values.basic.emoji,
    };
    httpClient
      .createPipeline(pipeline)
      .then(async (resp) => {
        await syncRealScheduledPushBackend(templateConfig);
        onFinish();
        onNewPipelineCreated(resp.uuid);
        toast.success(t('pipelines.createSuccess'));
      })
      .catch((err) => {
        toast.error(t('pipelines.createError') + err.msg);
      });
  }

  function handleModify(values: FormValues) {
    const configMode = isWorkflowAnswerMode ? 'workflow' : 'template';
    if (configMode === 'workflow') {
      const workflowSource = (values.workflow_source as WorkflowSource) || {};
      const templateConfig =
        (values.template_config as PipelineTemplateConfig | undefined) ||
        createBlankAgentTemplateConfig();
      const rolePrompt = values.role_prompt || '';
      const baseWorkflow =
        (selectedWorkflowProject?.workflow as PipelineWorkflow | undefined) ||
        (values.workflow as PipelineWorkflow | undefined) ||
        createDefaultWorkflow();
      const realConfig = {
        basic: {
          avatar: values.basic.avatar || DEFAULT_AGENT_AVATAR,
        },
        ai: syncTemplateModelIntoAIConfig(templateConfig, values.ai),
        trigger: values.trigger,
        safety: values.safety,
        output: values.output,
        config_mode: 'workflow',
        template_config: templateConfig,
        role_prompt: rolePrompt,
        workflow_source: workflowSource,
        workflow: applyRolePromptToWorkflow(baseWorkflow, rolePrompt),
      };

      const pipeline: Pipeline = {
        config: realConfig,
        description: values.basic.description ?? '',
        name: values.basic.name,
        emoji: values.basic.emoji,
      };
      httpClient
        .updatePipeline(pipelineId || '', pipeline)
        .then(async () => {
          await syncRealScheduledPushBackend(templateConfig);
          savedSnapshotRef.current = JSON.stringify(form.getValues());
          onFinish();
          toast.success(t('pipelines.saveSuccess'));
        })
        .catch((err) => {
          toast.error(t('pipelines.saveError') + err.msg);
        });
      return;
    }

    const templateConfig =
      (values.template_config as PipelineTemplateConfig | undefined) ||
      createBlankAgentTemplateConfig();
    const baseWorkflow = (values.workflow as PipelineWorkflow | undefined) || createDefaultWorkflow();
    const workflow = baseWorkflow;
    const realConfig = {
      basic: {
        avatar: values.basic.avatar || DEFAULT_AGENT_AVATAR,
      },
      ai: syncTemplateModelIntoAIConfig(templateConfig, values.ai),
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
      .then(async () => {
        await syncRealScheduledPushBackend(templateConfig);
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

  function handleTemplateConfigChange(templateConfig: PipelineTemplateConfig) {
    form.setValue('template_config', templateConfig, { shouldDirty: true });
  }

  function handleWorkflowProjectChange(workflowUuid: string) {
    const project = workflowProjects.find((item) => item.uuid === workflowUuid);
    if (!project) {
      return;
    }
    form.setValue(
      'workflow_source',
      {
        workflow_uuid: project.uuid,
        workflow_name: project.name,
        workflow_folder: project.folder,
      },
      { shouldDirty: true },
    );
    form.setValue('workflow', cloneWorkflow(project.workflow as PipelineWorkflow), {
      shouldDirty: true,
    });
  }

  function renderWorkflowBasicSettings() {
    return (
      <div className="space-y-5 rounded-lg border border-slate-200 bg-white p-6">
        <div>
          <h3 className="text-base font-semibold text-slate-950">基本信息</h3>
          <p className="mt-1 text-sm text-slate-500">
            设置数字员工对客户展示的名称、头像、描述和首次开场白。
          </p>
        </div>
        <FormField
          control={form.control}
          name="basic.avatar"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Agent头像</FormLabel>
              <FormControl>
                <AgentAvatarPicker
                  value={field.value}
                  onChange={field.onChange}
                  uploadInputId="workflow-agent-avatar-upload"
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="basic.name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                数字员工名称<span className="text-destructive">*</span>
              </FormLabel>
              <FormControl>
                <Input
                  {...field}
                  placeholder="例如：课程顾问、售后助手、订单客服"
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="basic.description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>描述</FormLabel>
              <FormControl>
                <Input
                  {...field}
                  placeholder="说明这个数字员工负责的客户场景"
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="template_config.opening_message"
          render={({ field }) => (
            <FormItem>
              <FormLabel>首次开场白</FormLabel>
              <FormControl>
                <Textarea
                  {...field}
                  value={field.value || ''}
                  className="min-h-[150px]"
                  placeholder="输入客户第一次看到的开场消息，可包含引导语、链接或下一步操作。"
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>
    );
  }

  function renderWorkflowBindingSettings() {
    return (
      <div className="space-y-5 rounded-lg border border-slate-200 bg-white p-6">
        <div>
          <h3 className="text-base font-semibold text-slate-950">
            工作流绑定
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            从工作流库选择一个流程，数字员工会按该流程组织回复。
          </p>
        </div>
        <FormItem>
          <FormLabel>绑定工作流</FormLabel>
          <Select
            value={selectedWorkflowUuid || undefined}
            onValueChange={handleWorkflowProjectChange}
            disabled={workflowProjectsLoading || workflowProjects.length === 0}
          >
            <FormControl>
              <SelectTrigger className="h-11 w-full border-slate-200 bg-white">
                <SelectValue
                  placeholder={
                    workflowProjectsLoading
                      ? '正在加载工作流...'
                      : '选择要绑定的工作流'
                  }
                />
              </SelectTrigger>
            </FormControl>
            <SelectContent>
              {workflowProjects.map((project) => (
                <SelectItem
                  key={project.uuid}
                  value={project.uuid}
                  description={project.description}
                >
                  {project.folder
                    ? `${project.folder} / ${project.name}`
                    : project.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FormMessage />
        </FormItem>

        {workflowProjectsLoading && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
            正在加载工作流...
          </div>
        )}

        {!workflowProjectsLoading && workflowProjects.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
            工作流库暂无可选工作流，请先在侧边栏工作流中创建。
          </div>
        )}

        {(selectedWorkflowProject || boundWorkflowName) && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
            <div className="text-sm font-medium text-slate-900">
              {boundWorkflowName}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {boundWorkflowFolder || '未分组'}
            </div>
            {selectedWorkflowProject?.description && (
              <p className="mt-3 text-sm leading-6 text-slate-500">
                {selectedWorkflowProject.description}
              </p>
            )}
          </div>
        )}
      </div>
    );
  }

  function renderWorkflowPreview() {
    const avatar = form.watch('basic.avatar') || DEFAULT_AGENT_AVATAR;
    const name = form.watch('basic.name') || '未命名数字员工';
    const openingMessage = currentTemplateConfig.opening_message || '';
    return (
      <aside className="flex min-h-0 flex-col border-t border-slate-200 bg-white lg:border-l lg:border-t-0">
        <div className="border-b border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-950">预览调试</h2>
          <p className="mt-1 text-sm text-slate-500">
            模拟客户看到的开场、绑定流程和回复效果
          </p>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <img
                src={avatar}
                alt=""
                className="size-12 rounded-full border border-slate-100 object-cover"
              />
              <div>
                <div className="font-semibold text-slate-950">{name}</div>
                <div className="text-sm text-emerald-600">在线 · 可调试</div>
              </div>
            </div>
          </div>
          <div className="mt-5 flex gap-3">
            <img
              src={avatar}
              alt=""
              className="mt-1 size-8 rounded-full border border-slate-100 object-cover"
            />
            <div className="max-w-[320px] rounded-lg bg-slate-100 px-4 py-3 text-sm leading-6 text-slate-700">
              {openingMessage || '开场白会显示在这里'}
            </div>
          </div>
          <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
              <Workflow className="size-4 text-blue-600" />
              {boundWorkflowName || '尚未绑定工作流'}
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              {boundWorkflowName
                ? `${boundWorkflowFolder || '未分组'} · 保存后按该工作流执行回答`
                : '切换到工作流绑定 tab，选择一个已有工作流。'}
            </p>
          </div>
        </div>
      </aside>
    );
  }

  function renderWorkflowAnswerEditor() {
    return (
      <div className="flex-1 overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
        <div className="grid h-full min-h-[640px] lg:grid-cols-[minmax(0,1fr)_420px]">
          <div className="flex min-h-0 flex-col">
            <div className="border-b border-slate-200 bg-white px-6 py-5">
              <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1">
                {formLabelList.map((section) => {
                  const Icon = section.icon;
                  return (
                    <button
                      key={section.name}
                      type="button"
                      onClick={() => setActiveSection(section.name)}
                      className={cn(
                        'flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors',
                        activeSection === section.name
                          ? 'bg-blue-50 text-blue-700 shadow-sm'
                          : 'text-slate-600 hover:bg-white hover:text-slate-900',
                      )}
                    >
                      <Icon className="size-4" />
                      {section.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-6">
              {activeSection === 'basic'
                ? renderWorkflowBasicSettings()
                : renderWorkflowBindingSettings()}
            </div>
          </div>
          {renderWorkflowPreview()}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="h-full p-0 flex flex-col">
        <Form {...form}>
          <form
            id="pipeline-form"
            onSubmit={form.handleSubmit(handleFormSubmit)}
            className="h-full flex flex-col flex-1 min-h-0 mb-2"
          >
            {isWorkflowAnswerMode ? (
              renderWorkflowAnswerEditor()
            ) : (
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
                    ? 'flex flex-col overflow-hidden'
                    : 'overflow-y-auto',
                )}
              >
                {/* Basic info section */}
                {activeSection === 'basic' && (
                  <div className="space-y-6">
                    {/* Basic Information Card */}
                    <Card>
                      <CardHeader>
                        <CardTitle>
                          {isWorkflowAnswerMode
                            ? '基本信息'
                            : t('pipelines.basicInfo')}
                        </CardTitle>
                        <CardDescription>
                          设置数字员工名称、头像和描述
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <FormField
                          control={form.control}
                          name="basic.avatar"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Agent头像</FormLabel>
                              <FormControl>
                                <AgentAvatarPicker
                                  value={field.value}
                                  onChange={field.onChange}
                                  uploadInputId="create-agent-avatar-upload"
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        <FormField
                          control={form.control}
                          name="basic.name"
                          render={({ field }) => (
                            <FormItem>
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

                      </CardContent>
                    </Card>
                  </div>
                )}

                {isEditMode &&
                  !isWorkflowAnswerMode &&
                  activeSection === 'workflow' && (
                  <div className="flex h-full min-h-0 flex-col">
                    <PipelineTemplateConfigEditor
                      value={form.watch('template_config') as PipelineTemplateConfig}
                      pipelineId={pipelineId}
                      hasUnsavedChanges={hasUnsavedChanges}
                      pipelineName={form.watch('basic.name')}
                      pipelineDescription={form.watch('basic.description')}
                      pipelineAvatar={form.watch('basic.avatar')}
                      onPipelineNameChange={(name) =>
                        form.setValue('basic.name', name, {
                          shouldDirty: true,
                        })
                      }
                      onPipelineDescriptionChange={(description) =>
                        form.setValue('basic.description', description, {
                          shouldDirty: true,
                        })
                      }
                      onPipelineAvatarChange={(avatar) =>
                        form.setValue('basic.avatar', avatar, {
                          shouldDirty: true,
                        })
                      }
                      onChange={handleTemplateConfigChange}
                    />
                  </div>
                )}
              </div>
            </div>
            )}
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

              {isEditMode && isDefaultPipeline && (
                <div className="text-muted-foreground text-sm h-full flex items-center mr-2">
                  {t('pipelines.defaultPipelineCannotDelete')}
                </div>
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
