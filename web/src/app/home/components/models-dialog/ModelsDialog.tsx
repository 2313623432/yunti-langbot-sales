import { useState, useEffect, useMemo } from 'react';
import {
  Plus,
  MessageSquareText,
  Volume2,
  Settings,
  KeyRound,
  Link2,
} from 'lucide-react';
import { httpClient, systemInfo } from '@/app/infra/http/HttpClient';
import { LLMModel, ModelProvider } from '@/app/infra/entities/api';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import ProviderForm from './component/provider-form/ProviderForm';
import { AddModelPopover, ModelItem } from './components';
import {
  ExtraArg,
  ModelType,
  ScanModelsResult,
  SelectedScannedModel,
  TestResult,
  ProviderModels,
  LANGBOT_MODELS_PROVIDER_REQUESTER,
} from './types';
import { CustomApiError } from '@/app/infra/entities/common';

interface ModelsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type ExtraArgValue = string | number | boolean | Record<string, unknown>;

function convertExtraArgsToObject(
  args: ExtraArg[],
): Record<string, ExtraArgValue> {
  const obj: Record<string, ExtraArgValue> = {};
  args.forEach((arg) => {
    if (!arg.key.trim()) return;
    if (arg.type === 'number') {
      obj[arg.key] = Number(arg.value);
    } else if (arg.type === 'boolean') {
      obj[arg.key] = arg.value === 'true';
    } else if (arg.type === 'object') {
      const raw = arg.value.trim() || '{}';
      let parsed: unknown;
      try {
        parsed = JSON.parse(raw);
      } catch {
        throw new Error(`Invalid JSON for extra parameter "${arg.key}"`);
      }
      if (
        parsed === null ||
        typeof parsed !== 'object' ||
        Array.isArray(parsed)
      ) {
        throw new Error(`Extra parameter "${arg.key}" must be a JSON object`);
      }
      obj[arg.key] = parsed as Record<string, unknown>;
    } else {
      obj[arg.key] = arg.value;
    }
  });
  return obj;
}

