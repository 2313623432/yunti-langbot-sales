import { useState, useEffect, useMemo } from 'react';
import {
  Plus,
  MessageSquareText,
  Volume2,
  Cpu,
  FileText,
  Settings,
  KeyRound,
  Link2,
  Trash2,
} from 'lucide-react';
import { httpClient, systemInfo } from '@/app/infra/http/HttpClient';
import { EmbeddingModel, LLMModel, ModelProvider } from '@/app/infra/entities/api';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
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
import { providerRequestUrl } from './providerRequestUrl';
import {
  getProtocolLabelKey,
  resolveProviderProtocol,
} from './protocolUtils';

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
  const [modelCategory, setModelCategory] = useState<'text' | 'voice' | 'embedding' | 'pdf'>(
    'text',
  );
  const [selectedProviderUuid, setSelectedProviderUuid] = useState<string | null>(
    null,
  );
  const [addModelMode, setAddModelMode] = useState<'manual' | 'scan'>('manual');
  const [requesterSupportTypes, setRequesterSupportTypes] = useState<
    Record<string, string[]>
  >({});
  const [deleteProviderConfirmOpen, setDeleteProviderConfirmOpen] =
    useState(false);

  // Separate LangBot Models provider (hide when models service is disabled)
  const langbotProvider = systemInfo.disable_models_service
    ? undefined
    : providers.find((p) => p.requester === LANGBOT_MODELS_PROVIDER_REQUESTER);
  const otherProviders = useMemo(
    () =>
      providers
        .filter((p) => p.requester !== LANGBOT_MODELS_PROVIDER_REQUESTER)
        .sort((a, b) => {
          const aOrder = a.is_builtin ? (a.sort_order ?? 999) : 10_000;
          const bOrder = b.is_builtin ? (b.sort_order ?? 999) : 10_000;
          if (aOrder !== bOrder) return aOrder - bOrder;
          return a.name.localeCompare(b.name);
        }),
    [providers],
  );
  const displayProviders = useMemo(
    () =>
      langbotProvider ? [langbotProvider, ...otherProviders] : otherProviders,
    [langbotProvider, otherProviders],
  );
  const categoryProviders = useMemo(() => {
    return displayProviders.filter((provider) =>
      providerBelongsToCategory(provider, modelCategory),
    );
  }, [displayProviders, providerModels, modelCategory, requesterSupportTypes]);
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
  const selectedEmbeddingModels = selectedModels?.embedding || [];
  const selectedPdfModels =
    selectedModels?.llm.filter((model) => model.abilities?.includes('pdf_parse')) || [];
  const visibleLlmModels =
    modelCategory === 'voice'
      ? selectedVoiceModels
      : modelCategory === 'pdf'
        ? selectedPdfModels
        : selectedTextModels;

  useEffect(() => {
    if (open) {
      loadProviders();
      loadRequesterSupportTypes();
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

  async function loadRequesterSupportTypes() {
    try {
      const resp = await httpClient.getProviderRequesters();
      const supportMap: Record<string, string[]> = {};
      resp.requesters.forEach((requester) => {
        const supportType = (
          requester.spec as { support_type?: string[] }
        ).support_type;
        supportMap[requester.name] = supportType || [];
      });
      setRequesterSupportTypes(supportMap);
    } catch (err) {
      console.error('Failed to load requester support types', err);
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

  function requesterSupportsCategory(
    requester: string,
    category: 'text' | 'voice' | 'embedding' | 'pdf',
  ) {
    const supportTypes = requesterSupportTypes[requester] || [];
    if (category === 'embedding') {
      return supportTypes.includes('text-embedding');
    }
    if (category === 'pdf') {
      return supportTypes.includes('pdf-parse');
    }
    return supportTypes.includes('llm');
  }

  function isPdfOnlyModel(model: LLMModel) {
    const abilities = model.abilities || [];
    return (
      abilities.includes('pdf_parse') &&
      abilities.every((ability) => ability === 'pdf_parse')
    );
  }

  function providerHasAnyModels(provider: ModelProvider) {
    const models = providerModels[provider.uuid];
    if (models) {
      return (
        models.llm.length > 0 ||
        models.embedding.length > 0 ||
        models.rerank.length > 0
      );
    }
    return (
      (provider.llm_count || 0) > 0 ||
      (provider.embedding_count || 0) > 0 ||
      (provider.rerank_count || 0) > 0
    );
  }

  function canDeleteProvider(provider: ModelProvider) {
    if (provider.is_builtin) {
      return false;
    }
    if (provider.requester === LANGBOT_MODELS_PROVIDER_REQUESTER) {
      return false;
    }
    return !providerHasAnyModels(provider);
  }

  function providerBelongsToCategory(
    provider: ModelProvider,
    category: 'text' | 'voice' | 'embedding' | 'pdf',
  ) {
    const models = providerModels[provider.uuid];
    if (models) {
      if (getModelsForCategory(provider, category).length > 0) {
        return true;
      }
      const totalModels =
        models.llm.length + models.embedding.length + models.rerank.length;
      if (totalModels === 0) {
        return requesterSupportsCategory(provider.requester, category);
      }
      return false;
    }

    if (category === 'embedding') {
      return (
        (provider.embedding_count || 0) > 0 ||
        (!providerHasAnyModels(provider) &&
          requesterSupportsCategory(provider.requester, category))
      );
    }
    if (category === 'voice' || category === 'pdf') {
      return (provider.llm_count || 0) > 0;
    }
    return (
      (provider.llm_count || 0) > 0 ||
      (!providerHasAnyModels(provider) &&
        requesterSupportsCategory(provider.requester, category))
    );
  }

  async function handleDeleteProvider(providerUuid: string) {
    try {
      await httpClient.deleteModelProvider(providerUuid);
      toast.success(t('models.providerDeleted'));
      setDeleteProviderConfirmOpen(false);
      setProviderModels((prev) => {
        const next = { ...prev };
        delete next[providerUuid];
        return next;
      });
      if (selectedProviderUuid === providerUuid) {
        setSelectedProviderUuid(null);
      }
      await loadProviders();
    } catch (err) {
      toast.error(
        t('models.providerDeleteError') + (err as CustomApiError).msg,
      );
    }
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
    if (!key) return t('models.apiKeyNotConfigured');
    if (key.length <= 8) return '****';
    return `${key.slice(0, 4)}...${key.slice(-4)}`;
  }

  function getProviderRequestUrl(provider: ModelProvider) {
    return providerRequestUrl(
      modelCategory,
      provider.requester || '',
      provider.base_url || '',
    );
  }

  function categoryConfigTitle() {
    if (modelCategory === 'voice') return t('models.voiceConfigTitle');
    if (modelCategory === 'embedding') return t('models.embeddingConfigTitle');
    if (modelCategory === 'pdf') return t('models.pdfConfigTitle');
    return t('models.textConfigTitle');
  }

  function categoryListTitle() {
    if (modelCategory === 'voice') return t('models.voiceListTitle');
    if (modelCategory === 'embedding') return t('models.embeddingListTitle');
    if (modelCategory === 'pdf') return t('models.pdfListTitle');
    return t('models.textListTitle');
  }

  function categoryListHint() {
    if (modelCategory === 'voice') return t('models.voiceListHint');
    if (modelCategory === 'embedding') return t('models.embeddingListHint');
    if (modelCategory === 'pdf') return t('models.pdfListHint');
    return t('models.textListHint');
  }

  function categoryEmptyHint() {
    if (modelCategory === 'voice') return t('models.noVoiceModels');
    if (modelCategory === 'embedding') return t('models.noEmbeddingModels');
    if (modelCategory === 'pdf') return t('models.noPdfModels');
    return t('models.noModels');
  }

  function relevantModelCount(provider: ModelProvider) {
    const models = providerModels[provider.uuid];
    if (!models) {
      if (modelCategory === 'embedding') return provider.embedding_count || 0;
      if (modelCategory === 'voice' || modelCategory === 'pdf') return provider.llm_count || 0;
      return provider.llm_count || 0;
    }
    return getModelsForCategory(provider, modelCategory).length;
  }

  function getModelsForCategory(
    provider: ModelProvider,
    category: 'text' | 'voice' | 'embedding' | 'pdf' = modelCategory,
  ) {
    const models = providerModels[provider.uuid];
    if (!models) return [];
    if (category === 'embedding') {
      return models.embedding;
    }
    if (category === 'voice') {
      return models.llm.filter((model) => model.abilities?.includes('tts'));
    }
    if (category === 'pdf') {
      return models.llm.filter((model) => model.abilities?.includes('pdf_parse'));
    }
    return models.llm.filter((model) => !isVoiceOnlyModel(model) && !isPdfOnlyModel(model));
  }

  function renderEmbeddingModelItem(model: EmbeddingModel) {
    if (!selectedProvider) return null;
    return (
      <ModelItem
        key={model.uuid}
        model={model}
        modelType="embedding"
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
          handleDeleteModel(selectedProvider.uuid, model.uuid, 'embedding')
        }
        onUpdateModel={(name, _abilities, extraArgs) =>
          handleUpdateModel(
            selectedProvider.uuid,
            model.uuid,
            'embedding',
            name,
            [],
            extraArgs,
          )
        }
        onTestModel={(name, _abilities, extraArgs) =>
          handleTestModel(
            selectedProvider.uuid,
            name,
            'embedding',
            [],
            extraArgs,
          )
        }
        isSubmitting={isSubmitting}
        isTesting={isTesting}
        testResult={testResult}
        onResetTestResult={() => setTestResult(null)}
      />
    );
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
                { key: 'text' as const, label: t('models.textCategory'), icon: MessageSquareText },
                { key: 'embedding' as const, label: t('models.embeddingCategory'), icon: Cpu },
                { key: 'voice' as const, label: t('models.voiceCategory'), icon: Volume2 },
                { key: 'pdf' as const, label: t('models.pdfCategory'), icon: FileText },
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
                          {t('models.modelsCount', {
                            count: relevantModelCount(provider),
                          })}
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
                        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                          <span>{categoryConfigTitle()}</span>
                          <Badge variant="outline" className="font-normal">
                            {t(
                              getProtocolLabelKey(
                                resolveProviderProtocol(selectedProvider),
                              ),
                            )}
                          </Badge>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {selectedProvider.is_builtin && (
                        <Badge variant="secondary" className="mr-1">
                          {t('models.builtinProvider')}
                        </Badge>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleEditProvider(selectedProvider.uuid)}
                      >
                        <Settings className="size-4" />
                      </Button>
                      {selectedProvider.requester !==
                        LANGBOT_MODELS_PROVIDER_REQUESTER &&
                        !selectedProvider.is_builtin && (
                        canDeleteProvider(selectedProvider) ? (
                          <Popover
                            open={deleteProviderConfirmOpen}
                            onOpenChange={setDeleteProviderConfirmOpen}
                          >
                            <PopoverTrigger asChild>
                              <Button variant="ghost" size="icon">
                                <Trash2 className="size-4 text-destructive" />
                              </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-64" align="end">
                              <div className="space-y-3">
                                <p className="text-sm">
                                  {t('models.deleteProviderConfirmation')}
                                </p>
                                <div className="flex justify-end gap-2">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() =>
                                      setDeleteProviderConfirmOpen(false)
                                    }
                                  >
                                    {t('common.cancel')}
                                  </Button>
                                  <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={() =>
                                      handleDeleteProvider(selectedProvider.uuid)
                                    }
                                  >
                                    {t('common.delete')}
                                  </Button>
                                </div>
                              </div>
                            </PopoverContent>
                          </Popover>
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon"
                            title={t('models.providerDeleteBlocked')}
                            onClick={() =>
                              toast.error(t('models.providerDeleteBlocked'))
                            }
                          >
                            <Trash2 className="size-4 text-muted-foreground" />
                          </Button>
                        )
                      )}
                    </div>
                  </div>

                  <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                          <KeyRound className="size-4 text-muted-foreground" />
                          {t('models.apiKey')}
                          {selectedProvider.api_key_required !== false && (
                            <span className="text-red-500">*</span>
                          )}
                        </div>
                        <div className="flex h-10 items-center rounded-md border bg-slate-50 px-3 text-sm text-muted-foreground">
                          {maskApiKey(selectedProvider.api_keys?.[0])}
                        </div>
                      </div>
                      <div>
                        <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                          <Link2 className="size-4 text-muted-foreground" />
                          {t('models.modelBaseURL')}
                        </div>
                        <div className="flex min-h-10 items-center rounded-md border bg-slate-50 px-3 py-2 text-sm text-muted-foreground">
                          <span className="break-all">{selectedProvider.base_url || '-'}</span>
                        </div>
                      </div>
                    </div>

                    <div className="mt-3 text-xs leading-5 text-muted-foreground">
                      <span className="rounded bg-violet-100 px-1 font-medium text-violet-700">
                        {t('models.requestURL')}
                      </span>
                      <span className="ml-1 break-all">
                        {getProviderRequestUrl(selectedProvider)}
                      </span>
                    </div>

                    <div className="mt-8">
                      <div className="mb-3 flex items-center justify-between">
                        <div>
                          <h3 className="text-base font-semibold text-slate-950">
                            {categoryListTitle()}
                          </h3>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {categoryListHint()}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <AddModelPopover
                            isOpen={
                              addModelPopoverOpen === selectedProvider.uuid &&
                              addModelMode === 'manual'
                            }
                            initialMode="manual"
                            defaultModelType={
                              modelCategory === 'embedding' ? 'embedding' : 'llm'
                            }
                            lockedModelType={
                              modelCategory === 'embedding' ? 'embedding' : undefined
                            }
                            trigger={
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setAddModelMode('manual')}
                              >
                                <Plus className="mr-1 size-4" />
                                {t('models.addModel')}
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
                                  : modelCategory === 'pdf'
                                    ? Array.from(new Set([...abilities, 'pdf_parse']))
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
                      ) : modelCategory === 'embedding' ? (
                        selectedEmbeddingModels.length > 0 ? (
                          <div className="space-y-2">
                            {selectedEmbeddingModels.map((model) =>
                              renderEmbeddingModelItem(model),
                            )}
                          </div>
                        ) : (
                          <div className="rounded-md border border-dashed py-10 text-center">
                            <p className="text-sm text-muted-foreground">
                              {categoryEmptyHint()}
                            </p>
                          </div>
                        )
                      ) : visibleLlmModels.length > 0 ? (
                        <div className="space-y-2">
                          {visibleLlmModels.map((model) => renderModelItem(model))}
                        </div>
                      ) : (
                        <div className="rounded-md border border-dashed py-10 text-center">
                          <p className="text-sm text-muted-foreground">
                            {categoryEmptyHint()}
                          </p>
                          {modelCategory === 'voice' && (
                            <Badge variant="outline" className="mt-3">
                              {t('models.ttsAbility')}
                            </Badge>
                          )}
                          {modelCategory === 'pdf' && (
                            <Badge variant="outline" className="mt-3">
                              {t('models.pdfParseAbility')}
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

      <Dialog open={providerFormOpen} onOpenChange={setProviderFormOpen} modal={false}>
        <DialogContent className="z-[1200] w-[600px] p-6">
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