export default function ModelsDialog({
  open,
  onOpenChange,
}: ModelsDialogProps) {
  const { t } = useTranslation();

  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [providerModels, setProviderModels] = useState<
    Record<string, ProviderModels>
  >({});
  const [loadingProviders, setLoadingProviders] = useState<Set<string>>(
    new Set(),
  );

  // Provider form modal
  const [providerFormOpen, setProviderFormOpen] = useState(false);
  const [editingProviderId, setEditingProviderId] = useState<string | null>(
    null,
  );

  // Popover states
  const [addModelPopoverOpen, setAddModelPopoverOpen] = useState<string | null>(
    null,
  );
  const [editModelPopoverOpen, setEditModelPopoverOpen] = useState<
    string | null
  >(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState<string | null>(
    null,
  );

  // Form states
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [modelCategory, setModelCategory] = useState<'text' | 'voice'>('text');
  const [selectedProviderUuid, setSelectedProviderUuid] = useState<string | null>(
    null,
  );
  const [addModelMode, setAddModelMode] = useState<'manual' | 'scan'>('manual');

  // Separate LangBot Models provider (hide when models service is disabled)
  const langbotProvider = systemInfo.disable_models_service
    ? undefined
    : providers.find((p) => p.requester === LANGBOT_MODELS_PROVIDER_REQUESTER);
  const otherProviders = useMemo(
    () =>
      providers.filter(
        (p) => p.requester !== LANGBOT_MODELS_PROVIDER_REQUESTER,
      ),
    [providers],
  );
  const displayProviders = useMemo(
    () =>
      langbotProvider ? [langbotProvider, ...otherProviders] : otherProviders,
    [langbotProvider, otherProviders],
  );
  const hasLoadedProviderModels = displayProviders.some(
    (provider) => providerModels[provider.uuid],
  );
  const categoryProviders = useMemo(() => {
    if (!hasLoadedProviderModels) {
      return displayProviders;
    }
    return displayProviders.filter((provider) => {
      const models = providerModels[provider.uuid];
      if (!models) return true;
      return getModelsForCategory(provider).length > 0;
    });
  }, [displayProviders, hasLoadedProviderModels, providerModels, modelCategory]);
  const selectedProvider =
    categoryProviders.find((provider) => provider.uuid === selectedProviderUuid) ||
    categoryProviders[0];
  const selectedModels = selectedProvider
    ? providerModels[selectedProvider.uuid]
    : undefined;
  const selectedTextModels =
    selectedModels?.llm.filter((model) => !isVoiceOnlyModel(model)) || [];
  const selectedVoiceModels =
    selectedModels?.llm.filter((model) => model.abilities?.includes('tts')) || [];
  const visibleModels =
    modelCategory === 'voice' ? selectedVoiceModels : selectedTextModels;

  useEffect(() => {
    if (open) {
      loadProviders();
    }
  }, [open]);

  useEffect(() => {
    if (!open || categoryProviders.length === 0) return;
    if (
      !selectedProviderUuid ||
      !categoryProviders.some((provider) => provider.uuid === selectedProviderUuid)
    ) {
      setSelectedProviderUuid(categoryProviders[0].uuid);
    }
  }, [open, categoryProviders, selectedProviderUuid]);

  useEffect(() => {
    if (!selectedProvider || providerModels[selectedProvider.uuid]) return;
    loadProviderModels(selectedProvider.uuid);
  }, [selectedProvider?.uuid]);

  useEffect(() => {
    if (!open || displayProviders.length === 0) return;
    displayProviders.forEach((provider) => {
      if (!providerModels[provider.uuid]) {
        loadProviderModels(provider.uuid, true);
      }
    });
  }, [open, displayProviders]);

  async function loadProviders() {
    try {
      const resp = await httpClient.getModelProviders();
      setProviders(resp.providers);
    } catch (err) {
      console.error('Failed to load providers', err);
      toast.error(t('models.loadError'));
    }
  }

  async function loadProviderModels(providerUuid: string, silent = false) {
    if (loadingProviders.has(providerUuid)) return;

    setLoadingProviders((prev) => new Set(prev).add(providerUuid));
    try {
      const [llmResp, embeddingResp, rerankResp] = await Promise.all([
        httpClient.getProviderLLMModels(providerUuid),
        httpClient.getProviderEmbeddingModels(providerUuid),
        httpClient.getProviderRerankModels(providerUuid),
      ]);
      setProviderModels((prev) => ({
        ...prev,
        [providerUuid]: {
          llm: llmResp.models,
          embedding: embeddingResp.models,
          rerank: rerankResp.models,
        },
      }));
    } catch (err) {
      console.error('Failed to load models', err);
    } finally {
      setLoadingProviders((prev) => {
        const next = new Set(prev);
        next.delete(providerUuid);
        return next;
      });
    }
  }

  function handleCreateProvider() {
    setEditingProviderId(null);
    setProviderFormOpen(true);
  }

  function handleEditProvider(providerId: string) {
    setEditingProviderId(providerId);
    setProviderFormOpen(true);
  }

  async function handleAddModel(
    providerUuid: string,
    modelType: ModelType,
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) {
    if (!name.trim()) {
      toast.error(t('models.modelNameRequired'));
      return;
    }
    setIsSubmitting(true);
    try {
      const extraArgsObj = convertExtraArgsToObject(extraArgs);

      if (modelType === 'llm') {
        await httpClient.createProviderLLMModel({
          name,
          provider_uuid: providerUuid,
          abilities,
          extra_args: extraArgsObj,
        } as never);
      } else if (modelType === 'embedding') {
        await httpClient.createProviderEmbeddingModel({
          name,
          provider_uuid: providerUuid,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.createProviderRerankModel({
          name,
          provider_uuid: providerUuid,
          extra_args: extraArgsObj,
        } as never);
      }
      setAddModelPopoverOpen(null);
      loadProviderModels(providerUuid, true);
      loadProviders();
    } catch (err) {
      toast.error(t('models.createError') + (err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleScanModels(
    providerUuid: string,
    modelType?: ModelType,
  ): Promise<ScanModelsResult> {
    try {
      const resp = await httpClient.scanProviderModels(providerUuid, modelType);
      return {
        models: resp.models,
        debug: resp.debug,
      };
    } catch (err) {
      toast.error(t('models.getModelListError') + (err as CustomApiError).msg);
      return { models: [] };
    }
  }

  async function handleAddScannedModels(
    providerUuid: string,
    modelType: ModelType,
    models: SelectedScannedModel[],
  ) {
    if (models.length === 0) return;

    setIsSubmitting(true);
    try {
      for (const item of models) {
        const effectiveType = item.model.type || modelType;
        if (effectiveType === 'llm') {
          await httpClient.createProviderLLMModel({
            name: item.model.name,
            provider_uuid: providerUuid,
            abilities: item.abilities,
            extra_args: {},
          } as never);
        } else if (effectiveType === 'embedding') {
          await httpClient.createProviderEmbeddingModel({
            name: item.model.name,
            provider_uuid: providerUuid,
            extra_args: {},
          } as never);
        } else {
          await httpClient.createProviderRerankModel({
            name: item.model.name,
            provider_uuid: providerUuid,
            extra_args: {},
          } as never);
        }
      }
      setAddModelPopoverOpen(null);
      loadProviderModels(providerUuid, true);
      loadProviders();
      toast.success(
        t('models.addSelectedModelsSuccess', { count: models.length }),
      );
    } catch (err) {
      toast.error(t('models.createError') + (err as CustomApiError).msg);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleUpdateModel(
    providerUuid: string,
    modelId: string,
    modelType: ModelType,
    name: string,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) {
    if (!name.trim()) {
      toast.error(t('models.modelNameRequired'));
      return;
    }
    setIsSubmitting(true);
    try {
      const extraArgsObj = convertExtraArgsToObject(extraArgs);

      if (modelType === 'llm') {
        await httpClient.updateProviderLLMModel(modelId, {
          name,
          provider_uuid: providerUuid,
          abilities,
          extra_args: extraArgsObj,
        } as never);
      } else if (modelType === 'embedding') {
        await httpClient.updateProviderEmbeddingModel(modelId, {
          name,
          provider_uuid: providerUuid,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.updateProviderRerankModel(modelId, {
          name,
          provider_uuid: providerUuid,
          extra_args: extraArgsObj,
        } as never);
      }
      setEditModelPopoverOpen(null);
      loadProviderModels(providerUuid, true);
      loadProviders();
    } catch (err) {
      toast.error(t('models.saveError') + (err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteModel(
    providerUuid: string,
    modelId: string,
    modelType: ModelType,
  ) {
    try {
      if (modelType === 'llm') {
        await httpClient.deleteProviderLLMModel(modelId);
      } else if (modelType === 'embedding') {
        await httpClient.deleteProviderEmbeddingModel(modelId);
      } else {
        await httpClient.deleteProviderRerankModel(modelId);
      }
      toast.success(t('models.deleteSuccess'));
      loadProviderModels(providerUuid, true);
      loadProviders();
    } catch (err) {
      toast.error(t('models.deleteError') + (err as Error).message);
    }
  }

  async function handleTestModel(
    providerUuid: string,
    name: string,
    modelType: ModelType,
    abilities: string[],
    extraArgs: ExtraArg[],
  ) {
    setIsTesting(true);
    setTestResult(null);
    const startTime = Date.now();
    try {
      const extraArgsObj = convertExtraArgsToObject(extraArgs);

      // Get the provider info
      const provider = providers.find((p) => p.uuid === providerUuid);
      const providerData = {
        requester: provider?.requester || '',
        base_url: provider?.base_url || '',
        api_keys: provider?.api_keys || [],
      };

      if (modelType === 'llm') {
        await httpClient.testLLMModel('_', {
          uuid: '',
          name,
          provider_uuid: '',
          provider: providerData,
          abilities,
          extra_args: extraArgsObj,
        } as never);
      } else if (modelType === 'embedding') {
        await httpClient.testEmbeddingModel('_', {
          uuid: '',
          name,
          provider_uuid: '',
          provider: providerData,
          extra_args: extraArgsObj,
        } as never);
      } else {
        await httpClient.testRerankModel('_', {
          uuid: '',
          name,
          provider_uuid: '',
          provider: providerData,
          extra_args: extraArgsObj,
        } as never);
      }
      const duration = Date.now() - startTime;
      setTestResult({ success: true, duration });
    } catch (err) {
      console.error('Failed to test model', err);
      toast.error(t('models.testError') + ': ' + (err as CustomApiError).msg);
      setTestResult(null);
    } finally {
      setIsTesting(false);
    }
  }

  function handleFormClose() {
    setProviderFormOpen(false);
    loadProviders();
    if (selectedProviderUuid) {
      loadProviderModels(selectedProviderUuid, true);
    }
  }

  function isVoiceOnlyModel(model: LLMModel) {
    const abilities = model.abilities || [];
    return (
      abilities.includes('tts') &&
      abilities.every((ability) => ability === 'tts')
    );
  }

  function maskApiKey(key?: string) {
    if (!key) return '未配置';
    if (key.length <= 8) return '****';
    return `${key.slice(0, 4)}...${key.slice(-4)}`;
  }

  function providerRequestUrl(provider: ModelProvider) {
    const baseUrl = provider.base_url || '';
    if (!baseUrl) return '-';
    if (modelCategory === 'voice') {
      return baseUrl;
    }
    return baseUrl.replace(/\/$/, '').endsWith('/v1')
      ? `${baseUrl.replace(/\/$/, '')}/chat/completions`
      : baseUrl;
  }

  function relevantModelCount(provider: ModelProvider) {
    const models = providerModels[provider.uuid];
    if (!models) return provider.llm_count || 0;
    return getModelsForCategory(provider).length;
  }

  function getModelsForCategory(provider: ModelProvider) {
    const models = providerModels[provider.uuid];
    if (!models) return [];
    if (modelCategory === 'voice') {
      return models.llm.filter((model) => model.abilities?.includes('tts'));
    }
    return models.llm.filter((model) => !isVoiceOnlyModel(model));
  }

  function renderModelItem(model: LLMModel) {
    if (!selectedProvider) return null;
    return (
      <ModelItem
        key={model.uuid}
        model={model}
        modelType="llm"
        isLangBotModels={
          selectedProvider.requester === LANGBOT_MODELS_PROVIDER_REQUESTER
        }
        editModelPopoverOpen={editModelPopoverOpen}
        deleteConfirmOpen={deleteConfirmOpen}
        onOpenEditModel={(modelId) => setEditModelPopoverOpen(modelId)}
        onCloseEditModel={() => setEditModelPopoverOpen(null)}
        onOpenDeleteConfirm={(modelId) => setDeleteConfirmOpen(modelId)}
        onCloseDeleteConfirm={() => setDeleteConfirmOpen(null)}
        onDeleteModel={() =>
          handleDeleteModel(selectedProvider.uuid, model.uuid, 'llm')
        }
        onUpdateModel={(name, abilities, extraArgs) =>
          handleUpdateModel(
            selectedProvider.uuid,
            model.uuid,
            'llm',
            name,
            abilities,
            extraArgs,
          )
        }
        onTestModel={(name, abilities, extraArgs) =>
          handleTestModel(selectedProvider.uuid, name, 'llm', abilities, extraArgs)
        }
        isSubmitting={isSubmitting}
        isTesting={isTesting}
        testResult={testResult}
        onResetTestResult={() => setTestResult(null)}
      />
    );
  }

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(newOpen) => {
          if (!newOpen && providerFormOpen) return;
          onOpenChange(newOpen);
        }}
      >
        <DialogContent className="overflow-hidden p-0 h-[82vh] flex flex-col !max-w-[76rem]">
          <DialogHeader className="sr-only">
            <DialogTitle>{t('models.title')}</DialogTitle>
            <DialogDescription>
              Configure text and voice model providers.
            </DialogDescription>
          </DialogHeader>

          <div className="grid min-h-0 flex-1 grid-cols-[12rem_15rem_minmax(0,1fr)]">
            <aside className="border-r bg-slate-50/60 p-3">
              {[
                { key: 'text' as const, label: '文本模型', icon: MessageSquareText },
                { key: 'voice' as const, label: '语音合成', icon: Volume2 },
              ].map((item) => {
                const Icon = item.icon;
                const active = modelCategory === item.key;
                return (
                  <button
                    key={item.key}
                    type="button"
                    className={`mb-1 flex h-10 w-full items-center gap-2 rounded-md px-3 text-sm font-medium ${
                      active
                        ? 'bg-violet-100 text-violet-700'
                        : 'text-slate-700 hover:bg-slate-100'
                    }`}
                    onClick={() => setModelCategory(item.key)}
                  >
                    <Icon className="size-4" />
                    {item.label}
                  </button>
                );
              })}
            </aside>

            <aside className="flex min-h-0 flex-col border-r bg-white">
              <div className="flex-1 overflow-y-auto p-3">
                {categoryProviders.map((provider) => {
                  const active = selectedProvider?.uuid === provider.uuid;
                  return (
                    <button
                      key={provider.uuid}
                      type="button"
                      className={`mb-2 flex w-full min-w-0 items-center gap-3 rounded-md border px-3 py-3 text-left ${
                        active
                          ? 'border-violet-300 bg-violet-50 shadow-sm'
                          : 'border-transparent hover:bg-slate-50'
                      }`}
                      onClick={() => {
                        setSelectedProviderUuid(provider.uuid);
                        if (!providerModels[provider.uuid]) {
                          loadProviderModels(provider.uuid);
                        }
                      }}
                    >
                      <img
                        src={httpClient.getProviderRequesterIconURL(provider.requester)}
                        alt={provider.name}
                        className="size-7 shrink-0 rounded-md"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-slate-900">
                          {provider.name}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {relevantModelCount(provider)} 个模型
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
              <div className="border-t p-3">
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={handleCreateProvider}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  {t('models.addProvider')}
                </Button>
              </div>
            </aside>

            <main className="flex min-h-0 flex-col bg-white">
              {selectedProvider ? (
                <>
                  <div className="flex items-center justify-between border-b px-6 py-5">
                    <div className="flex min-w-0 items-center gap-3">
                      <img
                        src={httpClient.getProviderRequesterIconURL(selectedProvider.requester)}
                        alt={selectedProvider.name}
                        className="size-10 shrink-0 rounded-md"
                      />
                      <div className="min-w-0">
                        <div className="truncate text-xl font-semibold text-slate-950">
                          {selectedProvider.name}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {modelCategory === 'voice' ? '语音合成配置' : '文本模型配置'}
                        </div>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleEditProvider(selectedProvider.uuid)}
                    >
                      <Settings className="size-4" />
                    </Button>
                  </div>

                  <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                          <KeyRound className="size-4 text-muted-foreground" />
                          API 密钥
                        </div>
                        <div className="flex h-10 items-center rounded-md border bg-slate-50 px-3 text-sm text-muted-foreground">
                          {maskApiKey(selectedProvider.api_keys?.[0])}
                        </div>
                      </div>
                      <div>
                        <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                          <Link2 className="size-4 text-muted-foreground" />
                          接口地址
                        </div>
                        <div className="flex min-h-10 items-center rounded-md border bg-slate-50 px-3 py-2 text-sm text-muted-foreground">
                          <span className="break-all">{selectedProvider.base_url || '-'}</span>
                        </div>
                      </div>
                    </div>

                    <div className="mt-3 text-xs leading-5 text-muted-foreground">
                      <span className="rounded bg-violet-100 px-1 font-medium text-violet-700">
                        请求地址
                      </span>
                      <span className="ml-1 break-all">
                        {providerRequestUrl(selectedProvider)}
                      </span>
                    </div>

                    <div className="mt-8">
                      <div className="mb-3 flex items-center justify-between">
                        <div>
                          <h3 className="text-base font-semibold text-slate-950">
                            {modelCategory === 'voice' ? '语音模型' : '文本模型'}
                          </h3>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {modelCategory === 'voice'
                              ? '只展示已勾选语音合成能力的模型。'
                              : '只展示可用于对话和视觉理解的文本模型。'}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <AddModelPopover
                            isOpen={
                              addModelPopoverOpen === selectedProvider.uuid &&
                              addModelMode === 'manual'
                            }
                            initialMode="manual"
                            trigger={
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setAddModelMode('manual')}
                              >
                                <Plus className="mr-1 size-4" />
                                新建模型
                              </Button>
                            }
                            onOpen={() => {
                              setAddModelMode('manual');
                              setAddModelPopoverOpen(selectedProvider.uuid);
                            }}
                            onClose={() => setAddModelPopoverOpen(null)}
                            onAddModel={(modelType, name, abilities, extraArgs) =>
                              handleAddModel(
                                selectedProvider.uuid,
                                modelType,
                                name,
                                modelCategory === 'voice'
                                  ? Array.from(new Set([...abilities, 'tts']))
                                  : abilities,
                                extraArgs,
                              )
                            }
                            onScanModels={(modelType) =>
                              handleScanModels(selectedProvider.uuid, modelType)
                            }
                            onAddScannedModels={(modelType, models) =>
                              handleAddScannedModels(selectedProvider.uuid, modelType, models)
                            }
                            onTestModel={(name, modelType, abilities, extraArgs) =>
                              handleTestModel(
                                selectedProvider.uuid,
                                name,
                                modelType,
                                abilities,
                                extraArgs,
                              )
                            }
                            isSubmitting={isSubmitting}
                            isTesting={isTesting}
                            testResult={testResult}
                            onResetTestResult={() => setTestResult(null)}
                          />
                        </div>
                      </div>

                      {loadingProviders.has(selectedProvider.uuid) ? (
                        <p className="rounded-md border py-8 text-center text-sm text-muted-foreground">
                          {t('common.loading')}...
                        </p>
                      ) : visibleModels.length > 0 ? (
                        <div className="space-y-2">
                          {visibleModels.map((model) => renderModelItem(model))}
                        </div>
                      ) : (
                        <div className="rounded-md border border-dashed py-10 text-center">
                          <p className="text-sm text-muted-foreground">
                            {modelCategory === 'voice'
                              ? '暂无语音模型，请新增模型并勾选语音合成。'
                              : t('models.noModels')}
                          </p>
                          {modelCategory === 'voice' && (
                            <Badge variant="outline" className="mt-3">
                              {t('models.ttsAbility')}
                            </Badge>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
                  {t('models.noProviders')}
                </div>
              )}
            </main>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={providerFormOpen} onOpenChange={setProviderFormOpen}>
        <DialogContent className="w-[600px] p-6">
          <DialogHeader>
            <DialogTitle>
              {editingProviderId
                ? t('models.editProvider')
                : t('models.addProvider')}
            </DialogTitle>
          </DialogHeader>
          <ProviderForm
            providerId={editingProviderId || undefined}
            onFormSubmit={handleFormClose}
            onFormCancel={() => setProviderFormOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}
